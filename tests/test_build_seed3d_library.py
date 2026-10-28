"""Pure metadata fixtures: no network/API, geometry loader, or visual review."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'build-seed3d-library.py'
SPEC = importlib.util.spec_from_file_location('build_seed3d_library', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Seed3DLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.job = 'seed3d-naiwa-v1'
        self.prefix = 'assets/private/seed3d/models/' + self.job
        self.input_path = 'assets/private/seed3d/references/input.png'
        self.input_hash = self.file(self.input_path, b'existing input pixels')
        self.plan = {'model': 'doubao-seed3d-2-0-260328',
                     'budget': {'declared_free_tokens': 2000000, 'batch_limit_tokens': 150000},
                     'jobs': [{'id': self.job, 'character_id': 'naiwa', 'version': 'network-seed3d-v1',
                               'source_asset_id': 'source-original', 'reference_path': self.input_path,
                               'reference_sha256': self.input_hash, 'license_status': 'source_no_license_local_only'}]}
        self.ledger = {'model': self.plan['model'], 'entries': [{'job_id': self.job, 'task_id': 'current-task',
                     'status': 'succeeded', 'reported_usage_tokens': 30000, 'reserved_tokens': 0}]}
        self.json('library/seed3d-plan.json', self.plan)
        self.json('production/seed3d/usage-ledger.json', self.ledger)

    def file(self, path, data=b'fixture'):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return MODULE.digest(target)

    def json(self, path, value):
        self.file(path, json.dumps(value).encode())

    def package(self, references=True):
        native_hash = self.file(self.prefix + '/files/native.glb', b'native mesh')
        self.json(self.prefix + '/manifest.json', {'job_id': self.job, 'reference_sha256': self.input_hash,
                  'meshes': ['files/native.glb'], 'files': [{'path': 'files/native.glb', 'sha256': native_hash}]})
        files = []
        for name, data in [('character.glb', b'normalized master'), ('character.obj', b'diffuse obj'),
                           ('character.mtl', b'material'), ('texture.png', b'texture')]:
            files.append({'path': name, 'sha256': self.file(self.prefix + '/package/' + name, data)})
        self.working_hash = files[0]['sha256']
        self.card = {'job_id': self.job, 'character_id': 'naiwa', 'source': {'sha256': native_hash},
                     'files': files, 'working_summary': {'triangle_count': 100, 'geometry_count': 1, 'instance_count': 1},
                     'obj_pbr_losses': ['metallicRoughnessTexture'],
                     'transformation': {'front_calibration': 'provided_visual_calibration'}}
        self.json(self.prefix + '/package/character-card.json', self.card)
        if not references:
            return
        views = []
        for i, (pitch, yaw) in enumerate((p, y) for p in (0, 15, -15) for y in range(0, 360, 45)):
            path = self.prefix + f'/references/view-{i:02d}.png'
            mask = self.prefix + f'/references/mask-{i:02d}.png'
            views.append({'path': path, 'sha256': self.file(path, f'view {i}'.encode()),
                          'mask_path': mask, 'mask_sha256': self.file(mask, f'mask {i}'.encode()),
                          'pitch_degrees': pitch, 'yaw_degrees': yaw})
        contact = self.prefix + '/references/contact-sheet.jpg'
        video = self.prefix + '/references/turntable.mp4'
        self.refpack = {'source_model_sha256': self.working_hash, 'views': views, 'contact_sheet': contact,
                        'turntable': {'path': video, 'camera_orbit_only': True},
                        'artifact_hashes': {'contact-sheet.jpg': self.file(contact, b'contact sheet'),
                                            'turntable.mp4': self.file(video, b'camera orbit')}}
        self.json(self.prefix + '/references/reference-pack.json', self.refpack)

    def build(self):
        return MODULE.build_library(self.root)

    def test_api_success_without_package_or_missing_dependency_is_not_complete(self):
        assets, registry, _ = self.build()
        self.assertEqual(registry['summary']['api_succeeded_jobs'], 1)
        self.assertEqual(registry['summary']['complete_jobs'], 0)
        self.assertFalse(any(a['kind'] == 'model' for a in assets['assets']))
        self.package()
        (self.root / self.prefix / 'package/texture.png').unlink()
        _, registry, _ = self.build()
        self.assertEqual(registry['summary']['complete_jobs'], 0)
        self.assertFalse(registry['versions'][0]['model_package_complete'])

    def test_complete_package_records_real_files_and_ordinary_camera_roles(self):
        self.package()
        assets, registry, markup = self.build()
        self.assertEqual(registry['summary']['complete_jobs'], 1)
        self.assertEqual(registry['versions'][0]['capabilities']['reference_views'], 24)
        self.assertEqual(registry['versions'][0]['capabilities']['silhouette_masks'], 24)
        self.assertFalse(registry['versions'][0]['rigged'])
        for asset in assets['assets']:
            self.assertTrue((self.root / asset['local_path']).is_file())
            self.assertEqual(MODULE.digest(self.root / asset['local_path']), asset['sha256'])
            self.assertTrue(asset['source_url'].startswith('https://'))
            self.assertEqual(asset['source_url'], MODULE.SEED3D_SOURCE_URL)
            self.assertEqual(asset['source_asset_id'], 'source-original')
            self.assertIsInstance(asset['tags'], list)
            self.assertIn(asset['reference_role'], {'candidate', 'front', 'side', 'back'})
            self.assertFalse(asset['publishing_allowed'])
            self.assertFalse(asset['default_identity'])
        self.assertIn('<video controls playsinline preload="none"', markup)
        self.assertNotIn('autoplay', markup)
        self.assertNotIn('https://', markup)

    def test_only_pinned_public_reference_urls_are_carried_into_catalog(self):
        self.package()
        pinned = 'https://raw.githubusercontent.com/example/repo/' + 'a'*40 + '/image.png'
        record = {'character_id': 'naiwa', 'source_asset_id': 'source-original',
                  'source_fixed_url': pinned, 'output_path': self.input_path, 'prepared_sha256': self.input_hash}
        self.json('library/seed3d-inputs.json', {'inputs': [record]})
        assets, _, _ = self.build()
        self.assertTrue(all(a['source_reference_url'] == pinned for a in assets['assets']))
        for unsafe in ('https://example.invalid/download?signature=PRIVATE_SIGNED_SECRET',
                       pinned + '?token=PRIVATE_SIGNED_SECRET', pinned.replace('a'*40, 'main'),
                       'file:///private/key', 'https://user:pass@raw.githubusercontent.com/x/y/' + 'a'*40 + '/x.png'):
            record['source_fixed_url'] = unsafe
            self.json('library/seed3d-inputs.json', {'inputs': [record]})
            with self.subTest(unsafe=unsafe):
                assets, registry, markup = self.build()
                self.assertTrue(all('source_reference_url' not in a for a in assets['assets']))
                self.assertNotIn('PRIVATE_SIGNED_SECRET', json.dumps([assets, registry]) + markup)

    def test_running_job_cannot_count_existing_package_as_completed(self):
        self.package()
        self.ledger['entries'][0].update(status='running', reserved_tokens=30000, reported_usage_tokens=None)
        self.json('production/seed3d/usage-ledger.json', self.ledger)
        assets, registry, _ = self.build()
        self.assertEqual(registry['summary']['complete_jobs'], 0)
        self.assertFalse(any(a['kind'] == 'model' for a in assets['assets']))
        self.assertEqual(registry['budget']['pending_reserved_tokens'], 30000)

    def test_visual_review_requires_current_working_model_hash(self):
        self.package()
        self.json('production/seed3d/visual-reviews.json', {'reviews': [{'job_id': self.job,
                  'working_model_sha256': self.working_hash, 'status': 'visual_checked_candidate',
                  'notes': ['Actually viewed the contact sheet'], 'default_identity': False}]})
        _, registry, _ = self.build()
        self.assertEqual(registry['versions'][0]['visual_review']['review_state'], 'current_hash')
        self.assertEqual(registry['versions'][0]['visual_review']['status'], 'visual_checked_candidate')
        new_hash = self.file(self.prefix + '/package/character.glb', b'changed model')
        self.card['files'][0]['sha256'] = new_hash
        self.json(self.prefix + '/package/character-card.json', self.card)
        _, registry, _ = self.build()
        review = registry['versions'][0]['visual_review']
        self.assertEqual(review['status'], 'not_reviewed')
        self.assertEqual(review['review_state'], 'stale_hash')
        self.assertEqual(review['notes'], [])
        self.assertFalse(registry['versions'][0]['reference_pack_complete'])

    def test_escape_html_and_do_not_copy_sensitive_or_large_fields(self):
        self.package()
        self.plan['api_key'] = 'UNKNOWN_PLAN_SECRET'
        self.plan['jobs'][0]['version'] = '<script>alert("x")</script>'
        self.plan['jobs'][0]['source_url'] = 'https://example.invalid/signed?token=URL_SECRET'
        self.ledger['entries'][0]['response'] = {'secret': 'UNKNOWN_RESPONSE_SECRET'}
        self.card['working_summary']['large_uv_data'] = 'LARGE_ARRAY_NOT_FOR_REGISTRY'
        self.card['authorization'] = 'UNKNOWN_CARD_SECRET'
        self.refpack['download_url'] = 'https://example.invalid/private?token=SIGNED_SECRET'
        self.json('library/seed3d-plan.json', self.plan)
        self.json('production/seed3d/usage-ledger.json', self.ledger)
        self.json(self.prefix + '/package/character-card.json', self.card)
        self.json(self.prefix + '/references/reference-pack.json', self.refpack)
        self.json('production/seed3d/visual-reviews.json', {'reviews': [{'job_id': self.job,
                  'working_model_sha256': self.working_hash, 'status': 'visual_checked',
                  'notes': ['<img src=x onerror=alert(1)>', 'ark-example-secret and https://x.invalid/?signature=REVIEW_SECRET']}]})
        assets, registry, markup = self.build()
        everything = json.dumps([assets, registry]) + markup
        for secret in ('UNKNOWN_PLAN_SECRET', 'URL_SECRET', 'UNKNOWN_RESPONSE_SECRET', 'LARGE_ARRAY_NOT_FOR_REGISTRY',
                       'UNKNOWN_CARD_SECRET', 'SIGNED_SECRET', 'ark-example-secret', 'REVIEW_SECRET'):
            self.assertNotIn(secret, everything)
        self.assertNotIn('<script>', markup)
        self.assertNotIn('<img src=x', markup)
        self.assertIn('&lt;script&gt;', markup)
        self.assertIn('&lt;img src=x', markup)

    def test_budget_only_current_jobs_model_and_unique_tasks(self):
        self.ledger['entries'].extend([
            {'job_id': 'old-hitem-job', 'reported_usage_tokens': 163125, 'status': 'succeeded'},
            {'job_id': self.job, 'model': 'other-model', 'reported_usage_tokens': 999999, 'status': 'succeeded'},
            dict(self.ledger['entries'][0]),
        ])
        self.json('production/seed3d/usage-ledger.json', self.ledger)
        _, registry, _ = self.build()
        self.assertEqual(registry['budget']['actual_reported_tokens'], 30000)
        self.assertFalse(registry['budget']['account_remaining_verified'])
        self.assertEqual(registry['budget']['declared_free_remaining_after_this_batch_estimate'], 1970000)

    def test_missing_or_duplicate_views_do_not_complete_and_escape_paths_rejected(self):
        self.package()
        self.refpack['views'][1] = self.refpack['views'][0]
        self.refpack['views'][2]['path'] = '../../outside.png'
        self.json(self.prefix + '/references/reference-pack.json', self.refpack)
        assets, registry, _ = self.build()
        self.assertFalse(registry['versions'][0]['reference_pack_complete'])
        self.assertFalse(any(a['local_path'].startswith('../') for a in assets['assets']))

    def test_output_guard_and_default_output_paths(self):
        self.package()
        result = MODULE.write_outputs(self.root)
        self.assertEqual(result['complete_jobs'], 1)
        self.assertTrue((self.root / 'library/seed3d-assets.json').is_file())
        self.assertTrue((self.root / 'library/seed3d-registry.json').is_file())
        self.assertTrue((self.root / 'assets/private/seed3d/index.html').is_file())
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            MODULE.write_outputs(self.root, assets_output='library/seed3d-plan.json')


if __name__ == '__main__':
    unittest.main()
