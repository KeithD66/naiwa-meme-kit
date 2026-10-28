#!/usr/bin/env python3
"""Prepare reviewed image-bound Hyper3D requests offline; never submit or read keys.

prepare JOB writes only assets/private/hyper3d/requests/JOB/. --dry-run validates
and prints summaries without writing anything. Actual submission is a separate
scripts/ark-task.py operation: one POST, no automatic retry after uncertainty.
The Seed3D free allowance and usage ledger are never read or modified here.
"""
import sys
# Keep an offline dry-run from creating import caches in the project or venv.
sys.dont_write_bytecode = True

import argparse
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import struct
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODEL = 'hyper3d-gen2-260112'
OFFICIAL_SOURCE = 'https://docs.volcengine.com/docs/ark/shadoweye-create-3d-generation-task-api?lang=zh'
PER_SUCCESS_TOKENS = 30000
MAX_IMAGE_BYTES = 30_000_000  # Decimal MB is the conservative interpretation.
MAX_IMAGE_PIXELS = 4096 * 4096
LOCAL_MAX_BODY_BYTES = 64 * 1024 * 1024  # Project guard, not a stated official body limit.
SEED_SPEC = importlib.util.spec_from_file_location('seed3d_offline_helpers', Path(__file__).with_name('seed3d-batch.py'))
SEED = importlib.util.module_from_spec(SEED_SPEC)
SEED_SPEC.loader.exec_module(SEED)


class PreparationError(ValueError):
    pass


def local_path(root, value):
    if not isinstance(value, str) or not value or '\x00' in value or '\\' in value:
        raise PreparationError('Invalid project-local path')
    path = Path(value)
    path = path if path.is_absolute() else root / path
    if not SEED.within(path.resolve(), root):
        raise PreparationError('Path must stay inside the project')
    for parent in [path] + list(path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise PreparationError('Project paths must not use symlinks')
    return path.resolve()


def identifier(value, field):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,159}', value):
        raise PreparationError('Invalid ' + field)
    return value


def meaningful(value, field):
    if (not isinstance(value, str) or len(value.strip()) < 12
            or re.search(r'(?i)\b(todo|tbd|placeholder|pending|unknown)\b|待补|待确认|占位|未核验', value)):
        raise PreparationError(field + ' must contain actual review evidence, not a placeholder')
    return value.strip()


def reject_credentials(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in {'authorization', 'api_key', 'apikey', 'secret_key', 'access_key', 'bearer'}:
                raise PreparationError('Plan must not contain credentials')
            reject_credentials(item)
    elif isinstance(value, list):
        for item in value:
            reject_credentials(item)
    elif isinstance(value, str) and re.search(r'\bark-[A-Za-z0-9-]+|\bBearer\s+\S+', value, re.I):
        raise PreparationError('Plan must not contain credentials')


def parameter_flags(parameters):
    required = {'mesh_mode', 'material', 'quality_override', 'hd_texture', 'addons',
                'use_original_alpha', 'TAPose', 'fileformat'}
    if not isinstance(parameters, dict) or set(parameters) != required:
        raise PreparationError('Parameters must use the explicit supported Ark flag set')
    mode = parameters['mesh_mode']
    if mode not in {'Quad', 'Raw'}:
        raise PreparationError('mesh_mode must be Quad or Raw')
    if parameters['material'] not in {'PBR', 'Shaded', 'All', 'None'}:
        raise PreparationError('Invalid material')
    quality = parameters['quality_override']
    low, high = (1000, 200000) if mode == 'Quad' else (500, 1000000)
    if type(quality) is not int or not low <= quality <= high:
        raise PreparationError(f'{mode} quality_override must be an integer in [{low}, {high}]')
    for key in ('hd_texture', 'use_original_alpha', 'TAPose'):
        if type(parameters[key]) is not bool:
            raise PreparationError(key + ' must be a boolean')
    if parameters['addons'] not in (None, 'HighPack'):
        raise PreparationError('Only the documented HighPack addon or null is supported')
    if parameters['fileformat'] not in {'glb', 'obj', 'usdz', 'fbx', 'stl'}:
        raise PreparationError('Invalid official fileformat')
    order = ['mesh_mode', 'material', 'quality_override', 'hd_texture', 'addons',
             'use_original_alpha', 'TAPose', 'fileformat']
    return ' '.join('--' + key + ' ' + (str(parameters[key]).lower() if type(parameters[key]) is bool else str(parameters[key]))
                    for key in order if parameters[key] is not None)


def image_input(path):
    """Preserve supported files; losslessly re-encode static WebP as same-size RGBA PNG."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise PreparationError('Pillow is required; run with .venv-render/bin/python') from exc
    source = path.read_bytes()
    if len(source) > MAX_IMAGE_BYTES:
        raise PreparationError('Source image exceeds the conservative 30 MB file guard')
    try:
        with Image.open(io.BytesIO(source)) as image:
            width, height = image.size
            if width < 1 or height < 1 or width*height >= MAX_IMAGE_PIXELS:
                raise PreparationError('Official image pixel count must be strictly below 4096*4096')
            if getattr(image, 'n_frames', 1) != 1:
                raise PreparationError('Animated sources are not silently reduced to one pose')
            source_format = image.format
            if source_format not in {'PNG', 'JPEG', 'WEBP'}:
                raise PreparationError('Source must be PNG/JPEG or static WebP for lossless conversion')
            image.load()
            rgba = image.convert('RGBA')
            rgba_bytes = rgba.tobytes()
            pixel_hash = hashlib.sha256(struct.pack('>II', width, height) + rgba_bytes).hexdigest()
            if source_format == 'WEBP':
                stream = io.BytesIO()
                rgba.save(stream, format='PNG')
                submitted = stream.getvalue()
                with Image.open(io.BytesIO(submitted)) as check:
                    if check.size != image.size or check.convert('RGBA').tobytes() != rgba_bytes:
                        raise PreparationError('PNG conversion changed source dimensions or decoded RGBA pixels')
                mime, transform = 'png', 'format_conversion_only'
            else:
                submitted = source
                mime, transform = ('png' if source_format == 'PNG' else 'jpeg'), 'none'
    except PreparationError:
        raise
    except Exception as exc:
        raise PreparationError('Cannot decode source image safely') from exc
    if len(submitted) > MAX_IMAGE_BYTES:
        raise PreparationError('Submitted image exceeds the conservative 30 MB file guard')
    info = {'source_sha256': hashlib.sha256(source).hexdigest(),
            'submitted_sha256': hashlib.sha256(submitted).hexdigest(),
            'submitted_format': mime, 'source_format': source_format.lower(),
            'dimensions': [width, height], 'source_bytes': len(source), 'submitted_bytes': len(submitted),
            'rgba_pixel_sha256': pixel_hash, 'rgba_hash_basis': 'big-endian uint32 width,height followed by decoded RGBA bytes',
            'transform': transform, 'dimensions_unchanged': True, 'decoded_pixels_unchanged': True}
    if mime == 'png':
        info['submitted_png_sha256'] = info['submitted_sha256']
    return submitted, info


def validate_reference(root, reference, job, catalog, reviews):
    if reference.get('origin') != 'existing_network_media':
        raise PreparationError('Each reference must originate in existing network media')
    if reference.get('version_id') != job['source_version_id'] or reference.get('pose_id') != job['pose_id']:
        raise PreparationError('References must share the declared source version and pose')
    asset_id = reference.get('source_asset_id')
    asset = catalog.get(asset_id)
    if not asset or asset.get('kind') != 'image' or asset.get('availability') != 'local':
        raise PreparationError('Reference must resolve to a real local catalog image')
    tier = str(asset.get('identity_tier', '')).lower()
    tags = ' '.join(str(v).lower() for v in asset.get('tags', []))
    if (asset.get('derived_from_asset_id') or any(t in tier + ' ' + tags for t in
            ('reconstruction', 'generated', '3d_render', 'model_render', 'reference_mismatch'))):
        raise PreparationError('Generated/reconstructed/rendered derivatives cannot masquerade as existing network references')
    if job['character_id'] not in asset.get('character_ids', []):
        raise PreparationError('Catalog character does not match the requested character')
    bundle = asset.get('source_identity_bundle_id') or asset.get('identity_bundle_id')
    if bundle != job['source_version_id']:
        raise PreparationError('Catalog identity version does not match the declared source version')
    if asset.get('pose_id') and asset['pose_id'] != job['pose_id']:
        raise PreparationError('Catalog pose contradicts the declared pose')
    path = local_path(root, reference.get('path'))
    catalog_path = local_path(root, asset.get('local_path'))
    if path != catalog_path or not path.is_file():
        raise PreparationError('Reference path must match the catalog source file')
    expected = reference.get('sha256')
    if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise PreparationError('Reference requires a SHA256 pin')
    if SEED.sha256(path) != expected or asset.get('sha256') != expected:
        raise PreparationError('Reference/catalog SHA256 mismatch; reindex and re-review changed files')
    visual = reference.get('visual_review', {})
    if visual.get('status') != 'visual_checked' or visual.get('sha256') != expected:
        raise PreparationError('Plan reference requires a current hash-bound visual review')
    meaningful(visual.get('note'), 'Plan visual review')
    evidence = asset.get('review_evidence', {})
    if (asset.get('visual_review') != 'visual_checked' or asset.get('review_status') != 'current_hash'
            or evidence.get('sha256') != expected or evidence.get('visual', {}).get('result') != 'visual_checked'):
        raise PreparationError('Catalog lacks a current hash-bound visual review')
    meaningful(evidence.get('visual', {}).get('note'), 'Catalog visual review')
    # The current ledger is authoritative. A review can be rejected or removed
    # after catalog indexing; cached positive catalog fields cannot revive it.
    current = reviews.get((asset_id, expected), {}).get('visual', {})
    if current.get('result') != 'visual_checked':
        raise PreparationError('Current review ledger lacks a matching positive visual review')
    meaningful(current.get('note'), 'Current ledger visual review')
    if current.get('identity_bundle_id') and current['identity_bundle_id'] != job['source_version_id']:
        raise PreparationError('Current ledger visual review contradicts the source version')
    data, info = image_input(path)
    info.update({'source_asset_id': asset_id, 'source_path': path.relative_to(root).as_posix(),
                 'version_id': reference['version_id'], 'pose_id': reference['pose_id'],
                 'view_label': reference.get('view', 'unspecified'),
                 'origin': 'existing_network_media', 'catalog_visual_review': 'current_hash',
                 'catalog_license_status': asset.get('license_status', 'rights_unresolved')})
    return data, info


def load_prepared(root, plan_path, selected_jobs=None):
    root = Path(root).resolve()
    plan_file = local_path(root, str(plan_path))
    try:
        plan = json.loads(plan_file.read_text())
        cat_data = json.loads(local_path(root, 'library/catalog.json').read_text())
        review_data = json.loads(local_path(root, 'library/reviews.json').read_text())
    except (OSError, ValueError) as exc:
        raise PreparationError('Cannot read valid plan, catalog, and current review ledger JSON') from exc
    if not isinstance(review_data, dict) or not isinstance(review_data.get('reviews'), list):
        raise PreparationError('Current review ledger must contain a valid reviews list')
    reviews = {}
    for entry in review_data['reviews']:
        if (not isinstance(entry, dict) or not isinstance(entry.get('asset_id'), str)
                or not entry['asset_id'] or not isinstance(entry.get('sha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', entry['sha256'])):
            raise PreparationError('Current review ledger has an invalid asset/hash record')
        visual = entry.get('visual')
        if visual is not None and (not isinstance(visual, dict)
                                   or visual.get('result') not in {'visual_checked', 'rejected', 'not_reviewed'}):
            raise PreparationError('Current review ledger has an invalid visual result')
        reviews[(entry['asset_id'], entry['sha256'])] = entry
    reject_credentials(plan)
    if plan.get('schema_version') != 1 or plan.get('model') != MODEL:
        raise PreparationError('Plan must use schema 1 and the fixed Hyper3D model')
    if plan.get('execution_stage') != 'prepared_not_submitted':
        raise PreparationError('This tool only prepares unsubmitted requests')
    budget = plan.get('budget', {})
    if (budget.get('per_success_tokens') != PER_SUCCESS_TOKENS or type(budget.get('batch_limit_tokens')) is not int
            or budget['batch_limit_tokens'] < PER_SUCCESS_TOKENS or type(budget.get('max_submissions')) is not int
            or budget['max_submissions'] < 1 or budget['max_submissions']*PER_SUCCESS_TOKENS > budget['batch_limit_tokens']):
        raise PreparationError('Plan must contain an explicit coherent independent Hyper3D token/call budget')
    catalog = {}
    for asset in cat_data.get('assets', []):
        if asset.get('id') in catalog:
            raise PreparationError('Catalog contains duplicate asset IDs')
        catalog[asset.get('id')] = asset
    jobs = {}
    for job in plan.get('jobs', []):
        job_id = identifier(job.get('id'), 'job ID')
        if job_id in jobs:
            raise PreparationError('Duplicate planned job ID')
        jobs[job_id] = job
    if not jobs:
        raise PreparationError('Plan requires at least one image-bound job')
    wanted = list(jobs) if selected_jobs is None else list(selected_jobs)
    if not wanted or len(set(wanted)) != len(wanted) or any(j not in jobs for j in wanted):
        raise PreparationError('Unknown or duplicate requested job ID')
    result = []
    for job_id in wanted:
        job = jobs[job_id]
        for key in ('character_id', 'version_id', 'source_version_id', 'pose_id'):
            identifier(job.get(key), key)
        if job['version_id'] == job['source_version_id']:
            raise PreparationError('Reconstruction must use a separate candidate version ID')
        references = job.get('references')
        if not isinstance(references, list) or not 1 <= len(references) <= 5:
            raise PreparationError('Image-to-3D requires 1 to 5 actual references; text-only is prohibited')
        if len(references) > 1:
            meaningful(job.get('multiview_evidence'), 'Multi-input source/version/pose evidence')
        prompt = job.get('prompt', '')
        if (not isinstance(prompt, str) or len(prompt) > 400 or '--' in prompt
                or any(ord(c) < 32 or ord(c) > 126 for c in prompt)):
            raise PreparationError('Prompt must be English ASCII, at most 400 characters, without flags')
        seed = job.get('seed')
        if type(seed) is not int or not 0 <= seed <= 65535:
            raise PreparationError('seed must be a top-level integer in [0, 65535]')
        flags = parameter_flags(job.get('parameters'))
        text = (prompt + ' ' + flags).strip()
        payload = {'model': MODEL, 'seed': seed, 'content': [{'type': 'text', 'text': text}]}
        submitted, information, source_hashes, pixel_hashes = [], [], set(), set()
        for i, reference in enumerate(references):
            data, info = validate_reference(root, reference, job, catalog, reviews)
            if info['source_sha256'] in source_hashes or info['rgba_pixel_sha256'] in pixel_hashes:
                raise PreparationError('Duplicate source image or decoded pixels cannot count as multiple references')
            source_hashes.add(info['source_sha256'])
            pixel_hashes.add(info['rgba_pixel_sha256'])
            filename = f'inputs/reference-{i:02d}.' + ('jpg' if info['submitted_format'] == 'jpeg' else 'png')
            info['submitted_file'] = filename
            information.append(info)
            submitted.append((filename, data))
            payload['content'].append({'type': 'image_url', 'image_url': {'url':
                'data:image/' + info['submitted_format'] + ';base64,' + base64.b64encode(data).decode('ascii')}})
        # Match ark-task.py's body serialization, not merely the pretty request file.
        encoded = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        if len(encoded) > LOCAL_MAX_BODY_BYTES:
            raise PreparationError('Request exceeds the project-local 64 MiB guard; this is not an official body limit')
        directory = local_path(root, 'assets/private/hyper3d/requests/' + job_id)
        summary = {'schema_version': 1, 'model': MODEL, 'job_id': job_id,
                   'character_id': job['character_id'], 'version_id': job['version_id'],
                   'source_version_id': job['source_version_id'], 'pose_id': job['pose_id'],
                   'stage': 'prepared_not_submitted', 'api_calls': 0, 'credential_read': False,
                   'request_path': (directory / 'request.json').relative_to(root).as_posix(),
                   'request_sha256': hashlib.sha256(encoded).hexdigest(),
                   'request_hash_basis': 'ark-task.py json.dumps(payload, ensure_ascii=False) UTF-8 body',
                   'request_bytes': len(encoded), 'local_max_request_bytes': LOCAL_MAX_BODY_BYTES,
                   'local_body_limit_is_official': False, 'prompt': prompt, 'parameter_text': flags,
                   'seed': seed, 'same_seed_guarantees_identical_output': False,
                   'parameters': dict(job['parameters']), 'references': information,
                   'reference_count': len(information),
                   'multi_input': {'used': len(information) > 1, 'ark_camera_role_semantics_verified': False,
                                   'evidence_present': len(information) > 1 and bool(job.get('multiview_evidence'))},
                   'rest_pose_reconstruction_requested': job['parameters']['TAPose'],
                   'hidden_geometry_would_be_inferred': True,
                   'rigging_created': False, 'default_identity': False,
                   'native_quad_topology_must_be_verified': job['parameters']['mesh_mode'] == 'Quad',
                   'downstream_format_requires_conversion': job['parameters']['fileformat'] not in {'glb', 'obj'},
                   'license_status': job.get('license_status', 'rights_unresolved'),
                   'usage_scope': 'local_reference_only', 'publishing_allowed': False,
                   'budget': {'per_success_tokens': PER_SUCCESS_TOKENS,
                              'batch_limit_tokens': budget['batch_limit_tokens'], 'max_submissions': budget['max_submissions'],
                              'free_balance_verified': False, 'declared_free_tokens': budget.get('declared_free_tokens'),
                              'payg_price_cny_per_success': budget.get('payg_price_cny_per_success'),
                              'seed3d_allowance_applies': False, 'actual_usage_tokens': None},
                   'official_source_url': OFFICIAL_SOURCE,
                   'submission_policy': 'Separate explicit ark-task.py operation; one POST, no automatic retry after timeout; do not infer account free balance.'}
        result.append((directory, payload, summary, submitted))
    return result


def prepare(root=ROOT, plan_path='library/hyper3d-plan.json', selected_jobs=None, dry_run=False):
    root = Path(root).resolve()
    prepared = load_prepared(root, plan_path, selected_jobs)
    if not dry_run:
        for directory, payload, summary, submitted in prepared:
            # Re-check fixed output paths, including symlink parents, before mutation.
            directory = local_path(root, str(directory))
            if directory.exists():
                request_file = local_path(root, str(directory / 'request.json'))
                summary_file = local_path(root, str(directory / 'summary.json'))
                try:
                    existing = json.loads(summary_file.read_text())
                    same = (existing == summary
                            and json.loads(request_file.read_text()) == payload
                            and all(local_path(root, str(directory / name)).is_file()
                                    and SEED.sha256(directory / name) == hashlib.sha256(data).hexdigest()
                                    for name, data in submitted))
                except (OSError, ValueError):
                    same = False
                if not same:
                    raise PreparationError('Existing request differs or has changed; preserve it and use a new job version')
                continue
            directory.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix='.hyper3d-prepare-', dir=directory.parent))
            try:
                for name, data in submitted:
                    path = stage / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    path.chmod(0o600)
                SEED.atomic_json(stage / 'request.json', payload)
                SEED.atomic_json(stage / 'summary.json', summary)
                stage.rename(directory)
            except BaseException:
                shutil.rmtree(stage, ignore_errors=True)
                raise
    return [summary for _, _, summary, _ in prepared]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', default='library/hyper3d-plan.json')
    parser.add_argument('--dry-run', action='store_true', help='Validate with no filesystem writes')
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('prepare')
    command.add_argument('job', nargs='?')
    command.add_argument('--all', action='store_true')
    command.add_argument('--dry-run', action='store_true', default=argparse.SUPPRESS)
    args = parser.parse_args()
    if bool(args.job) == args.all:
        parser.error('Choose one job ID or --all')
    try:
        summaries = prepare(plan_path=args.plan, selected_jobs=[args.job] if args.job else None, dry_run=args.dry_run)
    except (PreparationError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, 'Preparation blocked: ' + str(exc) + '\n')
    print(json.dumps({'dry_run': args.dry_run, 'api_calls': 0, 'summaries': summaries}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
