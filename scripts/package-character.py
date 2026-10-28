#!/usr/bin/env python3
"""Package an existing audited character model for local 3D/reference workflows.

Run with .venv-render/bin/python. No network/API calls, mesh repair, welding,
rigging, or character generation. GLB is the material master; OBJ is a diffuse
exchange copy. Source geometry and dependencies are never overwritten.
"""
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import tempfile
import argparse


AUDIT_SPEC = importlib.util.spec_from_file_location('character_model_audit', Path(__file__).with_name('inspect-model.py'))
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def image_record(image):
    if image is None:
        return None
    # Canonical RGBA pixels tolerate lossless RGB/RGBA container differences.
    rgba = image.convert('RGBA')
    return {'size': list(image.size), 'source_mode': image.mode,
            'rgba_pixel_sha256': hashlib.sha256(rgba.tobytes()).hexdigest()}


def material_record(material):
    import numpy as np
    result = {'type': type(material).__name__, 'textures': {}}
    for name in ('baseColorTexture', 'metallicRoughnessTexture', 'normalTexture', 'occlusionTexture',
                 'emissiveTexture', 'image'):
        image = getattr(material, name, None)
        if image is not None:
            result['textures'][name] = image_record(image)
    for name in ('baseColorFactor', 'metallicFactor', 'roughnessFactor', 'emissiveFactor',
                 'alphaMode', 'alphaCutoff', 'doubleSided', 'diffuse'):
        value = getattr(material, name, None)
        if value is not None:
            result[name] = value if isinstance(value, (str, bool)) else np.asarray(value).tolist()
    return result


def summarize(scene):
    import numpy as np
    import trimesh
    meshes = []
    for name, mesh in scene.geometry.items():
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError('Only triangle meshes are supported; no point/line fallback')
        uv = getattr(mesh.visual, 'uv', None)
        material = getattr(mesh.visual, 'material', None)
        meshes.append({'name': str(name), 'vertices': len(mesh.vertices), 'triangles': len(mesh.faces),
                       'visual_kind': mesh.visual.kind, 'uv_vertices': len(uv) if uv is not None else 0,
                       'uv_bounds': [np.min(uv, axis=0).tolist(), np.max(uv, axis=0).tolist()] if uv is not None and len(uv) else None,
                       'material': material_record(material) if material is not None else None})
    instances = []
    for node in scene.graph.nodes_geometry:
        transform, geometry = scene.graph[node]
        instances.append({'node': str(node), 'geometry': str(geometry),
                          'triangles': len(scene.geometry[geometry].faces), 'transform': transform.tolist()})
    return {'bounds': np.asarray(scene.bounds).tolist(), 'geometry_count': len(meshes),
            'instance_count': len(instances), 'triangle_count': sum(m['triangles'] for m in meshes),
            'instance_triangle_count': sum(i['triangles'] for i in instances),
            'uv_mesh_count': sum(m['uv_vertices'] > 0 for m in meshes), 'meshes': meshes, 'instances': instances}


def texture_inventory(summary, diffuse_only=False):
    values = Counter()
    instances = Counter(item['geometry'] for item in summary['instances'])
    for mesh in summary['meshes']:
        for channel, image in (mesh['material'] or {}).get('textures', {}).items():
            if diffuse_only and channel not in ('baseColorTexture', 'image'):
                continue
            # Channel spelling changes from SimpleMaterial image to PBR baseColorTexture.
            channel = 'baseColorTexture' if channel == 'image' else channel
            values[(channel, tuple(image['size']), image['rgba_pixel_sha256'])] += mesh['triangles'] * instances[mesh['name']]
    return values


def verify_roundtrip(before, after, *, diffuse_only=False, flatten=False):
    import numpy as np
    before_triangles = before['instance_triangle_count']
    if before_triangles != after['instance_triangle_count']:
        raise ValueError('Conversion changed triangle/instance counts')
    if not np.allclose(before['bounds'], after['bounds'], rtol=1e-6, atol=2e-6):
        raise ValueError('Conversion changed model bounds')
    expected, actual = texture_inventory(before, diffuse_only), texture_inventory(after, diffuse_only)
    # Weight each texture binding by instanced triangles, so a map silently lost
    # from one mesh cannot pass because another mesh still references that image.
    if expected != actual:
        raise ValueError('Conversion changed or dropped texture pixels/channels')
    if before['uv_mesh_count'] and not after['uv_mesh_count']:
        raise ValueError('Conversion dropped UV coordinates')
    expected_uv = sorted(tuple(tuple(row) for row in m['uv_bounds']) for m in before['meshes'] if m['uv_bounds'])
    actual_uv = sorted(tuple(tuple(row) for row in m['uv_bounds']) for m in after['meshes'] if m['uv_bounds'])
    if len(expected_uv) == len(actual_uv) and not np.allclose(expected_uv, actual_uv, atol=2e-6, rtol=1e-6):
        raise ValueError('Conversion changed UV bounds')


def write_obj(scene, destination):
    """Bake only scene transforms; explicit separate v/vt offsets avoid exporter ambiguity."""
    import numpy as np
    from PIL import Image
    lines = ['# Local normalized diffuse exchange; GLB is the PBR master', 'mtllib character.mtl']
    materials, losses = [], set()
    voffset = uoffset = 0
    for index, node in enumerate(scene.graph.nodes_geometry):
        transform, geometry_name = scene.graph[node]
        mesh = scene.geometry[geometry_name].copy()
        mesh.apply_transform(transform)
        name = f'material_{index:04d}'
        lines.extend([f'o mesh_{index:04d}', f'usemtl {name}'])
        uv = getattr(mesh.visual, 'uv', None)
        material = getattr(mesh.visual, 'material', None)
        record = material_record(material) if material is not None else {'textures': {}}
        losses.update(k for k in record['textures'] if k not in ('baseColorTexture', 'image'))
        losses.update(k for k in ('metallicFactor', 'roughnessFactor', 'emissiveFactor', 'alphaMode',
                                 'alphaCutoff', 'doubleSided') if k in record)
        if uv is not None and len(uv) != len(mesh.vertices):
            raise ValueError('UV count does not match vertex count')
        simple = material.to_simple() if hasattr(material, 'to_simple') else material
        color = getattr(simple, 'diffuse', np.array([255, 255, 255, 255]))
        color = np.asarray(color, dtype=float) / 255.0
        image = getattr(simple, 'image', None)
        mtl = [f'newmtl {name}', 'Kd ' + ' '.join(f'{n:.9g}' for n in color[:3]),
               f'd {color[3] if len(color) > 3 else 1:.9g}', 'illum 2']
        if image is not None:
            if uv is None:
                raise ValueError('Diffuse image exists without UV coordinates')
            filename = f'{name}-diffuse.png'
            image.save(destination / filename, format='PNG')
            # Verify the lossless exported container before referencing it.
            with Image.open(destination / filename) as exported:
                if image_record(exported)['rgba_pixel_sha256'] != image_record(image)['rgba_pixel_sha256']:
                    raise ValueError('PNG export changed diffuse pixels')
            mtl.append(f'map_Kd {filename}')
        materials.extend(mtl + [''])
        vertex_colors = getattr(mesh.visual, 'vertex_colors', None) if mesh.visual.kind in ('vertex', 'face') else None
        if mesh.visual.kind == 'face':
            losses.add('face_colors_approximated_as_vertex_colors_in_obj')
        for i, vertex in enumerate(mesh.vertices):
            text = 'v ' + ' '.join(f'{n:.9g}' for n in vertex)
            if vertex_colors is not None:
                text += ' ' + ' '.join(f'{n/255:.9g}' for n in vertex_colors[i][:3])
            lines.append(text)
        if uv is not None:
            lines.extend('vt ' + ' '.join(f'{n:.9g}' for n in value) for value in uv)
        for face in mesh.faces:
            lines.append('f ' + ' '.join(f'{v+voffset+1}/{v+uoffset+1}' if uv is not None else str(v+voffset+1) for v in face))
        voffset += len(mesh.vertices)
        uoffset += len(uv) if uv is not None else 0
    (destination / 'character.obj').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (destination / 'character.mtl').write_text('\n'.join(materials), encoding='utf-8')
    return sorted(losses | {'normal_vectors_recomputed_by_importer_not_embedded_in_obj'})


def package_character(model, source_root, job_id, character_id, output, front_yaw=None, up_axis='y'):
    import numpy as np
    import trimesh
    model, source_root, output = Path(model).resolve(), Path(source_root).resolve(), Path(output).resolve()
    for label, value in (('job_id', job_id), ('character_id', character_id)):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', value):
            raise ValueError(f'Invalid {label}')
    if front_yaw is not None and not math.isfinite(front_yaw):
        raise ValueError('front_yaw must be finite')
    if up_axis not in {'x', 'y', 'z'}:
        raise ValueError('up_axis must be x, y, or z')
    source_audit = AUDIT.audit_model(model, source_root)
    if not source_audit['safe_to_import']:
        raise ValueError('Source safety audit blocked: ' + ', '.join(i['code'] for i in source_audit['issues'] if i['severity'] == 'error'))
    if source_audit.get('skin_count', 0) or source_audit.get('animation_count', 0):
        raise ValueError('Animated/skinned source must not be flattened by a static-reference packager')
    settings = {'job_id': job_id, 'character_id': character_id, 'source_sha256': source_audit['sha256'],
                'source_dependencies': source_audit['dependencies'], 'front_yaw_degrees': front_yaw, 'up_axis': up_axis}
    if output.exists():
        card_path = output / 'character-card.json'
        if card_path.is_file():
            existing = json.loads(card_path.read_text())
            files = existing.get('files', [])
            if (existing.get('settings') == settings and files
                    and all(Path(f['path']).name == f['path'] and (output / f['path']).resolve().is_relative_to(output)
                            and (output / f['path']).is_file() and digest(output / f['path']) == f['sha256'] for f in files)):
                return existing
        raise ValueError('Output exists with different settings or modified files; choose a fresh destination')
    protected = {model} | {source_root / item['path'] for item in source_audit['dependencies']}
    if any(output == p or p.is_relative_to(output) for p in protected):
        raise ValueError('Output must not contain or overwrite any source file')
    # OBJ UV seams may require splitting a position into distinct UV vertices.
    # This importer step is representation-only, never welding or face repair.
    scene = trimesh.load_scene(model, process=False, maintain_order=model.suffix.lower() != '.obj')
    original = summarize(scene)
    if original['triangle_count'] != source_audit['triangle_count']:
        raise ValueError('Loader triangle count differs from independent source audit')
    if model.suffix.lower() == '.glb':
        if source_audit.get('texture_count', 0) and not texture_inventory(original):
            raise ValueError('Loader dropped source GLB textures')
        expected_channels, loaded_channels = Counter(), Counter()
        for primitive in source_audit['meshes']:
            index = primitive.get('material_index')
            if index is None:
                continue
            material = source_audit['materials'][index]
            if material.get('extensions'):
                raise ValueError('Source material extensions require explicit preservation support')
            channels = set(k for k in material if k.endswith('Texture'))
            channels.update(k for k in material.get('pbrMetallicRoughness', {}) if k.endswith('Texture'))
            expected_channels.update({k: primitive['triangle_count'] for k in channels})
        for mesh in original['meshes']:
            loaded_channels.update({k: mesh['triangles'] for k in (mesh['material'] or {}).get('textures', {})})
        if expected_channels != loaded_channels:
            raise ValueError('Loader changed source GLB material texture-channel coverage')
    else:
        source_maps = [m for material in source_audit.get('materials', []) for m in material['texture_maps']]
        unsupported = {m['channel'] for m in source_maps if m['channel'].lower() != 'map_kd'}
        if unsupported:
            raise ValueError('OBJ non-diffuse map import needs explicit PBR mapping: ' + ', '.join(sorted(unsupported)))
        if source_maps and not texture_inventory(original):
            raise ValueError('Loader dropped source OBJ diffuse texture')
        from PIL import Image
        loaded_images = {key[2] for key in texture_inventory(original)}
        for texture in source_maps:
            with Image.open(source_root / texture['path']) as image:
                if image_record(image)['rgba_pixel_sha256'] not in loaded_images:
                    raise ValueError('Loader dropped or changed a source OBJ diffuse image')
    up_rotation = np.eye(4)
    if up_axis == 'z':
        up_rotation = trimesh.transformations.rotation_matrix(-math.pi/2, [1, 0, 0])
    elif up_axis == 'x':
        up_rotation = trimesh.transformations.rotation_matrix(math.pi/2, [0, 0, 1])
    yaw_rotation = trimesh.transformations.rotation_matrix(-math.radians(front_yaw or 0), [0, 1, 0])
    rotation = yaw_rotation @ up_rotation
    scene.apply_transform(rotation)
    bounds = np.asarray(scene.bounds, dtype=float)
    height = bounds[1, 1] - bounds[0, 1]
    if not np.isfinite(bounds).all() or height <= 1e-12:
        raise ValueError('Model has invalid bounds or zero height for selected up axis')
    scale = 2.0/height
    center = np.array([(bounds[0, 0]+bounds[1, 0])/2, bounds[0, 1], (bounds[0, 2]+bounds[1, 2])/2])
    scale_matrix = np.diag([scale, scale, scale, 1])
    translation = np.eye(4)
    translation[:3, 3] = -center * scale
    normalization = translation @ scale_matrix
    scene.apply_transform(normalization)
    matrix = normalization @ rotation
    normalized = summarize(scene)
    output.parent.mkdir(parents=True, exist_ok=True)
    build = Path(tempfile.mkdtemp(prefix='.package-build-', dir=output.parent))
    try:
        master = build / 'character.glb'
        master.write_bytes(scene.export(file_type='glb', include_normals=None))
        master_audit = AUDIT.audit_model(master, build)
        if not master_audit['safe_to_import']:
            raise ValueError('Exported GLB failed independent safety audit')
        master_summary = summarize(trimesh.load_scene(master, process=False, maintain_order=True))
        verify_roundtrip(normalized, master_summary)
        losses = write_obj(scene, build)
        obj_audit = AUDIT.audit_model(build / 'character.obj', build)
        if not obj_audit['safe_to_import']:
            raise ValueError('Exported OBJ failed independent safety audit')
        obj_summary = summarize(trimesh.load_scene(build / 'character.obj', process=False, maintain_order=False))
        verify_roundtrip(normalized, obj_summary, diffuse_only=True, flatten=True)
        for path in protected:
            expected = source_audit['sha256'] if path == model else next(d['sha256'] for d in source_audit['dependencies'] if source_root / d['path'] == path)
            if digest(path) != expected:
                raise ValueError('Source file changed during packaging')
        for report, name in ((master_audit, 'character.glb'), (obj_audit, 'character.obj')):
            report['input'], report['root'] = str(output / name), str(output)
        dump(build / 'source-audit.json', source_audit)
        dump(build / 'safe-import-report.json', {'source': source_audit, 'glb': master_audit, 'obj': obj_audit,
              'roundtrip': {'glb_geometry_uv_texture_pixels': 'passed', 'obj_geometry_uv_diffuse_pixels': 'passed'},
              'obj_pbr_losses': losses})
        card = {'schema_version': 1, 'settings': settings, 'character_id': character_id, 'job_id': job_id,
                'source': {'path': str(model), 'sha256': source_audit['sha256'], 'immutable': True},
                'identity_status': 'unreviewed_reconstruction_candidate',
                'usage_scope': 'local_reference_only; source media rights still apply',
                'transformation': {'source_to_working_4x4': matrix.tolist(), 'uniform_scale': scale,
                                   'source_up_axis': '+' + up_axis.upper(), 'working_up_axis': '+Y',
                                   'front_yaw_source_camera_degrees': front_yaw,
                                   'front_calibration': 'provided_visual_calibration' if front_yaw is not None else 'uncalibrated',
                                   'working_front_axis': '+Z' if front_yaw is not None else 'unverified',
                                   'height': 2, 'units': 'normalized units, not metres or centimetres',
                                   'pivot': 'horizontal bounds centre at lowest geometry Y=0'},
                'source_summary': original, 'working_summary': master_summary, 'obj_summary': obj_summary,
                'capabilities': {'static_reference_render': True, 'uv_textured': bool(texture_inventory(master_summary)),
                                 'rigged': False, 'animated': False, 'animation_ready': False,
                                 'identity_verified': False, 'unseen_views_verified': False,
                                 'mesh_repair_or_welding': False},
                'material_master': 'character.glb', 'exchange_obj': 'character.obj',
                'obj_pbr_losses': losses, 'files': []}
        text = f"# {character_id} · {job_id}\n\nExisting-reference reconstruction candidate for local use. Identity and inferred back views require visual review.\n\n"
        text += 'Use `character.glb` as the PBR material master. `character.obj` + `character.mtl` + PNG files are a diffuse Blender exchange copy.\n\n'
        text += 'Height: 2 normalized units; +Y up; horizontal bounds centred; geometry bottom Y=0. This is not a real-world measurement.\n\n'
        text += f"Source SHA256: `{source_audit['sha256']}`. Front: {card['transformation']['front_calibration']}.\n\n"
        text += 'No rigging, topology repair, welding, retopology, or invented character views were added. The lowest source geometry is the pivot; it is not a semantic foot detector.\n\n'
        text += 'OBJ limitations: ' + ', '.join(losses) + '.\n'
        (build / 'character-card.md').write_text(text, encoding='utf-8')
        for path in sorted(build.iterdir()):
            card['files'].append({'path': path.name, 'bytes': path.stat().st_size, 'sha256': digest(path)})
        dump(build / 'character-card.json', card)
        build.rename(output)
        return card
    except BaseException:
        shutil.rmtree(build, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--job-id', required=True)
    parser.add_argument('--character-id', required=True)
    parser.add_argument('--front-yaw', type=float, help='Source front-camera yaw; working model rotates by its negative')
    parser.add_argument('--up-axis', choices=['x', 'y', 'z'], default='y', help='Explicit source up axis; never automatically guessed')
    parser.add_argument('--output', type=Path, help='Default assets/private/seed3d/models/JOB/package')
    args = parser.parse_args()
    output = args.output or Path('assets/private/seed3d/models') / args.job_id / 'package'
    try:
        card = package_character(args.model, args.source_root, args.job_id, args.character_id,
                                 output, args.front_yaw, args.up_axis)
    except (ValueError, OSError, KeyError, IndexError, TypeError) as exc:
        parser.exit(2, f'Packaging blocked: {exc}\n')
    print(json.dumps({'output': str(output), 'character_id': card['character_id'], 'job_id': card['job_id'],
                      'source_sha256': card['source']['sha256'], 'triangles': card['working_summary']['triangle_count'],
                      'bounds': card['working_summary']['bounds'], 'capabilities': card['capabilities']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
