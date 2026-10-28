"""Pixel-only preparation contracts, using generated ordinary test shapes."""
import copy
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

from PIL import Image


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare-seed3d-references.py"
SPEC = importlib.util.spec_from_file_location("prepare_seed3d_refs", SCRIPT)
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()

    def fixture(self):
        path = self.root / "assets/source.png"
        path.parent.mkdir(parents=True)
        Image.new("RGB", (40, 20), "red").save(path)
        return {
            "schema_version": 1, "canvas_size": 768, "margin_fraction": 0.12,
            "inputs": [{"id": "fixture", "source_path": "assets/source.png",
                        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "output_path": "assets/private/seed3d/references/fixture.png"}],
        }

    def test_changed_source_hash_refuses_before_outputs_exist(self):
        manifest = self.fixture()
        Image.new("RGB", (40, 20), "blue").save(self.root / "assets/source.png")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            PREPARE.prepare_records(self.root, manifest)
        self.assertFalse((self.root / "assets/private").exists())

    def test_hidden_rgb_never_leaks_through_transparent_pixels(self):
        source = Image.new("RGBA", (2, 1), (0, 255, 0, 0))
        source.putpixel((1, 0), (255, 0, 0, 255))
        output, _ = PREPARE.prepare_image(source, canvas_size=300)
        self.assertEqual(output.mode, "RGB")
        for red, green, blue in output.getdata():
            self.assertEqual(red, 255)
            self.assertEqual(green, blue)

    def test_uniform_scale_preserves_aspect_and_white_margin(self):
        output, evidence = PREPARE.prepare_image(Image.new("RGB", (400, 200), "red"))
        self.assertEqual(evidence["resized_dimensions"], [584, 292])
        self.assertEqual(evidence["paste_origin"], [92, 238])
        self.assertEqual(output.getpixel((91, 384)), (255, 255, 255))
        self.assertEqual(output.getpixel((92, 238)), (255, 0, 0))
        self.assertEqual(output.getpixel((675, 529)), (255, 0, 0))
        self.assertEqual(output.getpixel((676, 530)), (255, 255, 255))

    def test_crop_validation_rejects_outside_empty_and_noninteger_bounds(self):
        source = Image.new("RGB", (40, 20), "red")
        for crop in [[-1, 0, 30, 20], [0, 0, 41, 20], [0, 0, 40, 21],
                     [10, 0, 10, 20], [0, 20, 40, 0], [0, 0, 40],
                     [False, 0, 40, 20], [0.0, 0, 40, 20]]:
            with self.subTest(crop=crop), self.assertRaisesRegex(ValueError, "crop"):
                PREPARE.prepare_image(source, crop)

    def test_single_cell_crop_excludes_neighboring_sprite(self):
        source = Image.new("RGB", (80, 20), "blue")
        source.paste("red", (0, 0, 40, 20))
        output, evidence = PREPARE.prepare_image(source, [0, 0, 40, 20])
        self.assertEqual(evidence["crop_dimensions"], [40, 20])
        self.assertFalse(any(blue > red for red, _, blue in output.getdata()))

    def test_paths_refuse_parent_absolute_and_symlink_escape(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        (self.root / "escape").symlink_to(outside, target_is_directory=True)
        for path in ["../outside/x.png", str(outside / "x.png"), "escape/x.png", "a\\b.png"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                PREPARE.confined_path(self.root, path)

    def test_destination_scope_and_duplicate_destinations_are_rejected(self):
        manifest = self.fixture()
        for destination in ["library/danger.png", "assets/private/seed3d/references/x.jpg"]:
            manifest["inputs"][0]["output_path"] = destination
            with self.assertRaisesRegex(ValueError, "output must"):
                PREPARE.prepare_records(self.root, manifest)
        manifest["inputs"][0]["output_path"] = "assets/private/seed3d/references/x.png"
        second = copy.deepcopy(manifest["inputs"][0])
        second["id"] = "second"
        manifest["inputs"].append(second)
        with self.assertRaisesRegex(ValueError, "duplicate output"):
            PREPARE.prepare_records(self.root, manifest)

    def test_output_hash_and_review_are_bound_to_actual_prepared_bytes(self):
        manifest = self.fixture()
        prepared, outputs = PREPARE.prepare_records(self.root, manifest)
        record = prepared["inputs"][0]
        self.assertEqual(record["prepared_sha256"], hashlib.sha256(outputs[0][1]).hexdigest())
        with Image.open(io.BytesIO(outputs[0][1])) as output:
            self.assertEqual(output.size, (768, 768))
        record["visual_review"] = {"status": "visual_checked", "sha256": record["prepared_sha256"]}
        repeated, _ = PREPARE.prepare_records(self.root, prepared)
        self.assertEqual(repeated["inputs"][0]["visual_review"]["status"], "visual_checked")
        repeated["margin_fraction"] = 0.15
        changed, _ = PREPARE.prepare_records(self.root, repeated)
        self.assertEqual(changed["inputs"][0]["visual_review"]["status"], "needs_review_changed_hash")


if __name__ == "__main__":
    unittest.main()
