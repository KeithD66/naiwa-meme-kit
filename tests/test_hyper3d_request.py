"""Offline request preparation contracts; no provider calls or credentials."""
import base64
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

try:
    from PIL import Image
except ImportError:
    Image = None

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'hyper3d-request.py'
SPEC = importlib.util.spec_from_file_location('hyper3d_request', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(Image is not None, 'Use .venv-render/bin/python with Pillow')
class Hyper3DRequestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.job_id = 'hyper3d-naiwa-quad-v1'
        self.catalog = {'assets': []}
        self.reviews = {'schema_version': 1, 'reviews': []}
        self.reference = self.add_source('source-front', 'WEBP', (13, 24, 35, 180))
        self.job = {'id': self.job_id, 'character_id': 'naiwa', 'version_id': 'naiwa-hyper-quad-v1',
                    'source_version_id': 'naiwa-existing-v1', 'pose_id': 'neutral',
                    'license_status': 'local_only_source_rights_unresolved', 'references': [self.reference],
                    'multiview_evidence': None, 'prompt': '', 'seed': 8648,
                    'parameters': {'mesh_mode': 'Quad', 'material': 'PBR', 'quality_override': 50000,
                                   'hd_texture': True, 'addons': 'HighPack', 'use_original_alpha': False,
                                   'TAPose': False, 'fileformat': 'obj'}}
        self.plan = {'schema_version': 1, 'model': MODULE.MODEL, 'execution_stage': 'prepared_not_submitted',
                     'budget': {'per_success_tokens': 30000, 'batch_limit_tokens': 30000, 'max_submissions': 1,
                                'free_balance_verified': False, 'declared_free_tokens': None, 'payg_price_cny_per_success': 1.8},
                     'jobs': [self.job]}
        self.save()

    def add_source(self, asset_id, fmt='PNG', color=(70, 80, 90, 255)):
        path = self.root / 'assets/repos/existing' / (asset_id + ('.webp' if fmt == 'WEBP' else '.png'))
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGBA', (24, 32), color).save(path, format=fmt, lossless=True)
        sha = MODULE.SEED.sha256(path)
        note = 'Actually inspected this exact image: same character version, complete neutral pose and no other characters.'
        self.catalog['assets'].append({'id': asset_id, 'kind': 'image', 'availability': 'local',
             'character_ids': ['naiwa'], 'local_path': str(path.relative_to(self.root)), 'sha256': sha,
             'identity_tier': 'network_3d_candidate', 'identity_bundle_id': 'naiwa-existing-v1',
             'visual_review': 'visual_checked', 'review_status': 'current_hash',
             'review_evidence': {'sha256': sha, 'visual': {'result': 'visual_checked', 'note': note}}})
        self.reviews['reviews'].append({'asset_id': asset_id, 'sha256': sha,
             'visual': {'result': 'visual_checked', 'note': note, 'identity_bundle_id': 'naiwa-existing-v1'}})
        return {'path': str(path.relative_to(self.root)), 'sha256': sha, 'source_asset_id': asset_id,
                'version_id': 'naiwa-existing-v1', 'pose_id': 'neutral', 'view': 'front',
                'origin': 'existing_network_media', 'visual_review': {'status': 'visual_checked', 'sha256': sha, 'note': note}}

    def save(self):
        (self.root / 'library').mkdir(exist_ok=True)
        (self.root / 'library/hyper3d-plan.json').write_text(json.dumps(self.plan))
        (self.root / 'library/catalog.json').write_text(json.dumps(self.catalog))
        (self.root / 'library/reviews.json').write_text(json.dumps(self.reviews))

    def prepare(self, dry_run=False):
        self.save()
        return MODULE.prepare(self.root, selected_jobs=[self.job_id], dry_run=dry_run)[0]

    def test_webp_lossless_png_same_pixels_source_immutable_and_flags_only(self):
        source = self.root / self.reference['path']
        original = source.read_bytes()
        summary = self.prepare()
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(summary['stage'], 'prepared_not_submitted')
        self.assertEqual(summary['api_calls'], 0)
        self.assertFalse(summary['budget']['free_balance_verified'])
        self.assertFalse(summary['budget']['seed3d_allowance_applies'])
        record = summary['references'][0]
        self.assertEqual(record['source_sha256'], self.reference['sha256'])
        self.assertEqual(record['transform'], 'format_conversion_only')
        self.assertEqual(record['dimensions'], [24, 32])
        self.assertEqual(record['submitted_png_sha256'], record['submitted_sha256'])
        request = json.loads((self.root / summary['request_path']).read_text())
        self.assertEqual(set(request), {'model', 'seed', 'content'})
        self.assertEqual(request['seed'], 8648)
        self.assertTrue(request['content'][0]['text'].startswith('--mesh_mode Quad'))
        self.assertNotIn('--seed', request['content'][0]['text'])
        encoded = request['content'][1]['image_url']['url']
        self.assertTrue(encoded.startswith('data:image/png;base64,'))
        with Image.open(io.BytesIO(base64.b64decode(encoded.split(',', 1)[1]))) as converted, Image.open(source) as actual:
            self.assertEqual(converted.size, actual.size)
            self.assertEqual(converted.convert('RGBA').tobytes(), actual.convert('RGBA').tobytes())
        self.assertNotIn('base64,', json.dumps(summary))
        self.assertEqual((self.root / summary['request_path']).stat().st_mode & 0o777, 0o600)

    def test_dry_run_is_zero_write_zero_api_zero_key_read(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with (mock.patch.object(MODULE.SEED, 'get_key', side_effect=AssertionError('must not read credentials')) as key,
              mock.patch.object(MODULE.SEED, 'api_json', side_effect=AssertionError('must not call API')) as api):
            summary = MODULE.prepare(self.root, selected_jobs=[self.job_id], dry_run=True)[0]
            key.assert_not_called()
            api.assert_not_called()
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.root / 'assets/private/hyper3d').exists())
        self.assertFalse(summary['credential_read'])

    def test_multi_input_requires_matching_pose_version_evidence_and_unique_images(self):
        second = self.add_source('source-side')
        self.job['references'].append(second)
        self.job['multiview_evidence'] = 'Actual front and side files show the same original character version and the same neutral pose.'
        self.assertEqual(self.prepare(dry_run=True)['reference_count'], 2)
        self.assertFalse(self.prepare(dry_run=True)['multi_input']['ark_camera_role_semantics_verified'])
        for field, wrong in [('pose_id', 'laugh'), ('version_id', 'different-version')]:
            with self.subTest(field=field):
                previous = second[field]
                second[field] = wrong
                with self.assertRaisesRegex(MODULE.PreparationError, 'source version and pose'):
                    self.prepare(dry_run=True)
                second[field] = previous
        self.job['multiview_evidence'] = 'TBD'
        with self.assertRaisesRegex(MODULE.PreparationError, 'evidence'):
            self.prepare(dry_run=True)
        self.job['multiview_evidence'] = 'Actual files are matched to the same version and the same pose.'
        self.job['references'] = [self.reference, copy.deepcopy(self.reference)]
        with self.assertRaisesRegex(MODULE.PreparationError, 'Duplicate source image'):
            self.prepare(dry_run=True)

    def test_text_only_six_images_and_prompt_flag_injection_are_rejected(self):
        for refs in ([], [self.reference]*6):
            self.job['references'] = refs
            with self.assertRaisesRegex(MODULE.PreparationError, '1 to 5'):
                self.prepare(dry_run=True)
        self.job['references'] = [self.reference]
        for prompt in ('x'*401, 'make a character --mesh_mode Raw', '中文角色'):
            self.job['prompt'] = prompt
            with self.assertRaisesRegex(MODULE.PreparationError, 'Prompt'):
                self.prepare(dry_run=True)

    def test_mode_specific_face_range_and_tapose_remains_static(self):
        self.job['parameters']['quality_override'] = 1000000
        with self.assertRaisesRegex(MODULE.PreparationError, 'Quad quality_override'):
            self.prepare(dry_run=True)
        self.job['parameters']['mesh_mode'] = 'Raw'
        self.job['parameters']['TAPose'] = True
        summary = self.prepare(dry_run=True)
        self.assertTrue(summary['rest_pose_reconstruction_requested'])
        self.assertTrue(summary['hidden_geometry_would_be_inferred'])
        self.assertFalse(summary['rigging_created'])
        self.assertIn('--TAPose true', summary['parameter_text'])
        self.job['parameters']['quality_override'] = 499
        with self.assertRaisesRegex(MODULE.PreparationError, 'Raw quality_override'):
            self.prepare(dry_run=True)

    def test_catalog_generation_and_stale_visual_or_bytes_cannot_be_laundered(self):
        asset = self.catalog['assets'][0]
        asset['identity_tier'] = 'ai_reconstruction_candidate'
        with self.assertRaisesRegex(MODULE.PreparationError, 'masquerade'):
            self.prepare(dry_run=True)
        asset['identity_tier'] = 'network_3d_candidate'
        asset['review_evidence']['sha256'] = '0'*64
        with self.assertRaisesRegex(MODULE.PreparationError, 'Catalog lacks'):
            self.prepare(dry_run=True)
        asset['review_evidence']['sha256'] = self.reference['sha256']
        self.reference['visual_review']['sha256'] = '0'*64
        with self.assertRaisesRegex(MODULE.PreparationError, 'hash-bound visual'):
            self.prepare(dry_run=True)
        self.reference['visual_review']['sha256'] = self.reference['sha256']
        (self.root / self.reference['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(MODULE.PreparationError, 'SHA256 mismatch'):
            self.prepare(dry_run=True)

    def test_catalog_path_escape_or_symlink_cannot_read_outside_project(self):
        self.reference['path'] = '../outside.png'
        with self.assertRaisesRegex(MODULE.PreparationError, 'inside the project'):
            self.prepare(dry_run=True)
        self.reference['path'] = self.catalog['assets'][0]['local_path']
        with tempfile.TemporaryDirectory() as other:
            target = Path(other) / 'outside.webp'
            target.write_bytes((self.root / self.reference['path']).read_bytes())
            source = self.root / self.reference['path']
            source.unlink()
            source.symlink_to(target)
            with self.assertRaisesRegex(MODULE.PreparationError, 'inside the project|symlinks'):
                self.prepare(dry_run=True)

    def test_live_review_ledger_rejection_removal_or_version_change_overrides_cached_catalog(self):
        ledger_path = self.root / 'library/reviews.json'
        catalog_bytes = (self.root / 'library/catalog.json').read_bytes()
        positive = copy.deepcopy(self.reviews['reviews'][0])
        rejected = copy.deepcopy(positive)
        rejected['visual']['result'] = 'rejected'
        changed_version = copy.deepcopy(positive)
        changed_version['visual']['identity_bundle_id'] = 'different-source-version'
        cases = [([positive, rejected], 'matching positive'), ([], 'matching positive'),
                 ([changed_version], 'contradicts the source version')]
        for entries, message in cases:
            # Change only the live ledger, with no index/catalog update.
            ledger_path.write_text(json.dumps({'schema_version': 1, 'reviews': entries}))
            with self.subTest(message=message, count=len(entries)):
                with self.assertRaisesRegex(MODULE.PreparationError, message):
                    MODULE.prepare(self.root, selected_jobs=[self.job_id], dry_run=True)
                self.assertEqual((self.root / 'library/catalog.json').read_bytes(), catalog_bytes)
        ledger_path.unlink()
        with self.assertRaisesRegex(MODULE.PreparationError, 'current review ledger'):
            MODULE.prepare(self.root, selected_jobs=[self.job_id], dry_run=True)

    def test_repeated_preparation_reuses_identical_request_but_never_overwrites_another(self):
        first = self.prepare()
        second = self.prepare()
        self.assertEqual(first['request_sha256'], second['request_sha256'])
        request = self.root / first['request_path']
        original = request.read_bytes()
        self.job['seed'] += 1
        with self.assertRaisesRegex(MODULE.PreparationError, 'Existing request differs'):
            self.prepare()
        self.assertEqual(request.read_bytes(), original)

    def test_model_budget_seed_unknown_parameters_and_credentials_are_rejected(self):
        self.plan['model'] = 'doubao-seed3d-2-0-260328'
        with self.assertRaisesRegex(MODULE.PreparationError, 'fixed Hyper3D model'):
            self.prepare(dry_run=True)
        self.plan['model'] = MODULE.MODEL
        self.plan['budget']['max_submissions'] = 2
        with self.assertRaisesRegex(MODULE.PreparationError, 'budget'):
            self.prepare(dry_run=True)
        self.plan['budget']['max_submissions'] = 1
        self.job['seed'] = 65536
        with self.assertRaisesRegex(MODULE.PreparationError, 'seed'):
            self.prepare(dry_run=True)
        self.job['seed'] = 0
        self.job['parameters']['condition_mode'] = 'MultiView'
        with self.assertRaisesRegex(MODULE.PreparationError, 'supported Ark flag set'):
            self.prepare(dry_run=True)
        del self.job['parameters']['condition_mode']
        self.plan['api_key'] = 'must never reach an output'
        with self.assertRaisesRegex(MODULE.PreparationError, 'credentials'):
            self.prepare(dry_run=True)

    def test_image_constraint_uses_pixel_product_not_seed3d_edge_or_aspect_limits(self):
        path = self.root / 'skinny.png'
        Image.new('RGB', (10000, 1), (10, 20, 30)).save(path)
        _, info = MODULE.image_input(path)
        self.assertEqual(info['dimensions'], [10000, 1])
        with mock.patch.object(MODULE, 'MAX_IMAGE_PIXELS', 10000):
            with self.assertRaisesRegex(MODULE.PreparationError, 'strictly below'):
                MODULE.image_input(path)


if __name__ == '__main__':
    unittest.main()
