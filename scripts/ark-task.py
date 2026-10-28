#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Explicit Ark task submit/query. Credentials stay in env or an external file."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.request
import urllib.error

BASE = 'https://ark.cn-beijing.volces.com/api/v3'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('submit')
    create.add_argument('--request', required=True)
    create.add_argument('--record', required=True)
    query = sub.add_parser('get')
    query.add_argument('task_id')
    query.add_argument('--record', required=True)
    args = parser.parse_args()
    key = os.environ.get('ARK_API_KEY')
    if not key and os.environ.get('ARK_API_KEY_FILE'):
        key = Path(os.environ['ARK_API_KEY_FILE']).read_text().strip()
    if not key:
        parser.error('Set ARK_API_KEY or ARK_API_KEY_FILE; never put a key in the request JSON')
    data = None
    url = BASE + '/contents/generations/tasks'
    if args.command == 'submit':
        payload = json.loads(Path(args.request).read_text())
        data = json.dumps(payload, ensure_ascii=False).encode()
    else:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', args.task_id):
            parser.error('Invalid task ID')
        url += '/' + args.task_id
    request = urllib.request.Request(url, data=data, headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=55) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        text = exc.read(12000).decode('utf-8', 'replace').replace(key, '[REDACTED]')
        try: error = json.loads(text)
        except ValueError: error = {'message': text}
        body = {'http_status': exc.code, 'error': error}
    except Exception as exc:
        # No automatic POST retry: an ambiguous timeout might already have created a billable task.
        body = {'network_error': str(exc).replace(key, '[REDACTED]'), 'automatic_retry': False}
    path = Path(args.record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: body[k] for k in ['id', 'status', 'model', 'http_status', 'error', 'network_error'] if k in body}, ensure_ascii=False))
    return 1 if body.get('error') or body.get('network_error') else 0


if __name__ == '__main__':
    sys.exit(main())
