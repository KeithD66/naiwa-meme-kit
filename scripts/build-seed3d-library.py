#!/usr/bin/env python3
"""Build a local Seed3D metadata registry and offline HTML gallery.

Reads existing project files only: no credentials, network, API, geometry import,
rendering, or visual approval. A successful API task is distinct from a complete
and hash-verified local model/reference package.
"""
import argparse
from collections import Counter
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
from urllib.parse import quote, urlsplit


NAMES = {'naiwa': '奶蛙', 'naidan': '奶蛋', 'capylulu': '水豚噜噜 · 社区版',
         'meituan_meme': '肥嘟嘟 · 社区版'}
TERMINAL = {'succeeded', 'failed', 'cancelled', 'canceled', 'expired'}
SEED3D_SOURCE_URL = 'https://docs.volcengine.com/docs/ark/create-3d-generation-task-api?lang=zh'


def fixed_source_reference_url(value):
    """Only accept pinned public GitHub media, never result/CDN/signed URLs."""
    if not isinstance(value, str) or any(c.isspace() or c in '\"\'<>' for c in value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if (parsed.scheme == 'https' and parsed.netloc == 'raw.githubusercontent.com'
            and not parsed.query and not parsed.fragment
            and re.fullmatch(r'/[^/]+/[^/]+/[0-9a-fA-F]{40}/.+', parsed.path)):
        return value
    return None


def safe_text(value):
    value = str(value)
    value = re.sub(r'https?://[^\s<>"\']+', '[外部链接已省略]', value, flags=re.I)
    value = re.sub(r'\bark-[A-Za-z0-9-]+', '[REDACTED]', value)
    value = re.sub(r'\bBearer\s+\S+', 'Bearer [REDACTED]', value, flags=re.I)
    value = re.sub(r'(?i)\b(api[_ -]?key|authorization|secret|access[_ -]?token)\s*[:=]\s*[^\s,;]+',
                   r'\1=[REDACTED]', value)
    return value[:4000]


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def confined(root, value, *, base=None, within=None):
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('Invalid local path')
    if urlsplit(value).scheme or urlsplit(value).netloc or Path(value).is_absolute():
        raise ValueError('Only project-relative local paths are allowed')
    path = ((base or root) / value).resolve()
    if not path.is_relative_to(root) or (within and not path.is_relative_to(within)):
        raise ValueError('Path escapes the allowed project/package directory')
    return path


def read_json(root, value, default=None, *, base=None, within=None):
    path = confined(root, value, base=base, within=within)
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def number(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def angle(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def batch_budget(plan, ledger):
    ids = {j['id'] for j in plan['jobs']}
    model = plan.get('model')
    entries = [e for e in ledger.get('entries', []) if e.get('job_id') in ids
               and e.get('model', ledger.get('model', model)) == model]
    # A repeated snapshot of one task must not double-count its usage. Distinct
    # task IDs for the same job still count if the ledger records an extra call.
    unique = {}
    for entry in entries:
        unique[entry.get('task_id') or entry['job_id']] = entry
    entries = list(unique.values())
    actual = sum(number(e.get('reported_usage_tokens')) for e in entries)
    pending = sum(number(e.get('reserved_tokens')) for e in entries if e.get('status') not in TERMINAL)
    budget = plan.get('budget', {})
    declared, limit = number(budget.get('declared_free_tokens')), number(budget.get('batch_limit_tokens'))
    return {'scope': 'current plan jobs and model only; prior tasks are excluded',
            'actual_reported_tokens': actual, 'pending_reserved_tokens': pending,
            'accounted_tokens': actual+pending, 'batch_limit_tokens': limit,
            'batch_remaining_after_reservations_tokens': max(0, limit-actual-pending),
            'declared_free_tokens': declared,
            'declared_free_remaining_after_this_batch_estimate': max(0, declared-actual-pending),
            'account_remaining_verified': False,
            'basis': 'local ledger, not provider account balance or confirmation of free billing'}


def build_library(root, html_path='assets/private/seed3d/index.html'):
    root = Path(root).resolve()
    html_target = confined(root, html_path)
    plan = read_json(root, 'library/seed3d-plan.json')
    if not isinstance(plan, dict) or not isinstance(plan.get('jobs'), list):
        raise ValueError('library/seed3d-plan.json must contain jobs')
    ledger = read_json(root, 'production/seed3d/usage-ledger.json', {})
    reviews = read_json(root, 'production/seed3d/visual-reviews.json', {}).get('reviews', [])
    prepared = read_json(root, 'library/seed3d-inputs.json', {}).get('inputs', [])
    latest = {e.get('job_id'): e for e in ledger.get('entries', [])
              if e.get('model', ledger.get('model', plan.get('model'))) == plan.get('model')}
    assets, versions, warnings, seen = [], [], [], set()

    for job in plan['jobs']:
        job_id, character = job['id'], job['character_id']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', job_id):
            raise ValueError('Invalid planned job ID')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', character):
            raise ValueError('Invalid character ID')
        if job_id in seen:
            raise ValueError('Duplicate planned job ID')
        seen.add(job_id)
        version = safe_text(job.get('version', job_id))
        license_status = safe_text(job.get('license_status', 'source_rights_unresolved'))
        entry = latest.get(job_id, {})
        status = safe_text(entry.get('status', 'not_submitted'))
        job_dir = root / 'assets/private/seed3d/models' / job_id
        package_dir = job_dir / 'package'
        refs_dir = job_dir / 'references'
        job_warnings, job_assets = [], []
        prepared_record = next((p for p in prepared if p.get('character_id') == character
                                and p.get('source_asset_id') == job.get('source_asset_id')), {})
        source_reference_url = fixed_source_reference_url(prepared_record.get('source_fixed_url'))

        def artifact(suffix, title, kind, value, expected=None, *, base=None, within=None,
                     role='candidate', derived=None, extra=None):
            if not value:
                return None
            try:
                path = confined(root, value, base=base, within=within)
                if not path.is_file():
                    job_warnings.append(f'{suffix}: file missing')
                    return None
                sha = digest(path)
                if expected and sha != expected:
                    job_warnings.append(f'{suffix}: SHA256 mismatch')
                    return None
            except (ValueError, OSError):
                job_warnings.append(f'{suffix}: unsafe or unreadable local path')
                return None
            record = {'id': f'{job_id}-{suffix}', 'title': title, 'kind': kind,
                      'job_id': job_id, 'character_ids': [character], 'version_id': version,
                      'source_asset_id': safe_text(job.get('source_asset_id', '')),
                      'source_url': SEED3D_SOURCE_URL, 'tags': ['seed3d', 'local_only'],
                      'identity_bundle_id': version, 'identity_tier': 'ai_reconstruction_candidate',
                      'local_path': path.relative_to(root).as_posix(), 'availability': 'local',
                      'sha256': sha, 'expected_sha256': sha, 'bytes': path.stat().st_size,
                      'license_status': license_status, 'usage_scope': 'local_reference_only',
                      'local_only': True, 'publishing_allowed': False,
                      'reference_role': role if role in {'front', 'side', 'back'} else 'candidate',
                      'default_identity': False}
            if source_reference_url:
                record['source_reference_url'] = source_reference_url
            if derived:
                record['derived_from_asset_id'] = derived
            if extra:
                record.update(extra)
            assets.append(record)
            job_assets.append(record)
            return record

        input_asset = artifact('input', 'API 实际输入参考', 'image', job.get('reference_path'),
                               job.get('reference_sha256'), derived=job.get('source_asset_id'),
                               extra={'identity_tier': 'existing_source_reference'})
        prepared_asset = artifact('prepared-input', '现成像素准备图', 'image', prepared_record.get('output_path'),
                                  prepared_record.get('prepared_sha256'), derived=job.get('source_asset_id'),
                                  extra={'identity_tier': 'existing_source_pixel_preparation'})
        manifest = read_json(root, 'manifest.json', {}, base=job_dir, within=job_dir)
        card = read_json(root, 'character-card.json', {}, base=package_dir, within=package_dir)
        refpack = read_json(root, 'reference-pack.json', {}, base=refs_dir, within=refs_dir)
        native_assets, working, obj, card_asset = [], None, None, None
        package_valid = False
        if (status == 'succeeded' and manifest.get('job_id') == job_id
                and manifest.get('reference_sha256') == job.get('reference_sha256')):
            manifest_files = {f.get('path'): f for f in manifest.get('files', []) if isinstance(f, dict)}
            for i, mesh in enumerate(manifest.get('meshes', [])):
                meta = manifest_files.get(mesh, {})
                if not meta.get('sha256'):
                    job_warnings.append('native mesh has no manifest hash')
                    continue
                asset = artifact(f'native-{i}', 'Seed3D 原始模型', 'model', mesh, meta['sha256'],
                                 base=job_dir, within=job_dir, derived=job.get('source_asset_id'))
                if asset:
                    native_assets.append(asset)
            package_valid = bool(card and card.get('job_id') == job_id and card.get('character_id') == character)
            if not package_valid:
                job_warnings.append('local package card is missing or does not identify this job')
            native_hashes = {a['sha256'] for a in native_assets}
            if card and card.get('source', {}).get('sha256') not in native_hashes:
                package_valid = False
                job_warnings.append('package source hash does not match a verified native model')
            file_meta = {f.get('path'): f for f in card.get('files', []) if isinstance(f, dict)}
            # Every declared package dependency must exist and match its recorded bytes.
            for name, meta in file_meta.items():
                try:
                    path = confined(root, name, base=package_dir, within=package_dir)
                    if not meta.get('sha256') or not path.is_file() or digest(path) != meta['sha256']:
                        package_valid = False
                        job_warnings.append('package dependency missing or changed: ' + safe_text(name))
                except (ValueError, OSError):
                    package_valid = False
                    job_warnings.append('unsafe package dependency')
            if not file_meta:
                package_valid = False
            if not {'character.glb', 'character.obj'} <= set(file_meta):
                package_valid = False
            if package_valid:
                working = artifact('working-glb', '标准尺度 PBR 工作模型', 'model', 'character.glb',
                                   file_meta.get('character.glb', {}).get('sha256'), base=package_dir,
                                   within=package_dir, derived=native_assets[0]['id'] if native_assets else None)
                obj = artifact('exchange-obj', 'Blender diffuse OBJ 交换版', 'model', 'character.obj',
                               file_meta.get('character.obj', {}).get('sha256'), base=package_dir,
                               within=package_dir, derived=working['id'] if working else None)
                card_asset = artifact('character-card', '角色卡 JSON', 'document', 'character-card.json',
                                      base=package_dir, within=package_dir)
                for name, meta in file_meta.items():
                    if name.endswith('.png') or name.endswith('.mtl') or name == 'character-card.md':
                        kind = 'texture' if name.endswith('.png') else 'document'
                        artifact('package-' + re.sub(r'[^A-Za-z0-9_-]', '-', name), 'OBJ 依赖 / 角色说明', kind,
                                 name, meta.get('sha256'), base=package_dir, within=package_dir)
        elif status == 'succeeded':
            job_warnings.append('successful API task has no matching local download manifest')

        visual = {'status': 'not_reviewed', 'review_state': 'not_recorded', 'default_identity': False, 'notes': []}
        if working:
            candidates = [r for r in reviews if r.get('job_id') == job_id]
            matched = [r for r in candidates if r.get('working_model_sha256') == working['sha256']]
            if matched:
                review = matched[-1]
                notes = review.get('notes', [])
                visual = {'status': safe_text(review.get('status', 'not_reviewed')), 'review_state': 'current_hash',
                          'working_model_sha256': working['sha256'], 'default_identity': False,
                          'notes': [safe_text(n) for n in (notes if isinstance(notes, list) else [notes])]}
            elif candidates:
                visual['review_state'] = 'stale_hash'

        view_assets, mask_assets, turntable, contact = [], [], None, None
        refs_match = bool(working and refpack.get('source_model_sha256') == working['sha256'])
        if refs_match:
            calibrated = card.get('transformation', {}).get('front_calibration') == 'provided_visual_calibration'
            for i, view in enumerate(refpack.get('views', [])):
                pitch, yaw = angle(view.get('pitch_degrees')), angle(view.get('yaw_degrees'))
                role = {0: 'front', 90: 'side', 180: 'back', 270: 'side'}.get(yaw, 'candidate') if pitch == 0 and calibrated else 'candidate'
                extra = {'camera_pitch_degrees': pitch, 'camera_yaw_degrees': yaw,
                         'view_label_basis': 'camera yaw only; anatomical identity not certified'}
                for is_mask in (False, True):
                    value, expected = (view.get('mask_path'), view.get('mask_sha256')) if is_mask else (view.get('path'), view.get('sha256'))
                    if not expected:
                        continue
                    record = artifact(('mask' if is_mask else 'view') + f'-{i:02d}',
                                      '轮廓 mask' if is_mask else '3D 参考帧', 'mask' if is_mask else 'image', value, expected,
                                      within=refs_dir, role='candidate' if is_mask else role, derived=working['id'], extra=extra)
                    if record:
                        (mask_assets if is_mask else view_assets).append(record)
            hashes = refpack.get('artifact_hashes', {})
            tt = refpack.get('turntable', {})
            if isinstance(tt, dict) and hashes.get('turntable.mp4'):
                turntable = artifact('turntable', '静态模型相机转台', 'video', tt.get('path'), hashes['turntable.mp4'],
                                     within=refs_dir, derived=working['id'], extra={'camera_orbit_only': True, 'character_motion_created': False})
            if hashes.get('contact-sheet.jpg'):
                contact = artifact('contact-sheet', '8 向联系图', 'image', refpack.get('contact_sheet'), hashes['contact-sheet.jpg'],
                                   within=refs_dir, derived=working['id'])
        elif refpack:
            job_warnings.append('reference pack source model SHA does not match current working model')
        model_complete = bool(status == 'succeeded' and package_valid and native_assets and working and obj and card_asset)
        input_complete = bool(input_asset and (not prepared_record or prepared_asset))
        references_complete = bool(refs_match and len({a['local_path'] for a in view_assets}) == 24
                                   and len({a['local_path'] for a in mask_assets}) == 24
                                   and len({(a['camera_pitch_degrees'], a['camera_yaw_degrees']) for a in view_assets}) == 24
                                   and turntable and contact)
        summary = card.get('working_summary', {}) if package_valid else {}
        version_record = {'job_id': job_id, 'character_id': character, 'display_name': NAMES.get(character, character),
                          'version_id': version, 'identity_bundle_id': version,
                          'source_asset_id': safe_text(job.get('source_asset_id', '')), 'model': safe_text(plan.get('model', '')),
                          'task_status': status, 'model_package_complete': model_complete,
                          'input_reference_complete': input_complete, 'reference_pack_complete': references_complete,
                          'complete': input_complete and model_complete and references_complete,
                          'visual_review': visual, 'default_identity': False,
                          'license_status': license_status, 'usage_scope': 'local_reference_only', 'local_only': True,
                          'publishing_allowed': False, 'community_version': 'community' in version,
                          'rigged': False, 'animated': False, 'camera_orbit_only': True,
                          'capabilities': {'static_reference_render': model_complete, 'reference_views': len(view_assets),
                                           'silhouette_masks': len(mask_assets), 'character_motion': False},
                          'geometry': {key: number(summary.get(key)) for key in ('geometry_count', 'instance_count', 'triangle_count')},
                          'obj_pbr_losses': [safe_text(n) for n in card.get('obj_pbr_losses', [])],
                          'asset_ids': [a['id'] for a in job_assets],
                          'links': {key: value['id'] for key, value in [('input', input_asset or prepared_asset), ('prepared_input', prepared_asset), ('working_glb', working),
                                    ('obj', obj), ('card', card_asset), ('turntable', turntable), ('contact_sheet', contact)] if value},
                          'limitations': ['静态网格，无骨骼和角色动作；转台只移动相机。', '单图遮挡部位及背面由模型推测，未核实原型。',
                                          'GLB 是 PBR 材质主本；OBJ 仅 diffuse 交换，具体损失见角色卡。'],
                          'warnings': job_warnings}
        if version_record['community_version']:
            version_record['limitations'].append('社区版本实验，不替代官方或网传标准身份。')
        front = next((a for a in view_assets if a.get('camera_pitch_degrees') == 0 and a.get('camera_yaw_degrees') == 0), None)
        if front:
            version_record['links']['front'] = front['id']
        if card_asset:
            version_record['package_path'] = package_dir.relative_to(root).as_posix()
        if refs_match:
            version_record['reference_pack_path'] = (refs_dir / 'reference-pack.json').relative_to(root).as_posix()
        versions.append(version_record)
        warnings.extend(f'{job_id}: {w}' for w in job_warnings)

    budget = batch_budget(plan, ledger)
    counts = {'planned_jobs': len(versions), 'api_succeeded_jobs': sum(v['task_status'] == 'succeeded' for v in versions),
              'complete_jobs': sum(v['complete'] for v in versions),
              'model_packages': sum(v['model_package_complete'] for v in versions),
              'reference_packs': sum(v['reference_pack_complete'] for v in versions), 'local_assets': len(assets)}
    asset_index = {'schema_version': 1, 'scope': 'local-only reconstruction candidates; no media embedded', 'assets': assets, 'summary': counts}
    registry = {'schema_version': 1, 'model': safe_text(plan.get('model', '')), 'budget': budget,
                'summary': counts, 'versions': versions, 'warnings': warnings}
    return asset_index, registry, gallery_html(root, html_target, asset_index, registry)


def gallery_html(root, html_target, asset_index, registry):
    by_id = {a['id']: a for a in asset_index['assets']}
    escape = lambda text: html.escape(safe_text(text), quote=True)

    def href(asset):
        target = confined(root, asset['local_path'])
        return html.escape(quote(os.path.relpath(target, html_target.parent), safe='/'), quote=True)

    sections = []
    for version in registry['versions']:
        links = {key: by_id[value] for key, value in version['links'].items() if value in by_id}
        pictures = []
        for key, label in (('input', 'API 实际输入参考'), ('front', '3D 正面相机')):
            pictures.append(f'<figure><img loading="lazy" src="{href(links[key])}" alt="{escape(label)}"><figcaption>{escape(label)}</figcaption></figure>'
                            if key in links else f'<figure><div class="placeholder">尚无{escape(label)}</div></figure>')
        video = f'<video controls playsinline preload="none" src="{href(links["turntable"])}"></video>' if 'turntable' in links else '<p>转台尚未完成。</p>'
        downloads = ' '.join(f'<a download href="{href(links[key])}">{escape(label)}</a>' for key, label in
                             [('working_glb', 'PBR GLB'), ('obj', 'OBJ'), ('contact_sheet', '联系图'), ('card', '角色卡 JSON')] if key in links)
        dependencies = ' '.join(f'<a download href="{href(by_id[aid])}">{escape(Path(by_id[aid]["local_path"]).name)}</a>'
                                for aid in version['asset_ids'] if '-package-' in aid)
        notes = version['limitations'] + version['visual_review']['notes'] + version['warnings']
        items = ''.join(f'<li>{escape(note)}</li>' for note in notes)
        review = version['visual_review']
        state = '本地资产完整' if version['complete'] else '本地资产未完成'
        sections.append(f'<article><h2>{escape(version["display_name"])}</h2><p class="version">{escape(version["version_id"])}</p>'
                        f'<p>{state} · API {escape(version["task_status"])} · 视觉审核 {escape(review["status"])} / {escape(review["review_state"])}</p>'
                        f'<div class="compare">{"".join(pictures)}</div>{video}<p class="downloads">{downloads}</p>'
                        f'<details><summary>OBJ 依赖与说明</summary>{dependencies}</details><ul>{items}</ul></article>')
    b, s = registry['budget'], registry['summary']
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' file:; media-src 'self' file:; style-src 'unsafe-inline'">
<title>奶蛙生态 · Seed3D 本地资产库</title><style>
body{{margin:0;background:#101318;color:#eef0f2;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1300px;margin:auto;padding:28px}}
h1{{font-size:30px}}h2{{margin:0}}.intro{{max-width:1000px;color:#bec8d1}}.budget{{padding:18px;background:#1f2b32;border-radius:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:22px;margin-top:24px}}article{{padding:20px;border:1px solid #36424c;border-radius:14px;background:#191f26}}
.version{{overflow-wrap:anywhere;color:#a8d8bd;font-size:13px}}.compare{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}figure{{margin:0}}img{{width:100%;aspect-ratio:1;object-fit:contain;background:#fff;border-radius:8px}}
figcaption{{font-size:13px;color:#c7d1db}}video{{width:100%;max-height:360px;margin-top:16px;background:#fff;border-radius:8px}}a{{color:#acd8ff;overflow-wrap:anywhere}}.downloads a{{display:inline-block;margin:4px 14px 4px 0}}.placeholder{{display:grid;place-items:center;min-height:180px;background:#252e38;border-radius:8px}}li{{margin:5px 0;font-size:14px}}details a{{display:block}}
</style></head><body><main><h1>奶蛙生态 · Seed3D 本地资产库</h1>
<p class="intro">只展示本机已有且哈希匹配的文件。全部为现成参考约束的 AI 重建候选，限本地使用；未获发布许可，不代表官方模型或已批准的默认身份。视觉审核来自绑定工作模型 SHA 的人工记录，图册不会代替看图。</p>
<div class="budget">本批：已报告 {b['actual_reported_tokens']:,} tokens · 待定预留 {b['pending_reserved_tokens']:,} · 批次上限 {b['batch_limit_tokens']:,}。<br>
用户声明免费额度 {b['declared_free_tokens']:,}；仅扣本批及预留后的本地估算 {b['declared_free_remaining_after_this_batch_estimate']:,}，不是账户实时余额或免费额度核验。<br>
{s['planned_jobs']} 个计划角色；{s['api_succeeded_jobs']} 个 API 成功；{s['complete_jobs']} 个完整本地资产包；{s['local_assets']} 个实际本地文件。</div>
<div class="grid">{''.join(sections)}</div></main></body></html>'''


def write_outputs(root, assets_output='library/seed3d-assets.json', registry_output='library/seed3d-registry.json',
                  html_output='assets/private/seed3d/index.html'):
    root = Path(root).resolve()
    assets, registry, markup = build_library(root, html_output)
    protected = {'library/seed3d-plan.json', 'library/seed3d-inputs.json', 'production/seed3d/usage-ledger.json',
                 'production/seed3d/visual-reviews.json'} | {a['local_path'] for a in assets['assets']}
    for version in registry['versions']:
        prefix = 'assets/private/seed3d/models/' + version['job_id']
        protected.update({prefix + '/manifest.json', prefix + '/package/character-card.json',
                          prefix + '/references/reference-pack.json'})
    outputs = [confined(root, p) for p in (assets_output, registry_output, html_output)]
    if len(set(outputs)) != 3 or any(p.relative_to(root).as_posix() in protected for p in outputs):
        raise ValueError('Output must not overwrite a source or another output')
    for path, data in zip(outputs, (json.dumps(assets, ensure_ascii=False, indent=2)+'\n',
                                  json.dumps(registry, ensure_ascii=False, indent=2)+'\n', markup)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding='utf-8')
    return registry['summary']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--assets-output', default='library/seed3d-assets.json')
    parser.add_argument('--registry-output', default='library/seed3d-registry.json')
    parser.add_argument('--html-output', default='assets/private/seed3d/index.html')
    args = parser.parse_args()
    try:
        print(json.dumps(write_outputs(args.root, args.assets_output, args.registry_output, args.html_output), ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, 'Index build failed: ' + safe_text(exc) + '\n')


if __name__ == '__main__':
    main()
