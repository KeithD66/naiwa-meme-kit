"""Offline checks for the actual-result/failure-benchmark index."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/build-hyper3d-library.py'
SPEC = importlib.util.spec_from_file_location('hyper_library', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HyperLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = 'hyper3d-test-v1'
        self.base = self.root / 'assets/private/hyper3d/models' / self.job
        (self.base / 'files').mkdir(parents=True)
        self.native = self.base / 'files/model.obj'
        self.native.write_text('v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n')
        self.sha = hashlib.sha256(self.native.read_bytes()).hexdigest()
        self.write('library/hyper3d-plan.json', {'model': MODULE.MODEL, 'jobs': [{
            'id': self.job, 'character_id': 'naiwa', 'version_id': 'hyper-quad-v1',
            'license_status': 'local_only', 'references': [{'source_asset_id': 'existing-image'}]}]})
        self.write('production/hyper3d/usage-ledger.json', {'model': MODULE.MODEL, 'entries': [{
            'job_id': self.job, 'task_id': 'task-one', 'status': 'succeeded',
            'reference_sha256': 'a' * 64, 'reported_usage_tokens': 30000, 'reserved_tokens': 0}]})
        self.write(self.base / 'manifest.json', {'model': MODULE.MODEL, 'task_id': 'task-one',
            'texture_files_returned': False, 'files': [{'path': 'files/model.obj', 'sha256': self.sha}]})
        self.write(self.base / 'native-audit.json', {'sha256': self.sha, 'material_count': 0,
            'meshes': [{'face_count': 1, 'source_face_vertex_histogram': {'4': 1}, 'quad_face_fraction': 1.0}]})

    def write(self, name, value):
        path = Path(name)
        if not path.is_absolute():
            path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def test_native_quads_are_indexed_without_material_or_identity_approval(self):
        registry = MODULE.build(self.root)
        self.assertEqual(registry['reported_usage_tokens'], 30000)
        self.assertEqual(registry['reserved_tokens'], 0)
        self.assertEqual(registry['versions'][0]['quad_face_fraction'], 1)
        assets = json.loads((self.root / 'library/hyper3d-assets.json').read_text())['assets']
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]['sha256'], self.sha)
        self.assertFalse(assets[0]['source_materials_provided'])
        self.assertFalse(assets[0]['source_textures_provided'])
        self.assertFalse(assets[0]['color_identity_reference_ready'])
        self.assertFalse(assets[0]['default_identity'])
        gallery = (self.root / 'assets/private/hyper3d/index.html').read_text()
        self.assertNotIn('src="http', gallery)
        self.assertNotIn('autoplay', gallery)
        self.assertNotIn('身份拒绝：多出', gallery)  # No review must not fabricate a diagnosis.

    def test_changed_native_bytes_cannot_reuse_an_old_audit(self):
        self.native.write_text(self.native.read_text() + '# changed\n')
        with self.assertRaisesRegex(ValueError, 'audit hash'):
            MODULE.build(self.root)
        self.assertFalse((self.root / 'library/hyper3d-assets.json').exists())

    def test_another_task_cannot_be_associated_with_the_charged_job(self):
        path = self.base / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['task_id'] = 'different-task'
        self.write(path, manifest)
        with self.assertRaisesRegex(ValueError, 'match ledger'):
            MODULE.build(self.root)


if __name__ == '__main__':
    unittest.main()
