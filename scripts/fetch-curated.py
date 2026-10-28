#!/usr/bin/env python3
"""Fetch pinned, hashed public media into the ignored local reference store."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'assets/private/curated'
MANIFEST = ROOT / 'library/downloads.json'


def target_path(relative):
    rel = PurePosixPath(relative)
    if not relative or rel.is_absolute() or '..' in rel.parts or '\\' in relative:
        raise ValueError('Unsafe asset path: ' + relative)
    target = DEST.joinpath(*rel.parts)
    if DEST.resolve() not in target.resolve().parents:
        raise ValueError('Asset path escapes reference store: ' + relative)
    return target


def check_bytes(asset, data):
    if asset.get('bytes') is not None and len(data) != asset['bytes']:
        raise ValueError('Byte count mismatch')
    git_sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if asset.get('git_blob_sha1') and git_sha != asset['git_blob_sha1'].lower():
        raise ValueError('Git blob SHA-1 mismatch')
    sha256 = hashlib.sha256(data).hexdigest()
    if asset.get('sha256') and sha256 != asset['sha256'].lower():
        raise ValueError('SHA-256 mismatch')
    return sha256


def download_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Expected public HTTPS URL')
    proxy = os.environ.get('GITHUB_PROXY', '').rstrip('/')
    if proxy and parsed.hostname in {'github.com', 'raw.githubusercontent.com'}:
        if urllib.parse.urlsplit(proxy).scheme != 'https':
            raise ValueError('GITHUB_PROXY must use HTTPS')
        return proxy + '/' + url
    return url


def fetch(asset, retries):
    target = target_path(asset['path'])
    result = {'id': asset['id'], 'path': str(target.relative_to(ROOT)), 'url': asset['url']}
    if target.is_file():
        try:
            sha = check_bytes(asset, target.read_bytes())
            return dict(result, status='verified_existing', sha256=sha, bytes=target.stat().st_size)
        except ValueError:
            pass  # Keep the old file until a verified replacement is ready.
    last_error = ''
    for attempt in range(1, retries + 1):
        temporary = None
        try:
            request = urllib.request.Request(download_url(asset['url']), headers={'User-Agent': 'naiwa-meme-kit-reference-fetcher/2'})
            limit = min(asset.get('max_bytes', 32 * 1024 * 1024), 128 * 1024 * 1024)
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError('Asset exceeds size limit')
            sha = check_bytes(asset, data)
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix='.' + target.name + '.', suffix='.part', dir=str(target.parent))
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
            os.replace(temporary, target)
            return dict(result, status='downloaded', sha256=sha, bytes=len(data), attempts=attempt)
        except Exception as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(min(attempt, 3))
        finally:
            if temporary and Path(temporary).exists():
                Path(temporary).unlink()
    return dict(result, status='failed', error=last_error, attempts=retries)


def load_manifest():
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    assets = data['assets']
    ids, paths = set(), set()
    for asset in assets:
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', asset['id']):
            raise ValueError('Invalid asset ID')
        if asset['id'] in ids or asset['path'] in paths:
            raise ValueError('Duplicate asset ID or destination')
        ids.add(asset['id']); paths.add(asset['path'])
        target_path(asset['path'])
        download_url(asset['url'])
        if not asset.get('git_blob_sha1') and not asset.get('sha256'):
            raise ValueError('Pinned content hash required: ' + asset['id'])
        if asset.get('git_blob_sha1') and not re.fullmatch(r'[0-9a-fA-F]{40}', asset['git_blob_sha1']):
            raise ValueError('Invalid Git blob hash: ' + asset['id'])
    return assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', action='append', default=[], help='Asset ID; repeat to select several')
    parser.add_argument('--retries', type=int, default=4)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.retries <= 20 or not 1 <= args.workers <= 8:
        parser.error('retries must be 1–20; workers must be 1–8')
    assets = load_manifest()
    if set(args.only) - {item['id'] for item in assets}:
        parser.error('Unknown asset ID')
    selected = [item for item in assets if not args.only or item['id'] in args.only]
    if args.dry_run:
        print(json.dumps(selected, ensure_ascii=False, indent=2))
        return 0
    DEST.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(lambda item: fetch(item, args.retries), selected))
    for item in results:
        print(item['id'] + ': ' + item['status'] + (' — ' + item['error'] if 'error' in item else ''))
    report = {'manifest': 'library/downloads.json', 'results': results}
    (DEST / 'download-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    failures = sum(item['status'] == 'failed' for item in results)
    print('Curated assets: %d verified, %d failed' % (len(results) - failures, failures))
    return 1 if failures else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
