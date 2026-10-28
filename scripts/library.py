#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Index, search and hand off existing meme media. Never generates media."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import html
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'library/catalog.json'
MEDIA = {'.jpg': 'image', '.jpeg': 'image', '.png': 'image', '.webp': 'image', '.gif': 'animation', '.mp4': 'video', '.webm': 'video', '.mp3': 'audio', '.wav': 'audio', '.m4a': 'audio', '.ogg': 'audio'}
VISUAL_KINDS = {'image', 'sprite', 'animation', 'video'}
VISUAL_RESULTS = {'visual_checked', 'rejected', 'not_reviewed'}
AUDIO_RESULTS = {'auditioned_match', 'rejected', 'not_auditioned'}
# These are annotations, not a way to certify a turnaround or license a model.
REVIEW_ROLES = {'identity', 'neutral', 'motion', 'laugh', 'existing_clip', 'sprite',
                'candidate', 'front', 'side', 'back', 'eye_direction_preview', 'turnaround_rejected'}
MULTIVIEW_ROLES = {'verified_turnaround', 'licensed_model_render'}


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def local_path(relative):
    path = ROOT / relative
    if ROOT.resolve() not in path.resolve().parents:
        raise ValueError('Path outside project: ' + str(relative))
    return path


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def probe(path):
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_name,width,height,sample_rate,channels', '-of', 'json', str(path)], capture_output=True, text=True)
        return json.loads(result.stdout) if result.returncode == 0 else {'probe_error': result.stderr.strip()}
    except FileNotFoundError:
        return {'probe_status': 'ffprobe_not_installed'}


def normalize_hub_url(url):
    match = re.fullmatch(r'([A-Za-z0-9-]+)/([0-9a-fA-F]{40})/(.+)', url)
    if match:
        return 'https://raw.githubusercontent.com/' + match[1] + '/NaiLoong/' + match[2] + '/' + urllib.parse.quote(match[3], safe='/')
    return url


def review_ledger():
    data = read_json(local_path('library/reviews.json'), {'schema_version': 1, 'reviews': []})
    if not isinstance(data, dict) or not isinstance(data.get('reviews'), list):
        raise ValueError('Invalid library/reviews.json: expected a reviews list')
    if any(not isinstance(entry, dict) or not entry.get('asset_id') or not entry.get('sha256') for entry in data['reviews']):
        raise ValueError('Invalid library/reviews.json: each review needs asset_id and sha256')
    return data


def apply_reviews(asset, records, verify_file=False):
    """Only a recorded review of these exact bytes can supply a positive result."""
    asset = deepcopy(asset)
    for field in ('identity_bundle_id', 'reference_role'):
        baseline = 'source_' + field
        asset.setdefault(baseline, asset.get(field))
        if asset[baseline] is None:
            asset.pop(field, None)
        else:
            asset[field] = asset[baseline]
    asset['visual_review'] = 'rejected_as_default' if asset.get('identity_tier') == 'reference_mismatch' else 'not_reviewed'
    asset['audio_review'] = 'not_auditioned' if asset.get('kind') in {'audio', 'video'} else 'not_applicable'
    asset.pop('review_evidence', None)
    matching = [entry for entry in records if entry.get('asset_id') == asset['id']]
    current = [entry for entry in matching if asset.get('sha256') and entry.get('sha256') == asset['sha256']]
    if current and verify_file and asset.get('availability') == 'local' and asset.get('local_path'):
        path = local_path(asset['local_path'])
        if not path.is_file() or file_sha(path) != asset['sha256']:
            current = []
    asset['review_status'] = 'stale_hash' if matching and not current else 'not_recorded'
    if asset.get('availability') != 'local' or not current:
        return asset
    entry = current[-1]
    evidence = {'asset_id': asset['id'], 'sha256': entry['sha256']}
    for category, field, allowed in [('visual', 'visual_review', VISUAL_RESULTS), ('audio', 'audio_review', AUDIO_RESULTS)]:
        review = entry.get(category)
        if not isinstance(review, dict) or review.get('result') not in allowed or not str(review.get('note', '')).strip():
            continue
        if category == 'visual' and asset.get('kind') not in VISUAL_KINDS:
            continue
        if category == 'audio' and asset.get('kind') not in {'audio', 'video'}:
            continue
        asset[field] = review['result']
        evidence[category] = deepcopy(review)
        if category == 'visual':
            if review.get('identity_bundle_id'):
                # A review may annotate a version, but cannot replace a source's certified bundle.
                if not asset.get('identity_bundle_id') or asset['identity_bundle_id'] == review['identity_bundle_id']:
                    asset['identity_bundle_id'] = review['identity_bundle_id']
            role = review.get('reference_role')
            if role in REVIEW_ROLES and asset.get('reference_role') not in MULTIVIEW_ROLES:
                asset['reference_role'] = role
    if len(evidence) > 2:
        asset['review_status'] = 'current_hash'
        asset['review_evidence'] = evidence
    return asset


def resolve_character(value):
    matches = [item['id'] for item in read_json(ROOT / 'library/characters.json', {}).get('characters', [])
               if value in [item['id'], item['name']] + item.get('aliases', [])]
    if len(matches) > 1:
        raise ValueError('Ambiguous character: ' + value + '; choose ' + ', '.join(matches))
    if not matches:
        raise ValueError('Unknown character: ' + value)
    return matches[0]


def index_assets():
    assets, repos = [], {}
    reviews = review_ledger()['reviews']
    for repo in sorted((ROOT / 'assets/repos').glob('*')):
        if (repo / '.git').is_dir():
            repos[repo.name] = {'origin': git(repo, 'config', '--get', 'remote.origin.url'), 'commit': git(repo, 'rev-parse', 'HEAD')}

    def add(asset):
        asset.setdefault('tags', [])
        asset.setdefault('character_ids', [])
        asset.setdefault('usage_scope', 'local_reference_only')
        asset.setdefault('identity_tier', 'unconfirmed')
        if asset.get('local_path'):
            path = local_path(asset['local_path'])
            asset['availability'] = 'local' if path.is_file() else 'missing'
            if path.is_file():
                asset['bytes'] = path.stat().st_size
                asset['sha256'] = file_sha(path)
                if asset.get('kind') in {'audio', 'video'}:
                    asset['media'] = probe(path)
        else:
            asset['availability'] = 'remote_index'
        assets.append(apply_reviews(asset, reviews))

    original = repos.get('naiwa-pet', {}).get('commit')
    for number, title, role in [(0, '奶蛙现成原序列·闭嘴参照', 'neutral'), (120, '奶蛙现成原序列·中段动作', 'motion'), (200, '奶蛙现成原序列·捧腹笑参照', 'laugh'), (437, '奶蛙现成原序列·末帧', 'motion')]:
        relative = 'assets/repos/naiwa-pet/public/pets/naiwa/frames/frame_%04d.webp' % number
        add({'id': 'naiwa-frame-%04d' % number, 'title': title, 'kind': 'image', 'character_ids': ['naiwa'], 'local_path': relative, 'source_url': 'https://github.com/LynnShaw/naiwa-pet', 'source_commit': original, 'reference_role': role, 'identity_bundle_id': 'naiwa-pet-network-3d', 'identity_tier': 'network_3d_candidate', 'license_status': 'no_license_local_only', 'tags': ['existing_frame', 'same_sequence', role], 'notes': '现成网络版候选；非用户认证原始作者来源，也不是三视图。'})
    for asset_id, title, kind, relative, role in [
        ('naiwa-original-video', '奶蛙现成大笑原片', 'video', 'assets/repos/naiwa-pet/naiwa.mp4', 'existing_clip'),
        ('naiwa-original-audio', '奶蛙原片提取音轨', 'audio', 'assets/repos/naiwa-pet/public/pets/naiwa/audio.m4a', 'laugh'),
        ('naiwa-codex-sprite', '奶蛙桌宠精灵表', 'sprite', 'assets/repos/codex-pet-naiwa/naifrog/spritesheet.webp', 'sprite'),
        ('naiwa-look-directions', '奶蛙注视方向预览', 'image', 'assets/repos/codex-pet-naiwa/naifrog/previews/look-directions.png', 'eye_direction_preview')]:
        add({'id': asset_id, 'title': title, 'kind': kind, 'character_ids': ['naiwa'], 'local_path': relative, 'source_url': 'https://github.com/' + ('LynnShaw/naiwa-pet' if 'original' in asset_id else 'timerring/codex-pet-naiwa'), 'reference_role': role, 'identity_tier': 'network_3d_candidate', 'license_status': 'third_party_rights_unresolved', 'notes': '包装仓库MIT不覆盖其Credits第三方媒体；本地参考。'})
    hub = ROOT / 'assets/repos/NaiLoong'
    for char in ['naiwa', 'naidan']:
        for item in read_json(hub / 'data' / char / 'voice.json', []):
            stem = Path(item['src']).stem
            add({'id': 'nai-hub-' + stem, 'title': item['text'], 'kind': 'audio', 'character_ids': [char], 'local_path': str(Path('assets/repos/NaiLoong') / item['src']), 'source_url': 'https://github.com/lin-alg/NaiLoong', 'source_commit': repos.get('NaiLoong', {}).get('commit'), 'cue_ids': ['naidan.andi'] if stem == 'andi' else [], 'license_status': 'recording_rights_unresolved', 'tags': [stem, char], 'notes': '归属来自上游voice.json；目录文字不是试听结论。'})
    # Preserve indexed remote images as remote entries; never claim catalog URLs are downloaded.
    for char in ['naiwa', 'naidan', 'others']:
        for section in ['static', 'animated']:
            for item in read_json(hub / 'data' / char / (section + '.json'), []):
                url = item.get('url') or item.get('src') or item.get('image')
                if not isinstance(url, str):
                    continue
                url = normalize_hub_url(url)
                title = item.get('name') or item.get('title') or item.get('alt') or Path(urllib.parse.urlsplit(url).path).name
                key = hashlib.sha1((char + section + url).encode()).hexdigest()[:12]
                add({'id': 'nai-hub-image-' + key, 'title': str(title), 'kind': 'animation' if section == 'animated' else 'image', 'character_ids': [char] if char != 'others' else [], 'source_url': url, 'download_url': url, 'license_status': 'community_media_rights_unresolved', 'tags': [section, char] + [str(tag) for tag in item.get('tags', [])], 'notes': '只有远程目录记录；没有自动下载。others分组未默认归给奶蛙。'})
    wallpaper = ROOT / 'assets/repos/wallpaper'
    listing = read_json(wallpaper / 'assets.json', {})
    items = listing.get('items', [])
    if not items:
        items = read_json(ROOT / 'assets/repos/NaiLong-Universe/docs/data/assets.json', {}).get('items', [])
    for item in items:
        name = item.get('file') or item.get('path') or item.get('id')
        if not name:
            continue
        category = item.get('category', 'unknown')
        rel = str(Path('assets/repos/wallpaper') / name)
        sidecar = Path(str(wallpaper / name) + '.txt')
        notes = sidecar.read_text(encoding='utf-8', errors='replace') if sidecar.is_file() else ''
        kind = MEDIA.get(Path(name).suffix.lower(), item.get('type', 'unknown'))
        add({'id': 'wallpaper-' + hashlib.sha1(name.encode()).hexdigest()[:12], 'title': item.get('title', name), 'kind': kind, 'character_ids': ['naiwa'], 'local_path': rel if (wallpaper / name).is_file() else None, 'source_url': 'https://github.com/Nailong-Studio/wallpaper/blob/' + (repos.get('wallpaper', {}).get('commit') or 'main') + '/' + urllib.parse.quote(name, safe='/'), 'source_commit': repos.get('wallpaper', {}).get('commit'), 'download_url': item.get('raw'), 'category': category, 'tags': [category, item.get('categoryName', '')], 'identity_tier': 'art_variant' if category in {'classic', 'laugh-gallery', 'art', 'hd', '4k', 'frames'} else 'network_3d_candidate', 'reference_role': 'candidate', 'license_status': 'per_asset_notice_required', 'notice_path': str(sidecar.relative_to(ROOT)) if sidecar.is_file() else None, 'source_notice': notes, 'notes': '逐件看同名说明和SOURCES；标题/类别不代表角色已锁定或作者权利已核实。'})
    for item in read_json(ROOT / 'library/downloads.json', {}).get('assets', []):
        asset = {'id': item['id'], 'title': item.get('title', item['id']), 'kind': item.get('kind', MEDIA.get(Path(item['path']).suffix.lower(), 'metadata')), 'character_ids': item.get('character_ids', []), 'local_path': str(Path('assets/private/curated') / item['path']), 'source_url': item.get('source_url', item['url']), 'download_url': item['url'], 'git_blob_sha1': item.get('git_blob_sha1'), 'license_status': item.get('license_status', 'unresolved'), 'tags': item.get('tags', []), 'cue_ids': item.get('cue_ids', []), 'identity_tier': item.get('identity_tier', 'unconfirmed'), 'notes': item.get('notes', '')}
        # Multi-angle certification is source evidence, never an ordinary review flag.
        for field in ('reference_role', 'identity_bundle_id', 'view_coverage', 'multiview_evidence',
                      'model_license_status', 'model_license_evidence'):
            if field in item:
                asset[field] = deepcopy(item[field])
        add(asset)
    for image in sorted((ROOT / 'assets/private/references').glob('neta-*.webp')):
        add({'id': image.stem, 'title': 'Neta三视图候选（正侧标签有误）', 'kind': 'image', 'character_ids': ['naiwa'], 'local_path': str(image.relative_to(ROOT)), 'source_url': 'https://neta.art/app/milk-frog-wiki', 'reference_role': 'turnaround_rejected', 'identity_tier': 'reference_mismatch', 'license_status': 'unresolved', 'notes': '已看图：正/侧标签对调，眼色与嘴形偏离标准；禁止直接锁定为生产基准。'})
    # Research-only candidates remain searchable without pretending their media was downloaded.
    aliases = dict(read_json(ROOT / 'library/audio-cues.json', {}).get('asset_aliases', {}))
    lookup = {item['id']: item for item in assets}
    by_path = {str(local_path(item['local_path']).resolve()): item for item in assets if item.get('local_path')}
    by_blob = {item['git_blob_sha1']: item for item in assets if item.get('git_blob_sha1')}
    for source in read_json(ROOT / 'research/audio-resources.json', {}).get('sources', []):
        for item in source.get('assets', []):
            research_id = item['id']
            asset_id = resolve_asset_id(research_id, lookup, aliases)
            candidate_path = item.get('local_path')
            path = local_path(candidate_path) if candidate_path else None
            existing = lookup.get(asset_id)
            if existing is None and path is not None:
                existing = by_path.get(str(path.resolve()))
            if existing is None and item.get('git_blob_sha1'):
                existing = by_blob.get(item['git_blob_sha1'])
            if existing is None:
                asset = {'id': asset_id, 'title': item.get('label', research_id), 'kind': item.get('kind', 'audio'),
                         'character_ids': item.get('character_ids', []),
                         'local_path': candidate_path if path is not None and path.is_file() else None,
                         'candidate_local_path': candidate_path, 'source_url': item.get('download_url') or source.get('url', ''),
                         'download_url': item.get('download_url'), 'source_commit': source.get('commit'),
                         'git_blob_sha1': item.get('git_blob_sha1'), 'expected_bytes': item.get('bytes'),
                         'license_status': item.get('license_status', source.get('license_status', 'unresolved')),
                         'fetch_policy': item.get('fetch_policy', 'manual_rights_review'),
                         'tags': ['research_audio_candidate'], 'notes': source.get('notes', '')}
                add(asset)
                existing = assets[-1]
                lookup[asset_id] = existing
                if existing.get('local_path'):
                    by_path[str(local_path(existing['local_path']).resolve())] = existing
                if existing.get('git_blob_sha1'):
                    by_blob[existing['git_blob_sha1']] = existing
            if research_id != existing['id']:
                aliases[research_id] = existing['id']
            if asset_id != existing['id']:
                aliases[asset_id] = existing['id']
            existing.setdefault('research_asset_ids', [])
            if research_id not in existing['research_asset_ids']:
                existing['research_asset_ids'].append(research_id)
            existing.setdefault('fetch_policy', item.get('fetch_policy', 'manual_rights_review'))
            for field in ('candidate_character_ids', 'forbid_default_for', 'role_assignment'):
                if field in item:
                    existing.setdefault(field, deepcopy(item[field]))
    # Local API reconstructions remain separate from the indexed network originals.
    # Missing derivative files are optional local outputs, never auto-regenerated.
    for manifest in ['derived-assets.json', 'seed3d-assets.json', 'seed3d-local-variants.json']:
        for item in read_json(ROOT / 'library' / manifest, {}).get('assets', []):
            add(dict(item))
    ids = [item['id'] for item in assets]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate asset IDs in catalog')
    result = {'schema_version': 2, 'basis': '本地仓库与固定版本清单；数量不是全网资源或授权完整性声明。', 'repositories': repos, 'asset_aliases': aliases, 'summary': {'total': len(assets), 'availability': dict(Counter(item['availability'] for item in assets)), 'kind': dict(Counter(item['kind'] for item in assets))}, 'assets': assets}
    dump(CATALOG, result)
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))


def catalog():
    if not CATALOG.is_file():
        raise ValueError('Run python3 scripts/library.py index first')
    data = read_json(CATALOG)
    records = review_ledger()['reviews']
    data['assets'] = [apply_reviews(item, records, verify_file=True) for item in data['assets']]
    return data


def review_asset(args):
    item = next((item for item in catalog()['assets'] if item['id'] == args.asset_id), None)
    if item is None:
        raise ValueError('Unknown asset ID: ' + args.asset_id)
    if not args.visual and not args.audio:
        raise ValueError('Specify --visual and/or --audio; metadata is not a review')
    if not args.note.strip():
        raise ValueError('Review --note must describe the actual visual/audio check')
    if args.visual and (args.visual not in VISUAL_RESULTS or item['kind'] not in VISUAL_KINDS):
        raise ValueError('Invalid visual review for: ' + args.asset_id)
    if args.audio and (args.audio not in AUDIO_RESULTS or item['kind'] not in {'audio', 'video'}):
        raise ValueError('Invalid audio review for: ' + args.asset_id)
    if (args.identity_bundle_id or args.reference_role) and not args.visual:
        raise ValueError('Identity bundle/reference role require --visual')
    if args.reference_role and args.reference_role not in REVIEW_ROLES:
        raise ValueError('Reference role cannot certify a turnaround or model license; record source evidence separately')
    if args.identity_bundle_id is not None and not args.identity_bundle_id.strip():
        raise ValueError('Identity bundle ID must not be empty')
    if (args.identity_bundle_id and item.get('source_reference_role') in MULTIVIEW_ROLES
            and item.get('source_identity_bundle_id') != args.identity_bundle_id):
        raise ValueError('Review cannot replace the source-certified identity bundle')
    if not item.get('local_path') or item.get('availability') != 'local':
        raise ValueError('Review requires a local file: ' + args.asset_id)
    path = local_path(item['local_path'])
    if not path.is_file():
        raise ValueError('Review requires a local file: ' + args.asset_id)
    sha256 = file_sha(path)
    if sha256 != item.get('sha256'):
        raise ValueError('Asset changed; re-index before recording its review: ' + args.asset_id)
    data = review_ledger()
    entry = next((entry for entry in data['reviews'] if entry.get('asset_id') == args.asset_id
                  and entry.get('sha256') == sha256), None)
    if entry is None:
        entry = {'asset_id': args.asset_id, 'sha256': sha256}
        data['reviews'].append(entry)
    for category in ('visual', 'audio'):
        result = getattr(args, category)
        if result:
            record = {'result': result, 'note': args.note.strip(),
                      'reviewed_at': datetime.now(timezone.utc).isoformat()}
            if category == 'visual':
                if args.identity_bundle_id:
                    record['identity_bundle_id'] = args.identity_bundle_id
                if args.reference_role:
                    record['reference_role'] = args.reference_role
            entry[category] = record
    dump(local_path('library/reviews.json'), data)
    print(json.dumps({'asset_id': args.asset_id, 'sha256': sha256, 'review': entry,
                      'note': '仅记录该文件的实际审核；不修改角色归属、许可或生成/发布授权。'}, ensure_ascii=False, indent=2))


def selected(args):
    result = []
    character_id = resolve_character(args.character) if getattr(args, 'character', None) else None
    for item in catalog()['assets']:
        if character_id and character_id not in item['character_ids']:
            continue
        if getattr(args, 'kind', None) and args.kind != item['kind']:
            continue
        if getattr(args, 'local', False) and item['availability'] != 'local':
            continue
        query = getattr(args, 'query', '').casefold()
        if query and query not in json.dumps(item, ensure_ascii=False).casefold():
            continue
        result.append(item)
    return result


def search(args):
    items = selected(args)[:args.limit]
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        for item in items:
            print('%s | %s | %s | %s' % (item['id'], item['availability'], item['title'], item.get('local_path') or item['source_url']))
        print('%d shown' % len(items))


def resolve_asset_id(value, lookup, aliases):
    seen = set()
    while value in aliases:
        if aliases[value] == value:
            break
        if value in seen:
            raise ValueError('Asset alias cycle: ' + value)
        seen.add(value)
        value = aliases[value]
    return value


def recipe_cue_ids(value):
    result = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {'cue_ids', 'audio_cue_ids'} and isinstance(child, list):
                result.extend(child)
            else:
                result.extend(recipe_cue_ids(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(recipe_cue_ids(child))
    return result


def doctor(args):
    data = catalog()
    integrity_errors, schema_errors, gaps = [], [], []
    lookup = {item['id']: item for item in data['assets']}
    if len(lookup) != len(data['assets']):
        schema_errors.append('Duplicate asset IDs in catalog')
    for item in data['assets']:
        if item['availability'] != 'local':
            continue
        path = local_path(item['local_path'])
        if not path.is_file():
            integrity_errors.append(item['id'] + ': missing file')
        elif file_sha(path) != item['sha256']:
            integrity_errors.append(item['id'] + ': SHA-256 changed; inspect source and re-index')
    for repo, expected in data['repositories'].items():
        if git(ROOT / 'assets/repos' / repo, 'rev-parse', 'HEAD') != expected['commit']:
            integrity_errors.append(repo + ': indexed commit differs from checkout')
    cue_data = read_json(ROOT / 'library/audio-cues.json', {})
    cues = {item['id']: item for item in cue_data.get('cues', [])}
    if len(cues) != len(cue_data.get('cues', [])):
        schema_errors.append('Duplicate cue IDs in library/audio-cues.json')
    aliases = dict(cue_data.get('asset_aliases', {}))
    aliases.update(data.get('asset_aliases', {}))
    for alias in aliases:
        try:
            target = resolve_asset_id(alias, lookup, aliases)
            if target not in lookup:
                schema_errors.append('Asset alias ' + alias + ': unknown asset ID ' + target)
        except ValueError as exc:
            schema_errors.append(str(exc))
    for cue_id, cue in cues.items():
        resolved = []
        for value in cue.get('asset_ids', []) + cue.get('candidate_asset_ids', []):
            try:
                asset_id = resolve_asset_id(value, lookup, aliases)
            except ValueError as exc:
                schema_errors.append(str(exc))
                continue
            if asset_id not in lookup:
                schema_errors.append('Cue ' + cue_id + ': unknown asset ID ' + value)
                continue
            asset = lookup[asset_id]
            resolved.append(asset)
            if asset.get('availability') != 'local':
                gaps.append({'type': 'audio_not_local', 'cue_id': cue_id, 'asset_id': asset_id,
                             'availability': asset.get('availability'), 'fetch_policy': asset.get('fetch_policy')})
        if not resolved:
            gaps.append({'type': 'cue_without_asset', 'cue_id': cue_id})
        elif not any(item.get('availability') == 'local' and item.get('audio_review') == 'auditioned_match' for item in resolved):
            gaps.append({'type': 'cue_without_auditioned_local_asset', 'cue_id': cue_id})
        for source_id in cue.get('external_sound_source_ids', []):
            gaps.append({'type': 'external_sound_source_unresolved', 'cue_id': cue_id, 'source_id': source_id})
    for asset in data['assets']:
        for cue_id in asset.get('cue_ids', []):
            if cue_id not in cues:
                schema_errors.append('Asset ' + asset['id'] + ': unknown cue ID ' + cue_id)
    recipes = read_json(ROOT / 'library/recipes.json', {}).get('recipes', [])
    if len({item['id'] for item in recipes}) != len(recipes):
        schema_errors.append('Duplicate recipe IDs in library/recipes.json')
    for recipe in recipes:
        for cue_id in recipe_cue_ids(recipe):
            if cue_id not in cues:
                schema_errors.append('Recipe ' + recipe['id'] + ': unknown cue ID ' + cue_id)
    errors = integrity_errors + schema_errors
    result = {'integrity_ok': not integrity_errors, 'schema_ok': not schema_errors, 'summary': data['summary'],
              'errors': errors, 'schema_errors': schema_errors, 'readiness_gaps': gaps,
              'production_notes': ['本地存在/哈希相符不代表授权或角色一致性已通过。', '未试听声音不能自动当目标原声；像素/再绘版不能替代网传3D版。',
                                   '远程候选与未试听项是readiness_gaps；不存在的资产/cue引用是schema_errors。']}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def multiview_ready(references):
    """Require source-backed coverage plus current visual reviews of the same version."""
    bundles = {}
    for item in references:
        role = item.get('source_reference_role')
        bundle = item.get('source_identity_bundle_id')
        if (role not in MULTIVIEW_ROLES or not bundle or item.get('availability') != 'local'
                or item.get('visual_review') != 'visual_checked' or item.get('review_status') != 'current_hash'
                or item.get('identity_tier') in {'art_variant', 'reference_mismatch'}
                or not item.get('multiview_evidence')):
            continue
        if role == 'licensed_model_render' and (item.get('model_license_status') != 'verified_reference_render_allowed'
                                                or not item.get('model_license_evidence')):
            continue
        bundles.setdefault(bundle, set()).update(item.get('view_coverage', []))
    return any({'front', 'side', 'back'} <= views for views in bundles.values())


def bind_assets(values, cast_ids, lookup, field):
    bindings = {key: [] for key in cast_ids}
    unassigned, blockers = [], []
    for value in values:
        requested, separator, asset_id = value.partition('=')
        if separator:
            character_id = resolve_character(requested)
            if character_id not in cast_ids:
                raise ValueError('Binding character is not in cast: ' + requested)
        else:
            character_id, asset_id = None, value
        if asset_id not in lookup:
            raise ValueError('Unknown asset ID: ' + asset_id)
        asset = lookup[asset_id]
        owners = [key for key in cast_ids if key in asset.get('character_ids', [])]
        if character_id and character_id not in owners:
            owners = []
        elif character_id:
            owners = [character_id]
        if len(owners) > 1:
            raise ValueError('Ambiguous asset binding: ' + asset_id + '; use --' + field + ' CHARACTER=' + asset_id)
        if not owners:
            unassigned.append({'requested_character_id': character_id, 'binding_type': field, 'asset': asset})
            blockers.append('角色不匹配，素材未绑定到cast: ' + asset_id)
        elif not any(item['id'] == asset_id for item in bindings[owners[0]]):
            bindings[owners[0]].append(asset)
    return bindings, unassigned, blockers


def character_blockers(character, references, sounds, mode):
    blockers = []
    if character.get('identity_status') == 'unresolved':
        blockers.append('角色身份未消歧；不得用牛来/食神唐牛等猜测替代。')
    if not references:
        blockers.append('未绑定具体本地视觉参考。')
    for item in references + sounds:
        if item['availability'] != 'local' or not item.get('local_path') or not local_path(item['local_path']).is_file():
            blockers.append('素材未落地: ' + item['id'])
        elif file_sha(local_path(item['local_path'])) != item.get('sha256'):
            blockers.append('素材哈希已变: ' + item['id'])
    for item in references:
        if item['kind'] not in VISUAL_KINDS:
            blockers.append('非视觉参考: ' + item['id'])
        if item['visual_review'] != 'visual_checked':
            blockers.append('参考尚未通过视觉核验: ' + item['id'])
        if item['identity_tier'] in {'art_variant', 'reference_mismatch'}:
            blockers.append('不能用艺术变体/错误三视图替代网传身份: ' + item['id'])
    bundles = {item['identity_bundle_id'] for item in references if item.get('identity_bundle_id')}
    if len(bundles) > 1:
        blockers.append('同一角色绑定了不同身份版本组，需选定同一版本: ' + ', '.join(sorted(bundles)))
    for item in sounds:
        if item['kind'] != 'audio':
            blockers.append('非音频素材: ' + item['id'])
        if item['audio_review'] != 'auditioned_match':
            blockers.append('声音尚未试听匹配: ' + item['id'])
    if mode == 'image-to-video' and not multiview_ready(references):
        blockers.append('AI视频前置未满足：缺少经核验的现成三视图或许可模型渲染多角度参考。原片单帧/16注视方向不是三视图。')
    return blockers


def handoff(args):
    lookup = {item['id']: item for item in catalog()['assets']}
    char_data = {item['id']: item for item in read_json(ROOT / 'library/characters.json', {}).get('characters', [])}
    requested = [args.character] if isinstance(args.character, str) else args.character
    cast_ids = list(dict.fromkeys(resolve_character(value) for value in requested))
    references, unassigned_refs, blockers = bind_assets(args.reference, cast_ids, lookup, 'reference')
    sounds, unassigned_audio, audio_blockers = bind_assets(args.audio, cast_ids, lookup, 'audio')
    blockers += audio_blockers
    positions = {}
    for value in getattr(args, 'position', []):
        name, separator, position = value.partition('=')
        if not separator or not position.strip():
            raise ValueError('Use --position CHARACTER=left/center/right')
        character_id = resolve_character(name)
        if character_id not in cast_ids:
            raise ValueError('Position character is not in cast: ' + name)
        if character_id in positions:
            raise ValueError('Duplicate screen position for: ' + name)
        positions[character_id] = position.strip()
    characters = []
    for number, character_id in enumerate(cast_ids):
        character = char_data[character_id]
        issues = character_blockers(character, references[character_id], sounds[character_id], args.mode)
        characters.append({'binding_id': chr(65 + number) if number < 26 else 'character-' + str(number + 1),
                           'character_id': character_id, 'character': character,
                           'screen_position': positions.get(character_id),
                           'reference_asset_ids': [item['id'] for item in references[character_id]],
                           'audio_asset_ids': [item['id'] for item in sounds[character_id]],
                           'reference_assets': references[character_id], 'audio_assets': sounds[character_id],
                           'multiview_ready': multiview_ready(references[character_id]), 'blockers': issues})
        blockers += [(('[' + character['name'] + '/' + character_id + '] ') if len(cast_ids) > 1 else '') + issue for issue in issues]
    recipe_data = read_json(ROOT / 'library/recipes.json', {}).get('recipes', [])
    recipe = next((item for item in recipe_data if item['id'] == args.recipe), None)
    if args.recipe and not recipe:
        raise ValueError('Unknown recipe: ' + args.recipe)
    output = local_path(args.output)
    # Validate final filenames too: a pre-existing symlink must not write outside ROOT.
    brief_path = local_path(output / 'brief.json')
    markdown_path = local_path(output / 'MODEL-HANDOFF.md')
    output.mkdir(parents=True, exist_ok=True)
    result = {'schema_version': 3, 'state': 'draft_only', 'mode': args.mode,
              'project_root': str(ROOT), 'character_ids': cast_ids, 'characters': characters,
              'reference_assets': [item for character in characters for item in character['reference_assets']],
              'audio_assets': [item for character in characters for item in character['audio_assets']],
              'unassigned_assets': unassigned_refs + unassigned_audio, 'recipe': recipe,
              'generation_allowed': False, 'publishing_allowed': False, 'blockers': blockers,
              'rules': ['读取并实际查看每个characters条目自己的reference_assets，不用文字另造形象。',
                        '每个角色只使用其绑定的身份、动作与录音；不串脸、串色，不把奶蛋andi交给奶蛙。',
                        'screen_position未指定时先确定位置；工具须逐角色接收真实附件，不凭多个名字融合形象。',
                        '仅使用audio_assets中的既有录音，不合成原作语音，不自动生成缺失BGM。',
                        '所有文件路径相对project_root，传给视频工具时必须上传真实文件。',
                        '本文件是交接草案，不代表素材有公开分发许可；不执行生成、剪辑或发布。']}
    if len(cast_ids) == 1:
        result['character'] = char_data[cast_ids[0]]
    dump(brief_path, result)
    lines = ['# 给视频模型的素材交接草案', '', '状态：draft_only；不得直接启动生成或发布。', '',
             '模式：' + args.mode, '项目根目录：`' + str(ROOT) + '`']
    for binding in characters:
        lines += ['', '## 角色' + binding['binding_id'] + '：' + binding['character']['name'] + ' (' + binding['character_id'] + ')',
                  '', '位置：' + (binding['screen_position'] or '待指定')]
        for field, label in [('reference_assets', '视觉'), ('audio_assets', '声音')]:
            for item in binding[field]:
                lines += ['- ' + label + ': ' + item['id'] + ' → `' + (item.get('local_path') or '未落地') + '`；SHA-256: ' + item.get('sha256', '无')]
    lines += ['', '## 当前阻塞'] + ['- ' + value for value in blockers]
    lines += ['', '## 给模型的指令'] + ['- ' + value for value in result['rules']]
    markdown_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output.relative_to(ROOT)), 'state': 'draft_only', 'blockers': blockers}, ensure_ascii=False, indent=2))


def preview(args):
    output = local_path('assets/private/catalog/index.html')
    output.parent.mkdir(parents=True, exist_ok=True)
    items = catalog()['assets']
    escape = html.escape
    cards = []
    for item in items:
        label = item['title'] + ' ' + item['id'] + ' ' + ' '.join(str(tag) for tag in item['tags']) + ' ' + ' '.join(item['character_ids'])
        body = ''
        if item['availability'] == 'local':
            relative = urllib.parse.quote(os.path.relpath(local_path(item['local_path']), output.parent), safe='/')
            src = escape(relative, quote=True)
            if item['kind'] in {'image', 'sprite', 'animation'}:
                body = '<img loading="lazy" src="' + src + '" alt="' + escape(item['title'], quote=True) + '">'
            elif item['kind'] == 'audio':
                body = '<audio controls preload="none" src="' + src + '"></audio>'
            elif item['kind'] == 'video':
                body = '<video controls preload="none" src="' + src + '"></video>'
        source = item['source_url']
        if urllib.parse.urlsplit(source).scheme != 'https':
            source = '#'
        cards.append(
            '<article data-search="' + escape(label.casefold(), quote=True)
            + '" data-kind="' + escape(item['kind'], quote=True)
            + '" data-local="' + item['availability'] + '">' + body
            + '<h2>' + escape(item['title']) + '</h2><code>' + escape(item['id']) + '</code>'
            + '<p>' + escape(', '.join(item['character_ids'])) + ' · ' + escape(item['availability'])
            + ' · ' + escape(item['license_status']) + '</p><p>' + escape(item.get('notes', ''))
            + '</p><a href="' + escape(source, quote=True)
            + '" target="_blank" rel="noopener noreferrer">原始来源</a></article>'
        )
    template = (ROOT / 'templates/catalog.html').read_text(encoding='utf-8')
    output.write_text(template.replace('{{CARDS}}', ''.join(cards)), encoding='utf-8')
    print(str(output))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('index')
    search_parser = subs.add_parser('search')
    search_parser.add_argument('--query', default='')
    search_parser.add_argument('--character')
    search_parser.add_argument('--kind')
    search_parser.add_argument('--local', action='store_true')
    search_parser.add_argument('--json', action='store_true')
    search_parser.add_argument('--limit', type=int, default=30)
    inspect = subs.add_parser('inspect'); inspect.add_argument('asset_id')
    review = subs.add_parser('review', help='Record an actual visual/audio check against the current file SHA-256')
    review.add_argument('asset_id')
    review.add_argument('--visual', choices=sorted(VISUAL_RESULTS))
    review.add_argument('--audio', choices=sorted(AUDIO_RESULTS))
    review.add_argument('--note', required=True, help='Evidence of what was actually viewed/listened to; not a metadata-only approval')
    review.add_argument('--identity-bundle-id', help='Same-version grouping, not an identity/rights certification')
    review.add_argument('--reference-role', choices=sorted(REVIEW_ROLES), help='Ordinary reference role; cannot certify a turnaround/model license')
    subs.add_parser('doctor')
    subs.add_parser('preview')
    hand = subs.add_parser('handoff')
    hand.add_argument('--character', required=True, action='append', help='Repeat for a cast; each character keeps its own references and sounds')
    hand.add_argument('--reference', action='append', default=[], help='ASSET_ID or CHARACTER=ASSET_ID; unqualified assets need exactly one cast owner')
    hand.add_argument('--audio', action='append', default=[], help='ASSET_ID or CHARACTER=ASSET_ID; voices never transfer between characters')
    hand.add_argument('--position', action='append', default=[], help='CHARACTER=left/center/right (optional)')
    hand.add_argument('--recipe', default='deadpan-thunder-laugh')
    hand.add_argument('--mode', choices=['image-to-video', 'existing-edit'], default='image-to-video')
    hand.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.command == 'index': index_assets()
    elif args.command == 'search': search(args)
    elif args.command == 'inspect':
        item = next((item for item in catalog()['assets'] if item['id'] == args.asset_id), None)
        if item is None: raise ValueError('Unknown asset ID: ' + args.asset_id)
        print(json.dumps(item, ensure_ascii=False, indent=2))
    elif args.command == 'review': review_asset(args)
    elif args.command == 'doctor': return doctor(args)
    elif args.command == 'preview': preview(args)
    elif args.command == 'handoff': handoff(args)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
