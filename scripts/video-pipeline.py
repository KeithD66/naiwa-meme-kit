#!/usr/bin/env python3
"""List configured video routes or plan a reference-bound shot offline."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def project_path(value):
    path = Path(value)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Path must stay inside the project')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    providers = commands.add_parser('providers')
    providers.add_argument('--tier', choices=['draft', 'standard', 'polish'])
    plan = commands.add_parser('plan')
    plan.add_argument('--request', required=True)
    plan.add_argument('--tier', choices=['draft', 'standard', 'polish'])
    plan.add_argument('--resolution')
    plan.add_argument('--output', help='Optional JSON report in production/, outputs/ or assets/private/')
    args = parser.parse_args()
    try:
        config = json.loads((ROOT / 'library/video-providers.json').read_text())
        if args.command == 'providers':
            tiers = {args.tier: config['tiers'][args.tier]} if args.tier else config['tiers']
            ids = {value for route in tiers.values() for value in route}
            result = {'tiers': tiers, 'providers': [p for p in config['providers'] if p['id'] in ids],
                      'api_calls': 0, 'tier_basis': config['tier_basis']}
        else:
            from video_pipeline import VideoPipeline, VideoRequest
            request_path = project_path(args.request)
            request = VideoRequest.from_dict(json.loads(request_path.read_text()))
            if args.tier:
                request = replace(request, tier=args.tier)
            if args.resolution:
                request = replace(request, resolution=args.resolution)
            result = VideoPipeline(root=ROOT, config=config).plan(request)
            if args.output:
                output = project_path(args.output)
                allowed = [ROOT / name for name in ('production', 'outputs', 'assets/private')]
                if not any(output.is_relative_to(base) for base in allowed) or output.suffix != '.json':
                    raise ValueError('Output must be a JSON report in production/, outputs/ or assets/private/')
                if output == request_path or output.exists():
                    raise ValueError('Output already exists or would overwrite the request; use a new report path')
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open('x', encoding='utf-8') as handle:
                    json.dump(result, handle, ensure_ascii=False, indent=2)
                    handle.write('\n')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'Planning failed: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
