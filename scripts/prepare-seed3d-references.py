#!/usr/bin/env python3
"""Prepare hash-pinned Seed3D inputs with crop/alpha/resize/padding only.

Run from the project root:
    python3 scripts/prepare-seed3d-references.py

Recipes and preparation evidence live in library/seed3d-inputs.json. This
script never calls a model, repairs a silhouette, or invents missing pixels.
"""
import argparse
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = "library/seed3d-inputs.json"
OUTPUT_SCOPE = Path("assets/private/seed3d/references")


def confined_path(root, relative):
    """Reject traversal, absolute paths, and symlink escapes before any write."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("path must be a nonempty project-relative POSIX path")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("path must remain inside the project")
    root = Path(root).resolve()
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("path resolves outside the project")
    return resolved


def checked_crop(crop, dimensions):
    width, height = dimensions
    if crop is None:
        return (0, 0, width, height)
    if (not isinstance(crop, (list, tuple)) or len(crop) != 4
            or any(type(value) is not int for value in crop)):
        raise ValueError("crop must contain four integer pixel coordinates")
    left, top, right, bottom = crop
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("crop is empty or outside source image bounds")
    return tuple(crop)


def prepare_image(source, crop=None, canvas_size=768, margin_fraction=0.12):
    if type(canvas_size) is not int or not 300 <= canvas_size <= 6000:
        raise ValueError("canvas size must be an integer between 300 and 6000")
    if (isinstance(margin_fraction, bool)
            or not isinstance(margin_fraction, (int, float))
            or not math.isfinite(margin_fraction)
            or not 0 <= margin_fraction < 0.45):
        raise ValueError("margin fraction must be finite and between 0 and 0.45")
    bounds = checked_crop(crop, source.size)
    fragment = source.crop(bounds).convert("RGBA")
    # Composite before resizing: RGB values hidden behind alpha=0 must never
    # bleed into the input through interpolation or direct RGB conversion.
    white = Image.new("RGBA", fragment.size, (255, 255, 255, 255))
    flattened = Image.alpha_composite(white, fragment).convert("RGB")
    margin_px = round(canvas_size * margin_fraction)
    fit_size = canvas_size - 2 * margin_px
    scale = min(fit_size / fragment.width, fit_size / fragment.height)
    resized_size = (max(1, round(fragment.width * scale)),
                    max(1, round(fragment.height * scale)))
    resized = flattened.resize(resized_size, Image.Resampling.LANCZOS)
    origin = ((canvas_size - resized.width) // 2,
              (canvas_size - resized.height) // 2)
    canvas = Image.new("RGB", (canvas_size, canvas_size), "white")
    canvas.paste(resized, origin)
    evidence = {
        "source_dimensions": list(source.size),
        "crop_xyxy": list(bounds),
        "crop_dimensions": list(fragment.size),
        "operations": ["crop_existing_pixels", "alpha_composite_on_white",
                       "uniform_scale_lanczos", "center_on_white_canvas"],
        "canvas_dimensions": [canvas_size, canvas_size],
        "margin_fraction": margin_fraction,
        "minimum_canvas_margin_px": margin_px,
        "scale_factor": scale,
        "resized_dimensions": list(resized_size),
        "paste_origin": list(origin),
        "upscaled": scale > 1,
        "upscale_adds_source_detail": False,
        "generated_or_outpainted_pixels": False,
        "warning": ("Low-resolution source enlarged; no detail recovered."
                    if min(fragment.size) < 300 else None),
    }
    return canvas, evidence


def prepare_records(root, manifest, only_ids=None):
    """Validate/render all selected records before creating any output file."""
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported input manifest schema")
    records = manifest.get("inputs")
    if not isinstance(records, list) or not records:
        raise ValueError("manifest requires a nonempty inputs list")
    ids = [record.get("id") for record in records]
    if any(not isinstance(item, str) or not item for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("input IDs must be nonempty and unique")
    selected = set(only_ids or ids)
    if selected - set(ids):
        raise ValueError("unknown input ID: " + ", ".join(sorted(selected - set(ids))))
    result = copy.deepcopy(manifest)
    outputs = []
    destinations = set()
    for record in result["inputs"]:
        output_path = confined_path(root, record["output_path"])
        scope = confined_path(root, str(OUTPUT_SCOPE))
        if scope != Path(root).resolve() / OUTPUT_SCOPE:
            raise ValueError("output scope must not redirect through a symlink")
        if not output_path.is_relative_to(scope) or output_path.suffix.lower() != ".png":
            raise ValueError("output must be a PNG inside " + str(OUTPUT_SCOPE))
        if output_path in destinations:
            raise ValueError("duplicate output destination")
        destinations.add(output_path)
        if record["id"] not in selected:
            continue
        source_path = confined_path(root, record["source_path"])
        content = source_path.read_bytes()
        expected = record.get("source_sha256", "")
        digest = hashlib.sha256(content).hexdigest()
        if not isinstance(expected, str) or len(expected) != 64 or digest != expected:
            raise ValueError("source SHA256 mismatch for " + record["id"])
        with Image.open(io.BytesIO(content)) as source:
            image, evidence = prepare_image(
                source, record.get("crop_xyxy"),
                manifest.get("canvas_size", 768),
                manifest.get("margin_fraction", 0.12))
        stream = io.BytesIO()
        image.save(stream, format="PNG", compress_level=9)
        png = stream.getvalue()
        if len(png) >= 30 * 1024 * 1024:
            raise ValueError("prepared PNG exceeds 30 MiB")
        record["prepared_sha256"] = hashlib.sha256(png).hexdigest()
        record["prepared_bytes"] = len(png)
        record["preparation"] = evidence
        record["api_image_constraints"] = {
            "width_and_height_300_to_6000": True,
            "aspect_ratio_between_0_4_and_2_5": True,
            "under_30_mib": True,
        }
        # A rerun preserves manual review only for byte-identical output.
        review = record.get("visual_review", {})
        if review and review.get("sha256") != record["prepared_sha256"]:
            record["visual_review"] = {"status": "needs_review_changed_hash"}
        outputs.append((output_path, png))
    return result, outputs


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(data)
        pending = Path(temporary.name)
    try:
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST,
                        help="project-relative recipe/evidence JSON")
    parser.add_argument("--only", action="append", dest="only_ids",
                        help="prepare this input ID; repeat for several")
    args = parser.parse_args(argv)
    manifest_path = confined_path(ROOT, args.manifest)
    manifest = json.loads(manifest_path.read_text())
    prepared, outputs = prepare_records(ROOT, manifest, args.only_ids)
    for path, content in outputs:
        atomic_write(path, content)
    atomic_write(manifest_path, (json.dumps(prepared, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"prepared": len(outputs), "manifest": args.manifest,
                      "outputs": [str(path.relative_to(ROOT)) for path, _ in outputs]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
