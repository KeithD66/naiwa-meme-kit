"""Offline video-routing contracts with injected adapters and temporary files."""
import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from video_pipeline import (
    AudioCueBinding, ProviderAdapter, ProviderCapabilities, ReferenceBinding,
    UnsupportedOperation, VideoPipeline, VideoPipelineError, VideoRequest,
)


PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1sAAAAASUVORK5CYII=')


class FakeAdapter(ProviderAdapter):
    def __init__(self, provider_id, capabilities=None):
        super().__init__(provider_id)
        self.value = capabilities or ProviderCapabilities(True, (6,), ('9:16',), ('720p', '1080p'), 'verified')
        self.actions = []

    def capabilities(self):
        return self.value

    def prepare(self, *args, **kwargs):
        self.actions.append('prepare')
        raise AssertionError('Offline plan must not prepare a provider request')

    def submit(self, *args, **kwargs):
        self.actions.append('submit')
        raise AssertionError('Offline plan must not submit')

    def get(self, *args, **kwargs):
        self.actions.append('get')
        raise AssertionError('Offline plan must not poll')


class VideoPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        path = self.root / 'assets/existing/naiwa.png'
        path.parent.mkdir(parents=True)
        path.write_bytes(PNG)
        self.reference = ReferenceBinding('naiwa', 'network-v1', 'naiwa-existing',
                                          'assets/existing/naiwa.png', hashlib.sha256(PNG).hexdigest())
        self.request = VideoRequest('tcp-shot-01', '奶蛙捧腹，屏幕显示 SYN；保持原图角色。', 6, '9:16', '720p', 'draft', (self.reference,))
        tiers = {'draft': ['hailuo-lite', 'grok', 'veo-draft'],
                 'standard': ['kling-720p', 'wan', 'jimeng'], 'polish': ['seedance', 'veo-fast']}
        self.config = {'schema_version': 1, 'tiers': tiers, 'providers': []}
        for ids in tiers.values():
            for provider in ids:
                self.config['providers'].append({'id': provider, 'display_name': provider, 'kind': 'video',
                    'adapter_id': None, 'planning_status': 'needs_adapter_and_model_resolution',
                    'capabilities': {'supports_image_reference': None, 'durations_seconds': [], 'aspect_ratios': [], 'resolutions': []},
                    'routing_constraints': {'resolutions': ['720p']} if provider == 'kling-720p' else {}})

    def pipeline(self, adapters=None):
        return VideoPipeline(root=self.root, config=self.config, adapters=adapters)

    def codes(self, result):
        return {b['code'] for b in result['blockers']}

    def test_all_unimplemented_profiles_remain_planning_candidates(self):
        result = self.pipeline().plan(self.request)
        self.assertEqual([c['provider_id'] for c in result['planning_candidates']], self.config['tiers']['draft'])
        self.assertEqual(result['preferred_provider_id'], 'hailuo-lite')
        self.assertIsNone(result['selected_provider_id'])
        self.assertTrue(all(c['status'] == 'needs_adapter' for c in result['planning_candidates']))
        self.assertFalse(result['submission_ready'])
        self.assertFalse(result['execution_performed'])
        self.assertEqual(result['api_calls'], 0)
        self.assertEqual(result['verified_references'][0]['attachment_status'], 'not_uploaded')
        self.assertNotIn('model_id', json.dumps(result))
        json.dumps(result, ensure_ascii=False)

    def test_verified_injected_adapter_only_selects_local_route_and_never_executes(self):
        adapter = FakeAdapter('grok')
        result = self.pipeline({'grok': adapter}).plan(self.request)
        self.assertEqual(result['selected_provider_id'], 'grok')
        self.assertEqual(result['preferred_provider_id'], 'hailuo-lite')
        self.assertEqual(adapter.actions, [])
        self.assertFalse(result['submission_ready'])
        self.assertFalse(result['automatic_fallback_performed'])
        self.assertIn('references_not_delivered', self.codes(result))

    def test_configuration_verified_or_enabled_booleans_do_not_install_an_adapter(self):
        profile = self.config['providers'][0]
        profile.update(adapter_id='pretend', enabled=True, ready=True, generation_authorized=True)
        profile['capabilities'].update(supports_image_reference=True, verification_status='verified',
                                      durations_seconds=[6], aspect_ratios=['9:16'], resolutions=['720p'])
        result = self.pipeline().plan(self.request)
        self.assertIsNone(result['selected_provider_id'])
        self.assertEqual(result['planning_candidates'][0]['capabilities_source'], 'configuration_only')

    def test_unknown_or_unverified_adapter_capabilities_are_not_eligible(self):
        for caps in (ProviderCapabilities(), ProviderCapabilities(True, (6,), ('9:16',), ('720p',)),
                     ProviderCapabilities(True, (), ('9:16',), ('720p',), 'verified')):
            with self.subTest(caps=caps):
                adapter = FakeAdapter('hailuo-lite', caps)
                result = self.pipeline({'hailuo-lite': adapter}).plan(self.request)
                self.assertIsNone(result['selected_provider_id'])
                self.assertEqual(result['planning_candidates'][0]['status'], 'needs_verification')
                self.assertEqual(adapter.actions, [])

    def test_kling_profile_720p_constraint_overrides_broader_adapter_capabilities(self):
        kling, wan = FakeAdapter('kling-720p'), FakeAdapter('wan')
        pipeline = self.pipeline({'kling-720p': kling, 'wan': wan})
        request = replace(self.request, tier='standard', resolution='1080p')
        result = pipeline.plan(request)
        self.assertEqual(result['planning_candidates'][0]['status'], 'incompatible')
        self.assertEqual(result['planning_candidates'][0]['blockers'][0]['code'], 'routing_resolution_constraint')
        self.assertEqual(result['preferred_provider_id'], 'wan')
        self.assertEqual(result['selected_provider_id'], 'wan')
        self.assertEqual(pipeline.plan(replace(request, resolution='720p'))['selected_provider_id'], 'kling-720p')
        self.assertEqual(kling.actions + wan.actions, [])

    def test_missing_identity_images_mixed_versions_and_changed_bytes_block_selection(self):
        adapter = FakeAdapter('hailuo-lite')
        pipeline = self.pipeline({'hailuo-lite': adapter})
        empty = pipeline.plan(replace(self.request, references=()))
        self.assertIn('identity_reference_required', self.codes(empty))
        self.assertIsNone(empty['selected_provider_id'])
        motion = pipeline.plan(replace(self.request, references=(replace(self.reference, role='motion'),)))
        self.assertIn('identity_reference_required', self.codes(motion))
        mixed = pipeline.plan(replace(self.request, references=(self.reference, replace(self.reference, version_id='other-v2'))))
        self.assertIn('mixed_character_versions', self.codes(mixed))
        self.assertIsNone(mixed['selected_provider_id'])
        (self.root / self.reference.path).write_bytes(PNG + b'changed')
        changed = pipeline.plan(self.request)
        self.assertIn('source_sha256_mismatch', self.codes(changed))
        self.assertIsNone(changed['selected_provider_id'])
        self.assertEqual(adapter.actions, [])

    def test_path_traversal_symlink_missing_and_non_image_reference_are_blocked(self):
        pipeline = self.pipeline()
        traversal = replace(self.reference, path='../outside.png')
        self.assertIn('source_path_outside_project', self.codes(pipeline.plan(replace(self.request, references=(traversal,)))))
        missing = replace(self.reference, path='assets/missing.png')
        self.assertIn('source_file_missing', self.codes(pipeline.plan(replace(self.request, references=(missing,)))))
        original = self.root / self.reference.path
        target = original.with_name('actual.png')
        original.rename(target)
        original.symlink_to(target)
        self.assertIn('source_symlink_not_allowed', self.codes(pipeline.plan(self.request)))
        original.unlink()
        original.write_bytes(b'words describing a character')
        wrong = replace(self.reference, sha256=hashlib.sha256(original.read_bytes()).hexdigest())
        self.assertIn('source_media_type_mismatch', self.codes(pipeline.plan(replace(self.request, references=(wrong,)))))

    def test_audio_cues_bind_existing_files_for_postproduction_without_synthesis(self):
        sound = self.root / 'assets/existing/cue.mp3'
        sound.write_bytes(b'ID3\x04\x00\x00\x00\x00\x00\x00fixture-existing-file')
        cue = AudioCueBinding('naiwa-laugh', 'existing-laugh', 'assets/existing/cue.mp3',
                              hashlib.sha256(sound.read_bytes()).hexdigest(), 1, 2.5, 'naiwa')
        result = self.pipeline().plan(replace(self.request, audio_cues=(cue,)))
        record = result['audio_postproduction'][0]
        self.assertEqual(record['stage'], 'postproduction_source_cue')
        self.assertFalse(record['voice_synthesis_performed'])
        self.assertFalse(record['audition_verified_by_pipeline'])
        self.assertEqual(record['start_seconds'], 1)
        unknown = self.pipeline().plan(replace(self.request, audio_cues=(replace(cue, character_id='naidan'),)))
        self.assertIn('audio_character_unbound', self.codes(unknown))

    def test_3d_models_cannot_be_registered_or_configured_as_video(self):
        for name in ('hitem3d-2-0', 'doubao-seed3d-2-0', 'hyper3d-gen2'):
            self.config['providers'].append({'id': name, 'kind': 'video'})
            with self.assertRaisesRegex(VideoPipelineError, '3D reconstruction'):
                self.pipeline()
            self.config['providers'].pop()
        adapter = FakeAdapter('hailuo-lite', ProviderCapabilities(True, (6,), ('9:16',), ('720p',), 'verified', kind='3d'))
        result = self.pipeline({'hailuo-lite': adapter}).plan(self.request)
        self.assertIsNone(result['selected_provider_id'])
        self.assertEqual(result['planning_candidates'][0]['blockers'][0]['code'], 'adapter_modality_mismatch')

    def test_verified_text_only_or_wrong_duration_does_not_fall_back_to_text(self):
        for caps in (ProviderCapabilities(False, (6,), ('9:16',), ('720p',), 'verified'),
                     ProviderCapabilities(True, (10,), ('9:16',), ('720p',), 'verified')):
            adapter = FakeAdapter('hailuo-lite', caps)
            result = self.pipeline({'hailuo-lite': adapter}).plan(self.request)
            self.assertEqual(result['planning_candidates'][0]['status'], 'incompatible')
            self.assertIsNone(result['selected_provider_id'])
            self.assertEqual(adapter.actions, [])

    def test_dict_contract_json_roundtrip_rejects_authorization_bool_and_base_operations_unsupported(self):
        payload = {'shot_id': 'shot-a', 'prompt': '保持图片中的奶蛙。', 'duration_seconds': 6,
                   'aspect_ratio': '9:16', 'resolution': '720p', 'tier': 'draft',
                   'references': [self.reference.__dict__]}
        request = VideoRequest.from_dict(payload)
        self.assertEqual(request.references[0], self.reference)
        payload['generation_authorized'] = True
        with self.assertRaisesRegex(VideoPipelineError, 'unsupported fields'):
            VideoRequest.from_dict(payload)

        class CapabilitiesOnly(ProviderAdapter):
            def capabilities(self):
                return ProviderCapabilities()

        adapter = CapabilitiesOnly('grok')
        for call in (lambda: adapter.prepare(request), lambda: adapter.submit({}), lambda: adapter.get('id')):
            with self.assertRaises(UnsupportedOperation):
                call()

    def test_project_relative_config_load_and_multicharacter_versions_remain_separate(self):
        config = self.root / 'library/video-providers.json'
        config.parent.mkdir()
        config.write_text(json.dumps(self.config))
        second = replace(self.reference, character_id='naidan', version_id='egg-smooth-v1')
        result = VideoPipeline(root=self.root).plan(replace(self.request, references=(self.reference, second)))
        self.assertNotIn('mixed_character_versions', self.codes(result))
        self.assertEqual({r['character_id'] for r in result['verified_references']}, {'naiwa', 'naidan'})
        camera = replace(self.reference, role='camera')
        result = VideoPipeline(root=self.root).plan(replace(self.request, references=(self.reference, camera)))
        self.assertEqual([r['role'] for r in result['verified_references']], ['identity', 'camera'])
        self.assertNotIn('identity_reference_required', self.codes(result))


if __name__ == '__main__':
    unittest.main()
