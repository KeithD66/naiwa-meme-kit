"""Small offline textured fixtures for the reusable character packager."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    import trimesh
    from PIL import Image
except ImportError:
    np = trimesh = Image = None

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'package-character.py'
SPEC = importlib.util.spec_from_file_location('package_character', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(trimesh is not None, 'Run with .venv-render/bin/python for textured packaging tests')
class PackageCharacterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.output = self.root / 'package'
        self.model = self.source / 'original.glb'
        self.diffuse = Image.fromarray(np.array([[[255, 0, 0], [0, 255, 0]],
                                                 [[0, 0, 255], [255, 255, 0]]], dtype=np.uint8))
        self.mr = Image.new('RGB', (2, 2), (255, 80, 120))

    def fixture(self, instanced=False):
        mesh = trimesh.creation.box(extents=[2, 4, 1])
        mesh.apply_translation([5, 9, -3])
        material = trimesh.visual.material.PBRMaterial(baseColorTexture=self.diffuse,
                    metallicRoughnessTexture=self.mr, roughnessFactor=0.35, metallicFactor=0.2,
                    baseColorFactor=[255, 255, 255, 255], doubleSided=False, name='body')
        uv = np.column_stack([(mesh.vertices[:, 0]-4)/2, (mesh.vertices[:, 1]-7)/4])
        mesh.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
        scene = trimesh.Scene(mesh)
        if instanced:
            geometry_name = next(iter(scene.geometry))
            transform = np.eye(4)
            transform[0, 3] = 4
            scene.graph.update(frame_to='second-instance', matrix=transform, geometry=geometry_name)
        self.model.write_bytes(scene.export(file_type='glb'))
        return self.model

    def run_package(self, model=None, yaw=30, output=None):
        return MODULE.package_character(model or self.model, self.source, 'test-job', 'naiwa',
                                        output or self.output, front_yaw=yaw)

    def test_textures_materials_pivot_scale_and_immutable_source(self):
        self.fixture()
        original = self.model.read_bytes()
        card = self.run_package()
        self.assertEqual(self.model.read_bytes(), original)
        self.assertEqual(card['source']['sha256'], hashlib.sha256(original).hexdigest())
        bounds = np.array(card['working_summary']['bounds'])
        self.assertAlmostEqual(bounds[0, 1], 0, places=6)
        self.assertAlmostEqual(bounds[1, 1], 2, places=6)
        self.assertAlmostEqual(bounds[:, 0].mean(), 0, places=6)
        self.assertAlmostEqual(bounds[:, 2].mean(), 0, places=6)
        self.assertEqual(card['working_summary']['triangle_count'], 12)
        textures = card['working_summary']['meshes'][0]['material']['textures']
        self.assertEqual(textures['baseColorTexture']['rgba_pixel_sha256'], MODULE.image_record(self.diffuse)['rgba_pixel_sha256'])
        self.assertEqual(textures['metallicRoughnessTexture']['rgba_pixel_sha256'], MODULE.image_record(self.mr)['rgba_pixel_sha256'])
        self.assertIn('metallicRoughnessTexture', card['obj_pbr_losses'])
        self.assertEqual(card['obj_summary']['triangle_count'], 12)
        self.assertGreater(card['obj_summary']['uv_mesh_count'], 0)
        self.assertFalse(card['capabilities']['animation_ready'])
        self.assertEqual(card['transformation']['working_front_axis'], '+Z')
        report = json.loads((self.output / 'safe-import-report.json').read_text())
        self.assertTrue(report['glb']['safe_to_import'])
        self.assertTrue(report['obj']['safe_to_import'])
        self.assertEqual(report['glb']['root'], str(self.output.resolve()))
        self.assertTrue((self.output / 'character.mtl').is_file())
        self.assertTrue(list(self.output.glob('*-diffuse.png')))

    def test_obj_source_roundtrip_and_source_dependencies_unchanged(self):
        self.fixture()
        self.run_package()
        # Reuse the tested diffuse exchange as a separate OBJ source package.
        import shutil
        obj_source = self.root / 'obj-source'
        obj_source.mkdir()
        for path in self.output.iterdir():
            if path.suffix in ('.obj', '.mtl', '.png'):
                shutil.copy2(path, obj_source / path.name)
        before = {p.name: MODULE.digest(p) for p in obj_source.iterdir()}
        card = MODULE.package_character(obj_source / 'character.obj', obj_source,
                  'obj-test', 'naiwa', self.root / 'obj-package')
        self.assertEqual({p.name: MODULE.digest(p) for p in obj_source.iterdir()}, before)
        self.assertEqual(card['working_summary']['triangle_count'], 12)
        self.assertTrue(card['capabilities']['uv_textured'])
        self.assertEqual(card['transformation']['front_calibration'], 'uncalibrated')

    def test_instanced_meshes_preserve_all_instances_in_obj(self):
        self.fixture(instanced=True)
        card = self.run_package()
        self.assertEqual(card['working_summary']['instance_triangle_count'], 24)
        self.assertEqual(card['obj_summary']['instance_triangle_count'], 24)

    def test_path_escape_is_blocked_before_import(self):
        obj = self.source / 'escape.obj'
        obj.write_text('mtllib ../outside.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
        (self.root / 'outside.mtl').write_text('newmtl body\nKd 1 1 1\n')
        with self.assertRaisesRegex(ValueError, 'safety audit blocked'):
            self.run_package(obj)
        self.assertFalse(self.output.exists())
        self.fixture()
        with self.assertRaisesRegex(ValueError, 'Invalid job_id'):
            MODULE.package_character(self.model, self.source, '../escape', 'naiwa', self.output)

    def test_idempotent_reuse_but_modified_output_refused(self):
        self.fixture()
        first = self.run_package()
        self.assertEqual(self.run_package()['source']['sha256'], first['source']['sha256'])
        (self.output / 'character.glb').write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError, 'modified files'):
            self.run_package()

    def test_normalization_matrix_maps_source_bounds_correctly(self):
        self.fixture()
        card = self.run_package(yaw=0)
        matrix = np.asarray(card['transformation']['source_to_working_4x4'])
        self.assertTrue(np.allclose(matrix @ [5, 7, -3, 1], [0, 0, 0, 1]))
        self.assertTrue(np.allclose(matrix @ [5, 11, -3, 1], [0, 2, 0, 1]))
        self.assertEqual(card['transformation']['height'], 2)
        self.assertIn('normalized', card['transformation']['units'])


if __name__ == '__main__':
    unittest.main()
