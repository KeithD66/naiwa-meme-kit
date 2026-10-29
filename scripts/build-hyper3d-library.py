#!/usr/bin/env python3
"""Index existing Hyper3D results and build a local, non-publishing QA gallery."""
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'hyper3d-gen2-260112'
SOURCE = 'https://docs.volcengine.com/docs/ark/shadoweye-create-3d-generation-task-api?lang=zh'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(root, value):
    path = Path(value)
    path = path if path.is_absolute() else root / path
    if not path.resolve().is_relative_to(root):
        raise ValueError('Result path escapes project')
    if any(p.is_symlink() for p in [path] + list(path.parents) if p != root):
        raise ValueError('Result path must not use symlinks')
    return path


def read(root, name, default=None):
    path = local(root, name)
    return json.loads(path.read_text()) if path.is_file() else default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def build(root=ROOT):
    root = Path(root).resolve()
    plan = read(root, 'library/hyper3d-plan.json')
    ledger = read(root, 'production/hyper3d/usage-ledger.json', {'entries': []})
    reviews = read(root, 'production/hyper3d/visual-reviews.json', {'reviews': []})['reviews']
    if plan.get('model') != MODEL or ledger.get('model', MODEL) != MODEL:
        raise ValueError('Unexpected result model')
    entries = {}
    for entry in ledger['entries']:
        if entry['job_id'] in entries:
            raise ValueError('Duplicate job in execution ledger')
        entries[entry['job_id']] = entry
    assets, versions = [], []
    for job in plan['jobs']:
        job_id = job['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', job_id):
            raise ValueError('Invalid result job ID')
        entry = entries.get(job_id, {})
        if entry.get('status') != 'succeeded':
            continue
        base = root / 'assets/private/hyper3d/models' / job_id
        manifest = read(root, base / 'manifest.json')
        audit = read(root, base / 'native-audit.json')
        if not manifest or not audit:
            raise ValueError('Successful result needs a downloaded manifest and native audit')
        if manifest.get('task_id') != entry['task_id'] or manifest.get('model') != MODEL:
            raise ValueError('Downloaded task does not match ledger')
        native = local(root, base / 'files/model.obj')
        native_hash = digest(native)
        if audit.get('sha256') != native_hash:
            raise ValueError('Native audit hash differs from actual OBJ')
        expected = next((f for f in manifest['files'] if f['path'] == 'files/model.obj'), None)
        if not expected or expected['sha256'] != native_hash:
            raise ValueError('Native OBJ differs from download manifest')
        review = next((r for r in reversed(reviews) if r['job_id'] == job_id
                       and r.get('native_model_sha256') == native_hash), {})
        common = {'character_ids': [job['character_id']], 'model': MODEL, 'task_id': entry['task_id'],
                  'identity_bundle_id': job['version_id'], 'identity_tier': 'geometry_only_reconstruction_candidate',
                  'default_identity': False, 'color_identity_reference_ready': False,
                  'reference_role': 'geometry_inspection_only', 'source_url': SOURCE,
                  'source_asset_id': job['references'][0]['source_asset_id'],
                  'source_sha256': entry['reference_sha256'], 'usage_scope': 'local_reference_only',
                  'license_status': job['license_status'], 'publishing_allowed': False,
                  'source_materials_provided': audit.get('material_count', 0) > 0,
                  'source_textures_provided': manifest.get('texture_files_returned', False),
                  'rigged': False, 'animation_ready': False,
                  'review_status_note': review.get('status', 'not_reviewed'),
                  'notes': 'Geometry inspection / failure benchmark only; not a default character identity reference.'}

        def add(suffix, path, kind, title, expected_hash=None):
            path = local(root, path)
            if not path.is_file():
                return None
            actual = digest(path)
            if expected_hash and expected_hash != actual:
                raise ValueError('Derived file hash mismatch: ' + suffix)
            asset_id = job_id + '-' + suffix
            assets.append({**common, 'id': asset_id, 'title': title, 'kind': kind,
                           'local_path': path.relative_to(root).as_posix(), 'sha256': actual,
                           'bytes': path.stat().st_size, 'derived_from_asset_id': job_id + '-native-obj'
                           if suffix != 'native-obj' else common['source_asset_id']})
            return asset_id

        native_id = add('native-obj', native, 'model', '奶蛙Hyper3D原生四边面·身份失败样本', native_hash)
        preview = base / 'geometry-preview-package/character.glb'
        preview_id = add('geometry-preview', preview, 'model', '奶蛙Hyper3D三角化灰模·仅几何检查')
        card = read(root, base / 'geometry-preview-package/character-card.json', {})
        if preview_id:
            expected_preview = next((f['sha256'] for f in card.get('files', []) if f['path'] == 'character.glb'), None)
            if expected_preview != digest(preview):
                raise ValueError('Preview does not match its character card')
        add('preview-card', base / 'geometry-preview-package/character-card.json', 'document', 'Hyper3D灰模派生说明')
        reference_file = base / 'references/reference-pack.json'
        pack = read(root, reference_file, {})
        view_count = mask_count = 0
        if pack:
            if not preview_id or pack.get('source_model_sha256') != digest(preview):
                raise ValueError('Reference pack is bound to another preview model')
            spec = importlib.util.spec_from_file_location('hyper_ref_validation', Path(__file__).with_name('render-character-pack.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.verify_cached_pack(reference_file.parent, digest(preview), pack['settings'])
            for i, view in enumerate(pack['views']):
                add('view-%02d' % i, view['path'], 'image', 'Hyper3D灰模几何视图·身份拒绝', view['sha256'])
                add('mask-%02d' % i, view['mask_path'], 'mask', 'Hyper3D灰模轮廓', view['mask_sha256'])
            view_count = mask_count = len(pack['views'])
            for name, kind in [('contact-sheet.jpg', 'image'), ('turntable.mp4', 'video')]:
                if name in pack.get('artifact_hashes', {}):
                    add(Path(name).stem, reference_file.parent / name, kind,
                        'Hyper3D几何失败样本·' + name, pack['artifact_hashes'][name])
        mesh = audit['meshes'][0]
        versions.append({'job_id': job_id, 'task_id': entry['task_id'], 'version_id': job['version_id'],
                         'native_asset_id': native_id, 'preview_asset_id': preview_id,
                         'native_sha256': native_hash, 'native_face_count': mesh['face_count'],
                         'source_face_vertex_histogram': mesh['source_face_vertex_histogram'],
                         'quad_face_fraction': mesh['quad_face_fraction'],
                         'material_count': audit.get('material_count', 0),
                         'reported_usage_tokens': entry.get('reported_usage_tokens'),
                         'visual_status': review.get('status', 'not_reviewed'),
                         'visual_findings': review.get('findings', []),
                         'default_identity': False, 'color_identity_reference_ready': False,
                         'views': view_count, 'masks': mask_count,
                         'source_input': 'assets/private/hyper3d/requests/' + job_id + '/inputs/reference-00.png',
                         'model_directory': base.relative_to(root).as_posix()})
    registry = {'schema_version': 1, 'model': MODEL, 'versions': versions,
                'reported_usage_tokens': sum(e.get('reported_usage_tokens') or 0 for e in entries.values()),
                'reserved_tokens': sum(e.get('reserved_tokens') or 0 for e in entries.values()),
                'account_remaining_verified': False, 'free_allowance_confirmed_by_user': True,
                'declared_free_tokens': None, 'asset_records': len(assets)}
    write(root / 'library/hyper3d-assets.json', {'schema_version': 1, 'assets': assets})
    write(root / 'library/hyper3d-registry.json', registry)
    gallery = root / 'assets/private/hyper3d/index.html'
    gallery.parent.mkdir(parents=True, exist_ok=True)

    def link(path):
        return html.escape(quote(os.path.relpath(local(root, path), gallery.parent)), quote=True)

    rows = []
    for version in versions:
        base = version['model_directory']
        status = ('身份拒绝：多出一对展开手臂，形成四臂。缺少材质及贴图。'
                  if version['visual_status'] == 'rejected_extra_limbs_missing_materials'
                  else '未认证的本地几何候选，须查看审核记录。')
        elements = [f'<h2>{html.escape(version["job_id"])}</h2>',
                    '<p><strong>' + status + '</strong></p>',
                    f'<p>原生四边面 {version["native_face_count"]:,}，占比 {version["quad_face_fraction"]:.0%}。仅作几何检查和失败样本。</p>']
        for path, label in [(version['source_input'], '实际输入'),
                            (base + '/references/level/front.png', '四臂灰模·拒绝作为身份参考')]:
            if local(root, path).is_file():
                elements.append(f'<figure><img src="{link(path)}" alt="{label}"><figcaption>{label}</figcaption></figure>')
        for path, label in [(base + '/files/model.obj', '下载原生四边面 OBJ'),
                            (base + '/geometry-preview-package/character.glb', '下载三角化灰模 GLB'),
                            (base + '/references/contact-sheet.jpg', '查看八角度检查图')]:
            if local(root, path).is_file():
                elements.append(f'<p><a href="{link(path)}">{label}</a></p>')
        video = base + '/references/turntable.mp4'
        if local(root, video).is_file():
            elements.append(f'<video controls preload="none" src="{link(video)}"></video>')
        rows.append('<section>' + ''.join(elements) + '</section>')
    comparison = root / 'assets/private/hyper3d/comparison/uniform-neutral/comparison.jpg'
    comparison_link = ('<p><a href="' + link(comparison) + '">Hitem3D / Seed3D / Hyper3D 统一几何对照</a></p>'
                       if comparison.is_file() else '')
    gallery.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Hyper3D奶蛙实测</title>'
                       '<style>body{font:16px/1.6 system-ui;max-width:1100px;margin:32px auto;padding:20px;background:#f4f3ef;color:#252525}'
                       'section{background:white;padding:24px;border-radius:16px}figure{display:inline-block;max-width:44%;vertical-align:top;margin:12px}img,video{width:100%;max-width:512px}strong{color:#9a290f}</style>'
                       '<h1>Hyper3D 奶蛙：实测与审核留档</h1><p>实际消耗' + format(registry['reported_usage_tokens'], ',') + ' tokens。'
                       '原生Quad保留，GLB为无纹理灰模派生件。相机转台没有骨骼或角色动作。</p>'
                       + comparison_link + ''.join(rows) + '</html>', encoding='utf-8')
    return registry


if __name__ == '__main__':
    result = build()
    print(json.dumps({'versions': len(result['versions']), 'assets': result['asset_records'],
                      'reported_tokens': result['reported_usage_tokens'], 'gallery': 'assets/private/hyper3d/index.html'}))
