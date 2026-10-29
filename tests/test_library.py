"""Offline contract tests. All files and reviews live in a temporary project."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/library.py'


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        self.root.mkdir()
        spec = importlib.util.spec_from_file_location('isolated_library', SCRIPT)
        self.lib = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.lib)
        self.lib.ROOT = self.root
        self.lib.CATALOG = self.root / 'library/catalog.json'
        self.probe = patch.object(self.lib, 'probe', return_value={})
        self.probe.start()
        self.addCleanup(self.probe.stop)
        self.write_json('library/characters.json', {'characters': [
            {'id': 'naiwa', 'name': '奶蛙', 'aliases': ['奶娃'], 'identity_status': 'reference_selection_required'},
            {'id': 'naidan', 'name': '奶蛋', 'aliases': [], 'identity_status': 'catalog_identity_supported'},
            {'id': 'tangniu_unresolved', 'name': '唐牛', 'aliases': ['tangniu'], 'identity_status': 'unresolved'},
        ]})
        self.downloads = [
            self.download('frog-ref', 'frog.png', ['naiwa']),
            self.download('egg-ref', 'egg.png', ['naidan']),
            self.download('shared-ref', 'shared.png', ['naiwa', 'naidan']),
        ]
        self.write_json('library/downloads.json', {'assets': self.downloads})
        for name in ['frog.png', 'egg.png', 'shared.png']:
            self.write('assets/private/curated/' + name, b'fixture-image-' + name.encode())
        self.write('assets/repos/naiwa-pet/public/pets/naiwa/frames/frame_0000.webp', b'fixture-frame')
        self.write('assets/repos/NaiLoong/assets/audio/andi.mp3', b'fixture-audio')
        self.write_json('assets/repos/NaiLoong/data/naidan/voice.json', [{'src': 'assets/audio/andi.mp3', 'text': '安~迪~'}])
        self.write_json('library/audio-cues.json', {'asset_aliases': {'old-andi': 'nai-hub-andi'}, 'cues': [
            {'id': 'naidan.andi', 'character_ids': ['naidan'], 'asset_ids': ['nai-hub-andi']},
        ]})
        self.write_json('library/recipes.json', {'recipes': [{'id': 'call-response-duo', 'beats': [{'cue_ids': ['naidan.andi']}]}]})
        self.run_cli('index')

    @staticmethod
    def download(asset_id, path, characters, **extra):
        return {'id': asset_id, 'path': path, 'url': 'https://example.invalid/' + path,
                'kind': 'image', 'character_ids': characters, **extra}

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def write_json(self, relative, content):
        self.write(relative, (json.dumps(content, ensure_ascii=False) + '\n').encode())

    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = self.lib.main(list(args))
        return code, json.loads(output.getvalue())

    def asset(self, asset_id):
        return next(item for item in self.lib.catalog()['assets'] if item['id'] == asset_id)

    def approve_duo(self):
        for asset_id, bundle in [('frog-ref', 'frog-version'), ('egg-ref', 'egg-version')]:
            self.run_cli('review', asset_id, '--visual', 'visual_checked', '--note', 'Test fixture visual check',
                         '--identity-bundle-id', bundle, '--reference-role', 'identity')
        self.run_cli('review', 'nai-hub-andi', '--audio', 'auditioned_match', '--note', 'Test fixture audio check')

    def duo_args(self, *extra):
        return ('handoff', '--character', '奶蛙', '--character', '奶蛋',
                '--reference', 'frog-ref', '--reference', 'egg-ref', '--audio', 'nai-hub-andi',
                '--recipe', 'call-response-duo', '--mode', 'existing-edit',
                '--output', 'assets/private/handoff', *extra)

    def brief(self):
        return json.loads((self.root / 'assets/private/handoff/brief.json').read_text())

    def test_review_survives_index_only_for_identical_bytes(self):
        self.assertEqual(self.asset('naiwa-frame-0000')['visual_review'], 'not_reviewed')
        self.run_cli('review', 'frog-ref', '--visual', 'visual_checked', '--note', 'Viewed this exact fixture',
                     '--identity-bundle-id', 'v1', '--reference-role', 'identity')
        self.run_cli('index')
        reviewed = self.asset('frog-ref')
        self.assertEqual(reviewed['visual_review'], 'visual_checked')
        self.assertEqual(reviewed['identity_bundle_id'], 'v1')
        self.assertEqual(reviewed['review_evidence']['visual']['note'], 'Viewed this exact fixture')
        self.write('assets/private/curated/frog.png', b'different bytes')
        self.assertEqual(self.asset('frog-ref')['visual_review'], 'not_reviewed')
        self.assertEqual(self.asset('frog-ref')['review_status'], 'stale_hash')
        with self.assertRaisesRegex(ValueError, 're-index'):
            self.run_cli('review', 'frog-ref', '--visual', 'visual_checked', '--note', 'Stale catalog')
        self.run_cli('index')
        changed = self.asset('frog-ref')
        self.assertEqual(changed['visual_review'], 'not_reviewed')
        self.assertEqual(changed['review_status'], 'stale_hash')
        self.assertNotIn('identity_bundle_id', changed)
        self.assertNotIn('reference_role', changed)
        self.assertNotIn('review_evidence', changed)
        self.assertEqual(len(json.loads((self.root / 'library/reviews.json').read_text())['reviews']), 1)

    def test_seed3d_metadata_enters_catalog_without_granting_identity(self):
        self.write('assets/private/seed3d/front.png', b'derived-render')
        self.write_json('library/seed3d-assets.json', {'assets': [{
            'id': 'seed3d-example-front', 'title': 'Derived front', 'kind': 'image',
            'character_ids': ['naiwa'], 'local_path': 'assets/private/seed3d/front.png',
            'source_url': 'https://docs.volcengine.com/docs/ark/create-3d-generation-task-api',
            'identity_bundle_id': 'seed3d-version-1', 'identity_tier': 'ai_reconstruction_candidate',
            'reference_role': 'front', 'default_identity': False,
            'license_status': 'unresolved_local_only'
        }]})
        self.run_cli('index')
        item=self.asset('seed3d-example-front')
        self.assertEqual(item['availability'],'local')
        self.assertEqual(item['identity_bundle_id'],'seed3d-version-1')
        self.assertEqual(item['visual_review'],'not_reviewed')
        self.assertFalse(item['default_identity'])
        self.assertFalse(self.lib.multiview_ready([item]))

    def test_audio_review_does_not_survive_changed_hash(self):
        self.run_cli('review', 'nai-hub-andi', '--audio', 'auditioned_match', '--note', 'Heard fixture')
        self.run_cli('index')
        self.assertEqual(self.asset('nai-hub-andi')['audio_review'], 'auditioned_match')
        self.write('assets/repos/NaiLoong/assets/audio/andi.mp3', b'replaced recording')
        self.run_cli('index')
        self.assertEqual(self.asset('nai-hub-andi')['audio_review'], 'not_auditioned')
        self.assertEqual(self.asset('nai-hub-andi')['review_status'], 'stale_hash')

    def test_hyper3d_geometry_preview_is_searchable_without_identity_approval(self):
        self.write('assets/private/hyper3d/front.png', b'geometry-preview')
        self.write_json('library/hyper3d-assets.json', {'assets': [{
            'id': 'hyper3d-geometry-front', 'title': 'Geometry-only preview', 'kind': 'image',
            'character_ids': ['naiwa'], 'local_path': 'assets/private/hyper3d/front.png',
            'identity_bundle_id': 'hyper3d-geometry-v1', 'identity_tier': 'geometry_only_reconstruction_candidate',
            'reference_role': 'geometry_inspection_only', 'default_identity': False,
            'color_identity_reference_ready': False, 'source_textures_provided': False,
            'license_status': 'unresolved_local_only'
        }]})
        self.run_cli('index')
        item = self.asset('hyper3d-geometry-front')
        self.assertEqual(item['availability'], 'local')
        self.assertEqual(item['visual_review'], 'not_reviewed')
        self.assertFalse(item['source_textures_provided'])
        self.assertFalse(item['color_identity_reference_ready'])
        self.assertFalse(self.lib.multiview_ready([item]))

    def test_andi_never_binds_to_naiwa(self):
        self.approve_duo()
        self.run_cli('handoff', '--character', 'naiwa', '--reference', 'frog-ref', '--audio', 'nai-hub-andi',
                     '--recipe', 'call-response-duo', '--mode', 'existing-edit', '--output', 'assets/private/handoff')
        brief = self.brief()
        self.assertEqual(brief['character']['id'], 'naiwa')  # Old single-character contract.
        self.assertEqual(brief['audio_assets'], [])
        self.assertEqual(brief['characters'][0]['audio_assets'], [])
        self.assertEqual(brief['unassigned_assets'][0]['asset']['id'], 'nai-hub-andi')
        self.assertTrue(any('角色不匹配' in message for message in brief['blockers']))
        self.assertEqual(self.asset('nai-hub-andi')['cue_ids'], ['naidan.andi'])

    def test_duo_independent_bindings_and_draft_authority(self):
        self.approve_duo()
        self.run_cli(*self.duo_args('--position', '奶蛙=right', '--position', '奶蛋=left'))
        brief = self.brief()
        cast = {item['character_id']: item for item in brief['characters']}
        self.assertEqual(cast['naiwa']['reference_asset_ids'], ['frog-ref'])
        self.assertEqual(cast['naiwa']['audio_asset_ids'], [])
        self.assertEqual(cast['naidan']['reference_asset_ids'], ['egg-ref'])
        self.assertEqual(cast['naidan']['audio_asset_ids'], ['nai-hub-andi'])
        self.assertEqual(cast['naidan']['screen_position'], 'left')
        self.assertEqual(brief['blockers'], [])
        self.assertEqual(brief['state'], 'draft_only')
        self.assertIs(brief['generation_allowed'], False)
        self.assertIs(brief['publishing_allowed'], False)

    def test_explicit_bindings_require_cast_and_real_ownership(self):
        with self.assertRaisesRegex(ValueError, 'not in cast'):
            self.run_cli('handoff', '--character', 'naiwa', '--audio', 'naidan=nai-hub-andi',
                         '--recipe', 'call-response-duo', '--output', 'assets/private/handoff')
        with self.assertRaisesRegex(ValueError, 'Ambiguous asset binding'):
            self.run_cli(*self.duo_args('--reference', 'shared-ref'))
        self.run_cli(*self.duo_args('--reference', 'naiwa=shared-ref'))
        cast = {item['character_id']: item for item in self.brief()['characters']}
        self.assertIn('shared-ref', cast['naiwa']['reference_asset_ids'])
        self.assertNotIn('shared-ref', cast['naidan']['reference_asset_ids'])
        self.run_cli(*self.duo_args('--audio', 'naiwa=nai-hub-andi'))
        cast = {item['character_id']: item for item in self.brief()['characters']}
        self.assertEqual(cast['naiwa']['audio_asset_ids'], [])

    def test_tangniu_stays_unresolved_without_changing_other_bindings(self):
        self.approve_duo()
        self.run_cli(*self.duo_args('--character', '唐牛'))
        cast = {item['character_id']: item for item in self.brief()['characters']}
        self.assertEqual(cast['naidan']['audio_asset_ids'], ['nai-hub-andi'])
        tangniu = cast['tangniu_unresolved']
        self.assertEqual(tangniu['reference_assets'], [])
        self.assertEqual(tangniu['audio_assets'], [])
        self.assertTrue(any('未消歧' in message for message in tangniu['blockers']))

    def test_multiview_is_per_character_and_cannot_be_flagged_into_existence(self):
        self.approve_duo()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.run_cli('review', 'frog-ref', '--visual', 'visual_checked', '--note', 'Not enough evidence',
                         '--reference-role', 'verified_turnaround')
        args = list(self.duo_args())
        args[args.index('existing-edit')] = 'image-to-video'
        self.run_cli(*args)
        self.assertTrue(all(any('AI视频前置' in issue for issue in item['blockers']) for item in self.brief()['characters']))
        # A certified source record plus a hash-bound actual review can establish coverage.
        self.downloads[0].update(reference_role='verified_turnaround', identity_bundle_id='frog-version',
                                 view_coverage=['front', 'side', 'back'], multiview_evidence='Fixture source confirms all three actual views')
        self.write_json('library/downloads.json', {'assets': self.downloads})
        self.run_cli('index')
        self.run_cli(*args)
        cast = {item['character_id']: item for item in self.brief()['characters']}
        self.assertTrue(cast['naiwa']['multiview_ready'])
        self.assertFalse(cast['naidan']['multiview_ready'])
        self.assertTrue(any('AI视频前置' in issue for issue in cast['naidan']['blockers']))

    def test_path_escape_and_symlink_escape_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Path outside project'):
            self.run_cli('handoff', '--character', 'naiwa', '--recipe', 'call-response-duo', '--output', '../escape')
        outside = self.root.parent / 'outside'
        outside.mkdir()
        (self.root / 'assets/private/linked').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Path outside project'):
            self.run_cli('handoff', '--character', 'naiwa', '--recipe', 'call-response-duo', '--output', 'assets/private/linked')
        output = self.root / 'assets/private/handoff'
        output.mkdir()
        (output / 'brief.json').symlink_to(outside / 'brief.json')
        with self.assertRaisesRegex(ValueError, 'Path outside project'):
            self.run_cli('handoff', '--character', 'naiwa', '--recipe', 'call-response-duo', '--output', 'assets/private/handoff')
        self.assertFalse((outside / 'brief.json').exists())
        raw = json.loads(self.lib.CATALOG.read_text())
        next(item for item in raw['assets'] if item['id'] == 'frog-ref')['local_path'] = '../outside/frog.png'
        self.lib.CATALOG.write_text(json.dumps(raw))
        with self.assertRaisesRegex(ValueError, 'Path outside project'):
            self.run_cli('review', 'frog-ref', '--visual', 'visual_checked', '--note', 'Must not read outside project')

    def test_model_render_requires_license_and_complete_same_bundle_coverage(self):
        self.approve_duo()
        self.downloads[0].update(reference_role='licensed_model_render', identity_bundle_id='frog-version',
                                 view_coverage=['front', 'side', 'back'], multiview_evidence='Fixture renders inspected')
        self.write_json('library/downloads.json', {'assets': self.downloads})
        self.run_cli('index')
        self.assertFalse(self.lib.multiview_ready([self.asset('frog-ref')]))
        with self.assertRaisesRegex(ValueError, 'cannot replace'):
            self.run_cli('review', 'frog-ref', '--visual', 'visual_checked', '--note', 'Wrong group',
                         '--identity-bundle-id', 'another-version')
        self.downloads[0].update(model_license_status='verified_reference_render_allowed',
                                 model_license_evidence='Fixture source permits reference rendering')
        self.write_json('library/downloads.json', {'assets': self.downloads})
        self.run_cli('index')
        self.assertTrue(self.lib.multiview_ready([self.asset('frog-ref')]))
        self.downloads[0]['view_coverage'] = ['front', 'side']
        self.write_json('library/downloads.json', {'assets': self.downloads})
        self.run_cli('index')
        self.assertFalse(self.lib.multiview_ready([self.asset('frog-ref')]))

    def test_review_requires_a_real_check_and_correct_media_type(self):
        with self.assertRaisesRegex(ValueError, 'must describe'):
            self.run_cli('review', 'frog-ref', '--visual', 'visual_checked', '--note', '  ')
        with self.assertRaisesRegex(ValueError, 'Invalid audio review'):
            self.run_cli('review', 'frog-ref', '--audio', 'auditioned_match', '--note', 'Image is not audio')
        with self.assertRaisesRegex(ValueError, 'require --visual'):
            self.run_cli('review', 'nai-hub-andi', '--audio', 'auditioned_match', '--note', 'No identity flags for audio',
                         '--identity-bundle-id', 'not-a-visual-review')
        self.assertFalse((self.root / 'library/reviews.json').exists())

    def test_research_audio_is_indexed_as_remote_and_aliases_deduplicate_local_files(self):
        self.write_json('research/audio-resources.json', {'sources': [{
            'id': 'research-source', 'url': 'https://example.invalid/source', 'assets': [
                {'id': 'old-andi', 'local_path': 'assets/repos/NaiLoong/assets/audio/andi.mp3', 'character_ids': ['naidan']},
                {'id': 'remote-wav', 'local_path': 'assets/private/not-downloaded.wav', 'character_ids': ['naidan'],
                 'download_url': 'https://example.invalid/remote.wav', 'fetch_policy': 'manual_rights_review'},
                {'id': 'diyeego_andi', 'character_ids': [], 'candidate_character_ids': ['naidan'],
                 'forbid_default_for': ['naiwa'], 'download_url': 'https://example.invalid/andi.mp3'},
            ]}]})
        self.run_cli('index')
        remote = self.asset('remote-wav')
        self.assertEqual(remote['availability'], 'remote_index')
        self.assertIsNone(remote['local_path'])
        self.assertEqual(remote['fetch_policy'], 'manual_rights_review')
        self.assertNotIn('sha256', remote)
        self.assertEqual(self.asset('diyeego_andi')['character_ids'], [])
        self.assertEqual(self.asset('diyeego_andi')['candidate_character_ids'], ['naidan'])
        self.assertFalse(any(item['id'] == 'old-andi' for item in self.lib.catalog()['assets']))

    def test_doctor_separates_readiness_from_broken_references(self):
        self.write_json('research/audio-resources.json', {'sources': [{'id': 'source', 'assets': [
            {'id': 'remote-audio', 'character_ids': [], 'download_url': 'https://example.invalid/remote.mp3',
             'fetch_policy': 'manual_rights_review'}]}]})
        self.run_cli('index')
        self.write_json('library/audio-cues.json', {'cues': [
            {'id': 'naidan.andi', 'asset_ids': ['nai-hub-andi']},
            {'id': 'remote.cue', 'asset_ids': ['remote-audio']},
        ]})
        code, result = self.run_cli('doctor')
        self.assertEqual(code, 0)
        self.assertTrue(result['integrity_ok'])
        self.assertTrue(result['schema_ok'])
        self.assertTrue(any(gap['type'] == 'audio_not_local' and gap['asset_id'] == 'remote-audio' for gap in result['readiness_gaps']))
        self.write_json('library/recipes.json', {'recipes': [{'id': 'broken', 'beats': [{'cue_ids': ['does.not.exist']}]}]})
        self.write_json('library/audio-cues.json', {'cues': [
            {'id': 'naidan.andi', 'asset_ids': ['nai-hub-andi']},
            {'id': 'broken.cue', 'asset_ids': ['no-such-asset']},
        ]})
        code, result = self.run_cli('doctor')
        self.assertEqual(code, 1)
        self.assertTrue(result['integrity_ok'])
        self.assertFalse(result['schema_ok'])
        self.assertTrue(any('unknown asset ID no-such-asset' in error for error in result['schema_errors']))
        self.assertTrue(any('unknown cue ID does.not.exist' in error for error in result['schema_errors']))

    def test_self_alias_is_terminal_but_a_cross_id_cycle_is_invalid(self):
        self.write_json('library/audio-cues.json', {'asset_aliases': {'remote-audio': 'remote-audio'}, 'cues': [
            {'id': 'naidan.andi', 'asset_ids': ['nai-hub-andi']},
            {'id': 'remote.cue', 'asset_ids': ['remote-audio']},
        ]})
        self.write_json('research/audio-resources.json', {'sources': [{'id': 'source', 'assets': [
            {'id': 'remote-audio', 'character_ids': [], 'download_url': 'https://example.invalid/remote.mp3',
             'fetch_policy': 'manual_rights_review'}]}]})
        self.run_cli('index')
        self.run_cli('index')  # Rebuilding with a self alias is idempotent.
        self.assertEqual(self.asset('remote-audio')['availability'], 'remote_index')
        code, result = self.run_cli('doctor')
        self.assertEqual(code, 0)
        self.assertTrue(result['schema_ok'])
        with self.assertRaisesRegex(ValueError, 'Asset alias cycle'):
            self.lib.resolve_asset_id('A', {}, {'A': 'B', 'B': 'A'})
        with self.assertRaisesRegex(ValueError, 'Asset alias cycle'):
            self.lib.resolve_asset_id('A', {'A': {}}, {'A': 'B', 'B': 'A'})


if __name__ == '__main__':
    unittest.main()
