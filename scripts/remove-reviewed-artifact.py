#!/usr/bin/env python3
"""Delete one manually reviewed hallucinated rod segment from one pinned GLB.

This is NOT a general character-cleaning algorithm. The CLI accepts only the
reviewed original GLB SHA256 below. It removes existing faces wholly inside a
conservative, measured outboard region. No new faces, welding, hole filling,
retopology, material changes, API calls, or image synthesis are performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


PROJECT = Path(__file__).resolve().parents[1]
PINNED_INPUT_SHA256 = '1357bfd6b244d21b03b4e26ba45c69b12a47e33b5b90ce3050d60575d3b50e6f'
EXPECTED_TRIANGLES = 999922
EXPECTED_REMOVED = 9284
DEFAULT_INPUT = PROJECT / 'assets/private/seed3d/models/seed3d-lulu-community-v1/files/pbr/mesh_textured_pbr.glb'
DEFAULT_OUTPUT = PROJECT / 'assets/private/seed3d/models/seed3d-lulu-community-v1/repairs/lulu-rod-outer-v1'


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def select_outer_rod(world_vertices, faces):
    """All 3 triangle corners must satisfy the fixed reviewed world-space ROI."""
    import numpy as np
    corners = np.asarray(world_vertices)[faces]
    return ((corners[:, :, 2] < -.30).all(axis=1)
            & (np.abs(corners[:, :, 0]) < .025).all(axis=1)
            & (corners[:, :, 1] > -.56).all(axis=1)
            & (corners[:, :, 1] < -.50).all(axis=1))


def delete_faces_exact(mesh, removed):
    """Prune unreferenced records without moving, welding or changing kept faces/UV."""
    import numpy as np
    if removed.dtype != bool or len(removed) != len(mesh.faces) or not removed.any() or removed.all():
        raise ValueError('Invalid selective deletion mask')
    kept_faces = np.asarray(mesh.faces)[~removed].copy()
    used = np.unique(kept_faces)
    remap = np.full(len(mesh.vertices), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    result = mesh.copy()
    result.update_faces(~removed)
    result.remove_unreferenced_vertices()
    if not np.array_equal(result.vertices, mesh.vertices[used]) or not np.array_equal(result.faces, remap[kept_faces]):
        raise ValueError('Unexpected geometry modification during deletion')
    old_uv, new_uv = getattr(mesh.visual, 'uv', None), getattr(result.visual, 'uv', None)
    if old_uv is not None and (new_uv is None or not np.array_equal(new_uv, old_uv[used])):
        raise ValueError('Retained UV coordinates changed')
    return result, used


def texture_pixels(scene):
    result = []
    for geometry, mesh in scene.geometry.items():
        material = getattr(mesh.visual, 'material', None)
        for channel in ('baseColorTexture', 'metallicRoughnessTexture', 'normalTexture', 'occlusionTexture', 'emissiveTexture', 'image'):
            image = getattr(material, channel, None)
            if image is not None:
                result.append({'geometry': str(geometry), 'channel': channel, 'size': list(image.size),
                               'rgba_pixel_sha256': hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest()})
    return sorted(result, key=lambda r: (r['channel'], r['rgba_pixel_sha256']))


def component_diagnostics(world_vertices, faces, removed):
    """Exact-coordinate adjacency is diagnostic only; output vertices are NOT welded."""
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    unique, inv = np.unique(world_vertices, axis=0, return_inverse=True)
    mapped = inv[faces]
    links = np.vstack((mapped[:, :2], mapped[:, 1:]))
    graph = coo_matrix((np.ones(len(links), dtype=np.uint8), (links[:, 0], links[:, 1])),
                      shape=(len(unique), len(unique))).tocsr()
    count, _ = connected_components(graph, directed=False)
    selected = mapped[removed]
    edges = np.vstack((selected[:, :2], selected[:, 1:], selected[:, [2, 0]]))
    edges, counts = np.unique(np.sort(edges, axis=1), axis=0, return_counts=True)
    frontier = edges[counts == 1]
    boundary_vertices = unique[np.unique(frontier)]
    return {'exact_position_components_before': int(count), 'position_unique_vertices_before': len(unique),
            'removed_patch_frontier_edges': len(frontier),
            'frontier_world_bbox': [boundary_vertices.min(0).tolist(), boundary_vertices.max(0).tolist()],
            'uv_seams_not_used_as_component_boundaries': True,
            'diagnostic_position_deduplication_did_not_modify_output_geometry': True}


def repair(input_path=DEFAULT_INPUT, output_dir=DEFAULT_OUTPUT):
    # Verify the immutable original BEFORE importing geometry. No arbitrary model
    # can be accepted by changing a CLI threshold or supplying an expected hash.
    input_path, output_dir = Path(input_path).resolve(), Path(output_dir).resolve()
    raw_sha = sha256_file(input_path)
    if raw_sha != PINNED_INPUT_SHA256:
        raise ValueError('Input SHA256 is not the manually reviewed model; no repair performed')
    if input_path.is_relative_to(output_dir):
        raise ValueError('Output directory must not contain the original input')
    if output_dir.exists():
        report_path, model_path = output_dir / 'repair-report.json', output_dir / 'cleaned.glb'
        if report_path.is_file() and model_path.is_file():
            previous = json.loads(report_path.read_text())
            if previous.get('input_sha256') == raw_sha and previous.get('output_sha256') == sha256_file(model_path):
                return previous
        raise ValueError('Existing repair output differs; preserve it and choose a fresh directory')
    import numpy as np
    import trimesh
    scene = trimesh.load_scene(input_path, process=False, maintain_order=True)
    if len(scene.geometry) != 1 or len(scene.graph.nodes_geometry) != 1:
        raise ValueError('Pinned model structure differs from the reviewed single-mesh scene')
    node = next(iter(scene.graph.nodes_geometry))
    transform, geometry = scene.graph[node]
    mesh = scene.geometry[geometry]
    if len(mesh.faces) != EXPECTED_TRIANGLES or getattr(mesh.visual, 'uv', None) is None:
        raise ValueError('Pinned triangle/UV structure differs from review')
    world = trimesh.transform_points(mesh.vertices, transform)
    removed = select_outer_rod(world, mesh.faces)
    if int(removed.sum()) != EXPECTED_REMOVED:
        raise ValueError('Fixed reviewed selection no longer produces its expected face count')
    selected_vertices = world[np.unique(mesh.faces[removed])]
    diagnostics = component_diagnostics(world, mesh.faces, removed)
    textures_before = texture_pixels(scene)
    cleaned, used = delete_faces_exact(mesh, removed)
    scene.geometry[geometry] = cleaned
    after_world = trimesh.transform_points(cleaned.vertices, transform)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    build = Path(tempfile.mkdtemp(prefix='.repair-build-', dir=output_dir.parent))
    try:
        output = build / 'cleaned.glb'
        output.write_bytes(scene.export(file_type='glb', include_normals=None))
        loaded = trimesh.load_scene(output, process=False, maintain_order=True)
        textures_after = texture_pixels(loaded)
        comparable = lambda values: [{k: v for k, v in r.items() if k != 'geometry'} for r in values]
        if comparable(textures_before) != comparable(textures_after):
            raise ValueError('Export changed a PBR texture image')
        loaded_mesh = next(iter(loaded.geometry.values()))
        if len(loaded_mesh.faces) != EXPECTED_TRIANGLES-EXPECTED_REMOVED:
            raise ValueError('Export changed retained triangle count')
        if not np.array_equal(loaded_mesh.visual.uv, cleaned.visual.uv):
            raise ValueError('Export changed retained UV coordinates')
        if not np.allclose(loaded_mesh.vertices, cleaned.vertices, atol=1e-8, rtol=1e-7):
            raise ValueError('Export changed retained vertex positions')
        if sha256_file(input_path) != raw_sha:
            raise ValueError('Original source changed during processing')
        report = {'schema_version': 1, 'repair_id': 'lulu-reviewed-outer-rod-removal-v1',
                  'input_path': str(input_path), 'input_sha256': raw_sha,
                  'output_path': str(output_dir / 'cleaned.glb'), 'output_sha256': sha256_file(output),
                  'reason': 'Manual comparison of the prepared source and actual contact sheet identified an unsupported thin rod extending horizontally behind the waist. The source has no such rod.',
                  'visual_basis': [
                      {'path': 'assets/private/seed3d/references/lulu-community.png', 'sha256': 'ea5e5b79e1e396cbc63f71c7574ee2cab3a3190ea10694033b2e14836d8464f4'},
                      {'path': 'assets/private/seed3d/models/seed3d-lulu-community-v1/references/contact-sheet.jpg', 'sha256': 'f82375a5096eddb1307d09ec74eebd4b637483fd1756ce2ed585547ed22c5594'}],
                  'selection': {'scope': 'fixed original GLB hash only', 'coordinate_frame': 'native scene world coordinates, before package normalization',
                                'rule': 'remove a triangle only when all three corners have z < -0.30, abs(x) < 0.025, -0.56 < y < -0.50',
                                'native_node_matrix': transform.tolist(),
                                'removed_world_bbox': [selected_vertices.min(0).tolist(), selected_vertices.max(0).tolist()],
                                'whole_connected_component_deleted': False,
                                'body_hat_stem_arms_feet_outside_reviewed_roi_preserved': True},
                  'before': {'triangles': len(mesh.faces), 'vertices': len(mesh.vertices),
                             'world_bbox': [world.min(0).tolist(), world.max(0).tolist()]},
                  'after': {'triangles': len(cleaned.faces), 'vertices': len(cleaned.vertices),
                            'world_bbox': [after_world.min(0).tolist(), after_world.max(0).tolist()]},
                  'before_triangles': len(mesh.faces), 'after_triangles': len(cleaned.faces),
                  'removed_triangles': int(removed.sum()), 'removed_unreferenced_vertex_records': len(mesh.vertices)-len(used),
                  'source_images_preserved': True, 'textures_before': textures_before, 'textures_after': textures_after,
                  'retained_uv_exact': True, 'retained_positions_exact_before_export': True,
                  'diagnostics': diagnostics,
                  'limitations': ['The rod is connected to the body; this deletes only its unambiguous outboard segment.',
                                  'The cut leaves 86 position-space boundary edges; no cap or hole filling was added.',
                                  'A small attachment/stub may remain near z=-0.32 to -0.27. Body-facing root geometry is deliberately retained.',
                                  'This is a local edited reconstruction candidate, not an unmodified API result or verified original character.'],
                  'welding_performed': False, 'hole_filling_performed': False, 'new_faces_added': 0,
                  'identity_verified': False, 'default_identity': False, 'usage_scope': 'local_reference_only'}
        (build / 'repair-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        build.rename(output_dir)
        return report
    except BaseException:
        shutil.rmtree(build, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        report = repair(args.input, args.output_dir)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, str(exc)+'\n')
    print(json.dumps({k: report[k] for k in ('input_sha256', 'output_path', 'output_sha256', 'removed_triangles', 'after_triangles', 'source_images_preserved')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
