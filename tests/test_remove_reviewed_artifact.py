"""Conservative fixed-region deletion, exact UV preservation, and hash guard."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    import trimesh
    from PIL import Image
except ImportError:
    np = trimesh = Image = None

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'remove-reviewed-artifact.py'
SPEC = importlib.util.spec_from_file_location('remove_reviewed_artifact', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(trimesh is not None, 'Run with .venv-render/bin/python')
class ReviewedArtifactTests(unittest.TestCase):
    def test_selection_requires_all_corners_inside_reviewed_outer_rod_region(self):
        v = np.array([[0, -.53, -.8], [.01, -.53, -.7], [-.01, -.54, -.6],
                      [0, -.53, -.29], [.04, -.53, -.6], [0, .7, -.6], [0, -.8, -.6]])
        faces = np.array([[0, 1, 2], [1, 2, 3], [0, 1, 4], [0, 1, 5], [0, 1, 6]])
        self.assertEqual(MODULE.select_outer_rod(v, faces).tolist(), [True, False, False, False, False])

    def test_deletion_preserves_kept_positions_faces_uv_and_pbr_image(self):
        vertices = np.array([[0, -.53, -.8], [.01, -.53, -.7], [-.01, -.54, -.6],
                             [0, 0, 0], [1, 0, 0], [0, 1, 0]])
        faces = np.array([[0, 1, 2], [3, 4, 5]])
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        uv = np.array([[0, 0], [1, 0], [0, 1], [.1, .2], [.3, .4], [.5, .6]])
        image = Image.new('RGB', (2, 2), (12, 34, 56))
        mesh.visual = trimesh.visual.TextureVisuals(uv=uv, material=trimesh.visual.material.PBRMaterial(baseColorTexture=image))
        original_vertices, original_faces, original_uv = mesh.vertices.copy(), mesh.faces.copy(), mesh.visual.uv.copy()
        removed = MODULE.select_outer_rod(vertices, faces)
        result, used = MODULE.delete_faces_exact(mesh, removed)
        self.assertTrue(np.array_equal(mesh.vertices, original_vertices))
        self.assertTrue(np.array_equal(mesh.faces, original_faces))
        self.assertTrue(np.array_equal(mesh.visual.uv, original_uv))
        self.assertTrue(np.array_equal(used, [3, 4, 5]))
        self.assertTrue(np.array_equal(result.vertices, vertices[used]))
        self.assertTrue(np.array_equal(result.visual.uv, uv[used]))
        self.assertTrue(np.array_equal(result.faces, [[0, 1, 2]]))
        a = MODULE.texture_pixels(trimesh.Scene(mesh))[0]
        b = MODULE.texture_pixels(trimesh.Scene(result))[0]
        self.assertEqual(a['rgba_pixel_sha256'], b['rgba_pixel_sha256'])

    def test_cli_core_refuses_any_unreviewed_model_before_geometry_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'unreviewed.glb'
            source.write_bytes(b'not the reviewed model')
            out = Path(temporary) / 'output'
            with self.assertRaisesRegex(ValueError, 'not the manually reviewed model'):
                MODULE.repair(source, out)
            self.assertFalse(out.exists())
            self.assertEqual(source.read_bytes(), b'not the reviewed model')

    def test_empty_and_whole_model_masks_are_refused(self):
        mesh = trimesh.creation.box()
        for selected in (np.zeros(len(mesh.faces), dtype=bool), np.ones(len(mesh.faces), dtype=bool)):
            with self.assertRaisesRegex(ValueError, 'Invalid selective deletion'):
                MODULE.delete_faces_exact(mesh, selected)


if __name__ == '__main__':
    unittest.main()
