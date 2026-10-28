"""Standard-library contracts for reference-bound, offline video routing.

Empty capability arrays mean UNKNOWN, not unlimited support. Empty profile
``routing_constraints`` impose no extra policy restriction. Provider config is
planning metadata, never proof of an installed adapter, live account access,
uploaded reference, authorization, or a billable request being submitted.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIERS = {'draft', 'standard', 'polish'}
ROLES = {'identity', 'motion', 'camera'}


class VideoPipelineError(ValueError):
    """Invalid request/configuration, with no remote response or credential data."""


class UnsupportedOperation(RuntimeError):
    """A provider operation has not been implemented."""


def _identifier(value, field):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}', value):
        raise VideoPipelineError('Invalid ' + field)
    return value


def _positive(value, field, *, zero=False):
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value) or (value < 0 if zero else value <= 0)):
        raise VideoPipelineError(field + ' must be finite and ' + ('nonnegative' if zero else 'positive'))


def _pin(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise VideoPipelineError('Each source requires a lowercase SHA256 pin')


def _relative_path(value):
    if (not isinstance(value, str) or not value or '\\' in value or '\x00' in value
            or Path(value).is_absolute() or ':' in value):
        raise VideoPipelineError('Source paths must be project-relative local files')


def _3d_only(value):
    normalized = str(value).lower().replace('-', '').replace('_', '')
    return any(name in normalized for name in ('hitem3d', 'seed3d', 'hyper3d'))


@dataclass(frozen=True)
class ReferenceBinding:
    character_id: str
    version_id: str
    asset_id: str
    path: str
    sha256: str
    role: str = 'identity'

    def __post_init__(self):
        for name in ('character_id', 'version_id', 'asset_id'):
            _identifier(getattr(self, name), name)
        _relative_path(self.path)
        _pin(self.sha256)
        if self.role not in ROLES:
            raise VideoPipelineError('Reference role must be identity, motion, or camera')


@dataclass(frozen=True)
class AudioCueBinding:
    cue_id: str
    asset_id: str
    path: str
    sha256: str
    start_seconds: float = 0
    end_seconds: float | None = None
    character_id: str | None = None

    def __post_init__(self):
        _identifier(self.cue_id, 'cue_id')
        _identifier(self.asset_id, 'audio asset_id')
        _relative_path(self.path)
        _pin(self.sha256)
        _positive(self.start_seconds, 'audio start_seconds', zero=True)
        if self.end_seconds is not None:
            _positive(self.end_seconds, 'audio end_seconds')
            if self.end_seconds <= self.start_seconds:
                raise VideoPipelineError('Audio out point must follow its in point')
        if self.character_id is not None:
            _identifier(self.character_id, 'audio character_id')


@dataclass(frozen=True)
class VideoRequest:
    shot_id: str
    prompt: str
    duration_seconds: float
    aspect_ratio: str
    resolution: str
    tier: str
    references: Sequence[ReferenceBinding]
    audio_cues: Sequence[AudioCueBinding] = ()

    def __post_init__(self):
        _identifier(self.shot_id, 'shot_id')
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise VideoPipelineError('A shot prompt is required alongside real image references')
        _positive(self.duration_seconds, 'duration_seconds')
        if not isinstance(self.aspect_ratio, str) or not re.fullmatch(r'[1-9][0-9]*:[1-9][0-9]*', self.aspect_ratio):
            raise VideoPipelineError('aspect_ratio must use a positive width:height ratio')
        if not isinstance(self.resolution, str) or not self.resolution.strip():
            raise VideoPipelineError('resolution must be an explicit provider-facing profile value')
        if self.tier not in TIERS:
            raise VideoPipelineError('tier must be draft, standard, or polish')
        if not isinstance(self.references, (list, tuple)) or not all(isinstance(r, ReferenceBinding) for r in self.references):
            raise VideoPipelineError('references must contain ReferenceBinding values')
        if not isinstance(self.audio_cues, (list, tuple)) or not all(isinstance(c, AudioCueBinding) for c in self.audio_cues):
            raise VideoPipelineError('audio_cues must contain AudioCueBinding values')
        object.__setattr__(self, 'references', tuple(self.references))
        object.__setattr__(self, 'audio_cues', tuple(self.audio_cues))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> 'VideoRequest':
        """Parse only the data contract; authorization/ready booleans are not fields."""
        if not isinstance(value, Mapping):
            raise VideoPipelineError('VideoRequest must be an object')
        try:
            data = dict(value)
            data['references'] = tuple(ReferenceBinding(**r) for r in data.get('references', []))
            data['audio_cues'] = tuple(AudioCueBinding(**r) for r in data.get('audio_cues', []))
            return cls(**data)
        except (TypeError, AttributeError) as exc:
            raise VideoPipelineError('VideoRequest contains missing or unsupported fields') from exc


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_image_reference: bool | None = None
    durations_seconds: Sequence[float] = ()
    aspect_ratios: Sequence[str] = ()
    resolutions: Sequence[str] = ()
    verification_status: str = 'unverified'
    kind: str = 'video'

    def __post_init__(self):
        if self.supports_image_reference is not None and type(self.supports_image_reference) is not bool:
            raise VideoPipelineError('supports_image_reference must be boolean or unknown')
        if self.verification_status not in {'verified', 'unverified', 'needs_verification'}:
            raise VideoPipelineError('Invalid capability verification_status')
        for value in self.durations_seconds:
            _positive(value, 'supported duration')
        for name in ('durations_seconds', 'aspect_ratios', 'resolutions'):
            values = getattr(self, name)
            if not isinstance(values, (list, tuple)):
                raise VideoPipelineError(name + ' must be a list or tuple')
            object.__setattr__(self, name, tuple(values))


class ProviderAdapter(ABC):
    """Injected code implementation; capabilities() must be pure local metadata.

    prepare() is an explicit local construction step. A future adapter must expose
    real file delivery evidence when it uploads/attaches references. Neither this
    interface nor a plan asserts that a provider has received a local path.
    """

    def __init__(self, provider_id: str):
        self.provider_id = _identifier(provider_id, 'adapter provider_id')

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        raise UnsupportedOperation('Provider capabilities have not been verified')

    def prepare(self, request: VideoRequest, verified_references: Sequence[Mapping[str, Any]] = ()) -> dict:
        raise UnsupportedOperation('Provider request preparation is not implemented')

    def submit(self, prepared: Mapping[str, Any]) -> dict:
        raise UnsupportedOperation('Provider submission is not implemented')

    def get(self, task_id: str) -> dict:
        raise UnsupportedOperation('Provider task querying is not implemented')


def _problem(code, detail, **extra):
    return {'code': code, 'detail': detail, **extra}


class VideoPipeline:
    def __init__(self, root: str | Path | None = None,
                 config: str | Path | Mapping[str, Any] = 'library/video-providers.json',
                 adapters: Mapping[str, ProviderAdapter] | None = None):
        self.root = Path(root or PROJECT_ROOT).resolve()
        if isinstance(config, Mapping):
            data = dict(config)
        else:
            path = Path(config)
            path = path if path.is_absolute() else self.root / path
            if not path.resolve().is_relative_to(self.root):
                raise VideoPipelineError('Provider config must stay within the project')
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                raise VideoPipelineError('Cannot read valid provider config JSON') from exc
        if data.get('schema_version') != 1 or not isinstance(data.get('tiers'), dict) or not isinstance(data.get('providers'), list):
            raise VideoPipelineError('Provider config requires schema_version 1, tiers and providers')
        self.providers = {}
        for provider in data['providers']:
            if not isinstance(provider, dict):
                raise VideoPipelineError('Each provider must be an object')
            provider_id = _identifier(provider.get('id'), 'provider ID')
            if provider_id in self.providers:
                raise VideoPipelineError('Duplicate provider ID')
            if provider.get('kind') != 'video' or _3d_only(provider_id):
                raise VideoPipelineError('3D reconstruction models must not be routed as video providers')
            constraints = provider.get('routing_constraints', {})
            if not isinstance(constraints, dict) or set(constraints) - {'resolutions'}:
                raise VideoPipelineError('Only explicit resolution routing constraints are currently supported')
            if not isinstance(constraints.get('resolutions', []), list):
                raise VideoPipelineError('routing_constraints.resolutions must be a list')
            self.providers[provider_id] = dict(provider)
        self.tiers = {}
        for tier in TIERS:
            values = data['tiers'].get(tier, [])
            if (not isinstance(values, list) or len(set(values)) != len(values)
                    or any(v not in self.providers for v in values)):
                raise VideoPipelineError('Each tier must list distinct known video provider IDs')
            self.tiers[tier] = tuple(values)
        self.adapters = dict(adapters or {})
        for provider_id, adapter in self.adapters.items():
            if (provider_id not in self.providers or not isinstance(adapter, ProviderAdapter)
                    or adapter.provider_id != provider_id or _3d_only(adapter.provider_id)):
                raise VideoPipelineError('Adapters must be actual matching video implementations keyed by provider ID')

    def _file(self, binding, media):
        candidate = self.root / binding.path
        path = candidate.resolve()
        if not path.is_relative_to(self.root):
            return None, _problem('source_path_outside_project', 'Source escapes the project', asset_id=binding.asset_id)
        for parent in [candidate] + list(candidate.parents):
            if parent == self.root:
                break
            if parent.is_symlink():
                return None, _problem('source_symlink_not_allowed', 'Source paths must not use symlinks', asset_id=binding.asset_id)
        if not path.is_file():
            return None, _problem('source_file_missing', 'Referenced source is not a local file', asset_id=binding.asset_id)
        h = hashlib.sha256()
        try:
            with path.open('rb') as stream:
                header = stream.read(32)
                h.update(header)
                for chunk in iter(lambda: stream.read(1024*1024), b''):
                    h.update(chunk)
        except OSError:
            return None, _problem('source_unreadable', 'Cannot read referenced source', asset_id=binding.asset_id)
        if h.hexdigest() != binding.sha256:
            return None, _problem('source_sha256_mismatch', 'Source bytes changed; rebind and review the actual file', asset_id=binding.asset_id)
        png = header.startswith(b'\x89PNG\r\n\x1a\n') and len(header) >= 24 and header[12:16] == b'IHDR'
        if png:
            png = all(v > 0 for v in struct.unpack('>II', header[16:24]))
        image = bool(png or header.startswith(b'\xff\xd8\xff') or (header.startswith(b'RIFF') and header[8:12] == b'WEBP')
                     or header.startswith((b'GIF87a', b'GIF89a', b'BM')))
        audio = bool(header.startswith((b'ID3', b'OggS', b'fLaC')) or (header.startswith(b'RIFF') and header[8:12] == b'WAVE')
                     or (len(header) > 1 and header[0] == 255 and header[1] & 0xE0 == 0xE0)
                     or (len(header) > 12 and header[4:8] == b'ftyp' and path.suffix.lower() in {'.m4a', '.aac'}))
        if (media == 'image' and not image) or (media == 'audio' and not audio):
            return None, _problem('source_media_type_mismatch', 'Source does not have a supported basic ' + media + ' header', asset_id=binding.asset_id)
        return {'path': path.relative_to(self.root).as_posix(), 'sha256': h.hexdigest(), 'bytes': path.stat().st_size,
                'verification_scope': 'local bytes and basic media header; no identity or audition certification'}, None

    def _candidate(self, provider_id, request):
        profile = self.providers[provider_id]
        result = {'provider_id': provider_id, 'display_name': profile.get('display_name', provider_id),
                  'planning_status': profile.get('planning_status', 'needs_adapter_and_model_resolution'),
                  'adapter_registered': provider_id in self.adapters, 'capabilities_source': 'configuration_only',
                  'status': 'needs_adapter', 'blockers': []}
        allowed = profile.get('routing_constraints', {}).get('resolutions', [])
        if allowed and request.resolution not in allowed:
            result['status'] = 'incompatible'
            result['blockers'].append(_problem('routing_resolution_constraint', 'Requested resolution is excluded by this routing profile', allowed_resolutions=list(allowed)))
            return result
        adapter = self.adapters.get(provider_id)
        if adapter is None:
            declared = profile.get('capabilities', {})
            # Config may describe possibilities, but cannot attest connection or verification.
            result['capabilities'] = {key: declared.get(key) for key in ('supports_image_reference', 'durations_seconds', 'aspect_ratios', 'resolutions')}
            result['blockers'].append(_problem('adapter_not_implemented', 'No code adapter is registered for this planning candidate'))
            result['blockers'].append(_problem('capabilities_need_verification', 'Configuration does not prove live image-reference support'))
            return result
        result['capabilities_source'] = 'registered_adapter_metadata'
        try:
            capabilities = adapter.capabilities()
        except Exception:
            result['status'] = 'needs_verification'
            result['blockers'].append(_problem('adapter_capabilities_unavailable', 'Adapter could not provide local capability metadata'))
            return result
        if not isinstance(capabilities, ProviderCapabilities) or capabilities.kind != 'video':
            result['status'] = 'incompatible'
            result['blockers'].append(_problem('adapter_modality_mismatch', 'Adapter does not describe a video capability contract'))
            return result
        result['capabilities'] = asdict(capabilities)
        unknown = (capabilities.verification_status != 'verified' or capabilities.supports_image_reference is None
                   or not capabilities.durations_seconds or not capabilities.aspect_ratios or not capabilities.resolutions)
        if unknown:
            result['status'] = 'needs_verification'
            result['blockers'].append(_problem('capabilities_need_verification', 'Image-reference, duration, aspect and resolution support require verified explicit values; empty arrays mean unknown'))
            return result
        mismatches = []
        if not capabilities.supports_image_reference:
            mismatches.append('image_reference')
        if request.duration_seconds not in capabilities.durations_seconds:
            mismatches.append('duration_seconds')
        if request.aspect_ratio not in capabilities.aspect_ratios:
            mismatches.append('aspect_ratio')
        if request.resolution not in capabilities.resolutions:
            mismatches.append('resolution')
        if mismatches:
            result['status'] = 'incompatible'
            result['blockers'].append(_problem('adapter_capability_mismatch', 'Verified adapter does not support this reference-bound request', fields=mismatches))
        else:
            result['status'] = 'eligible_for_explicit_prepare'
        return result

    def plan(self, request: VideoRequest) -> dict:
        if not isinstance(request, VideoRequest):
            raise VideoPipelineError('plan requires a VideoRequest instance')
        blockers, verified, audio = [], [], []
        cast = {}
        for reference in request.references:
            cast.setdefault(reference.character_id, []).append(reference)
        if not cast:
            blockers.append(_problem('identity_reference_required', 'A real character image is required; text-only fallback is prohibited'))
        for character, references in cast.items():
            if len({r.version_id for r in references}) != 1:
                blockers.append(_problem('mixed_character_versions', 'One character must use a single explicit version within a shot', character_id=character))
            if not any(r.role == 'identity' for r in references):
                blockers.append(_problem('identity_reference_required', 'Each character requires its own identity image', character_id=character))
        for reference in request.references:
            record, problem = self._file(reference, 'image')
            if problem:
                blockers.append(problem)
            else:
                verified.append({**asdict(reference), **record, 'attachment_status': 'not_uploaded'})
        for cue in request.audio_cues:
            if cue.character_id is not None and cue.character_id not in cast:
                blockers.append(_problem('audio_character_unbound', 'Character-specific cue has no matching cast reference', cue_id=cue.cue_id))
            record, problem = self._file(cue, 'audio')
            if problem:
                blockers.append(problem)
            else:
                audio.append({**asdict(cue), **record, 'stage': 'postproduction_source_cue',
                              'voice_synthesis_performed': False, 'audition_verified_by_pipeline': False})
        candidates = [self._candidate(provider_id, request) for provider_id in self.tiers[request.tier]]
        preferred = next((c['provider_id'] for c in candidates if c['status'] != 'incompatible'), None)
        selected = None if blockers else next((c['provider_id'] for c in candidates if c['status'] == 'eligible_for_explicit_prepare'), None)
        if not candidates:
            blockers.append(_problem('tier_has_no_candidates', 'No planning candidates are configured for this tier'))
        if selected is None:
            blockers.append(_problem('no_eligible_video_adapter', 'No verified compatible registered adapter is selected; inspect candidate reasons'))
        blockers.append(_problem('references_not_delivered', 'Verified local files have not been uploaded or attached to a video provider'))
        return {'schema_version': 1, 'shot_id': request.shot_id, 'tier': request.tier,
                'request': asdict(request), 'execution_state': 'offline_plan', 'execution_performed': False,
                'api_calls': 0, 'plan_cost': 0, 'submission_ready': False,
                'preferred_provider_id': preferred, 'selected_provider_id': selected,
                'planning_candidates': candidates, 'verified_references': verified,
                'audio_postproduction': audio, 'blockers': blockers,
                'automatic_fallback_performed': False,
                'reference_delivery_status': 'not_uploaded',
                'selection_scope': 'local routing eligibility only; account access, actual attachments and execution authorization are separate workflow facts'}
