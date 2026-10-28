"""Behavioral tests; all HTTP/downloads mocked and all state in temporary roots."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import stat
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

SPEC = importlib.util.spec_from_file_location("seed3d_batch", Path(__file__).resolve().parents[1] / "scripts/seed3d-batch.py")
batch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(batch)


def glb_bytes(model=None):
    raw = json.dumps(model or {"asset": {"version": "2.0"}}).encode()
    raw += b" " * ((-len(raw)) % 4)
    return struct.pack("<4sIIII", b"glTF", 2, len(raw) + 20, len(raw), 0x4E4F534A) + raw


class Seed3DBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        reference = self.root / "assets/reference.png"
        reference.parent.mkdir()
        reference.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 960, 960) + b"actual-reference-test")
        self.plan = {"model": batch.MODEL, "budget": {"declared_free_tokens": 2000000, "batch_limit_tokens": 150000,
                     "per_success_tokens": 30000, "account_remaining_verified": False}, "jobs": []}
        for i in range(5):
            self.plan["jobs"].append({"id": "job-%d" % i, "character_id": "naiwa", "source_asset_id": "source",
                "reference_path": "assets/reference.png", "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
                "subdivision_level": "high", "file_format": "glb", "version": "v1", "license_status": "local_only", "notes": "reviewed"})
        self.write_plan()
        self.key = "ark-11111111-2222-3333-4444-555555555555-abcdef"
        self.http = Mock(return_value={"id": "task-0"})
        self.control = batch.Controller(self.root, http=self.http, key_provider=lambda: self.key)

    def tearDown(self):
        self.temp.cleanup()

    def write_plan(self):
        target = self.root / "library/seed3d-plan.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(self.plan))

    def ledger(self):
        return json.loads((self.root / "production/seed3d/usage-ledger.json").read_text())

    def response(self, status="succeeded", usage=30000, **kwargs):
        result = {"id": "task-0", "model": batch.MODEL, "status": status,
                  "fileformat": "glb", "subdivisionlevel": "high", **kwargs}
        if usage is not None:
            result["usage"] = {"completion_tokens": usage, "total_tokens": usage}
        return result

    def test_reservation_is_durable_before_post_and_reference_is_attached(self):
        def send(method, task, payload, key):
            self.assertEqual(self.ledger()["entries"][0]["reserved_tokens"], 30000)
            self.assertEqual(method, "POST")
            self.assertTrue(payload["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"))
            self.assertEqual(payload["content"][0]["text"], "--subdivisionlevel high --fileformat glb")
            return {"id": "task-0"}
        self.control.http = Mock(side_effect=send)
        self.control.submit("job-0")
        self.assertEqual(self.control.http.call_count, 1)

    def test_duplicate_job_never_sends_another_post(self):
        self.control.submit("job-0")
        with self.assertRaises(batch.BatchError):
            self.control.submit("job-0")
        self.assertEqual(self.http.call_count, 1)

    def test_timeout_preserves_reservation_and_blocks_retry(self):
        self.http.side_effect = TimeoutError(self.key)
        with self.assertRaises(batch.BatchError):
            self.control.submit("job-0")
        entry = self.ledger()["entries"][0]
        self.assertEqual(entry["status"], "submission_uncertain")
        self.assertEqual(entry["reserved_tokens"], 30000)
        with self.assertRaises(batch.BatchError):
            self.control.submit("job-0")
        self.assertEqual(self.http.call_count, 1)
        self.control.adopt("job-0", "recovered-task")
        self.assertEqual(self.ledger()["entries"][0]["task_id"], "recovered-task")

    def test_budget_ceiling_blocks_before_post(self):
        self.plan["budget"]["batch_limit_tokens"] = 30000
        self.write_plan()
        self.control.submit("job-0")
        with self.assertRaises(batch.BatchError):
            self.control.submit("job-1")
        self.assertEqual(self.http.call_count, 1)

    def test_global_ceiling_cannot_be_increased_by_plan(self):
        self.plan["budget"]["batch_limit_tokens"] = 180000
        self.write_plan()
        with self.assertRaises(batch.BatchError):
            self.control.submit("job-0")
        self.http.assert_not_called()

    def test_maximum_five_attempts_even_if_prior_jobs_fail(self):
        self.http.side_effect = [{"id": "task-%d" % i} for i in range(5)]
        for i in range(5):
            self.control.submit("job-%d" % i)
        self.assertEqual(self.control.status()["submission_slots_used"], 5)
        self.plan["jobs"][0]["id"] = "new-job"
        self.write_plan()
        with self.assertRaises(batch.BatchError):
            self.control.submit("new-job")
        self.assertEqual(self.http.call_count, 5)

    def test_adopt_is_offline_idempotent_and_preserves_unknown_data(self):
        path = self.root / "production/seed3d/usage-ledger.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"model": batch.MODEL, "root_note": "keep", "entries": [{"job_id": "job-0", "task_id": "task-0",
            "status": "submitted", "reserved_tokens": 30000, "reported_usage_tokens": None, "request_sha256": "actual-wire-digest", "custom": "keep"}]}))
        self.control.adopt("job-0", "task-0")
        self.http.assert_not_called()
        self.assertEqual(self.ledger()["entries"][0]["request_sha256"], "actual-wire-digest")
        self.http.return_value = self.response()
        self.control.sync("job-0")
        self.assertEqual(self.ledger()["root_note"], "keep")
        self.assertEqual(self.ledger()["entries"][0]["custom"], "keep")

    def test_same_task_cannot_be_adopted_across_jobs(self):
        self.control.adopt("job-0", "task-0")
        with self.assertRaises(batch.BatchError):
            self.control.adopt("job-1", "task-0")
        self.assertEqual(len(self.ledger()["entries"]), 1)

    def test_success_usage_and_failed_accounting(self):
        self.control.adopt("job-0", "task-0")
        self.http.return_value = self.response()
        self.control.sync("job-0")
        summary = self.control.status()
        self.assertEqual(summary["batch_accounted_tokens"], 30000)
        self.assertEqual(summary["reserved_or_estimated_tokens"], 0)
        self.assertFalse(summary["account_remaining_verified"])
        self.control.adopt("job-1", "task-1")
        self.http.return_value = {"id": "task-1", "status": "failed"}
        self.control.sync("job-1")
        self.assertEqual(self.control.status()["batch_accounted_tokens"], 30000)
        self.assertEqual(self.ledger()["entries"][1]["reserved_tokens"], 0)

    def test_missing_success_usage_is_explicit_estimate(self):
        self.control.adopt("job-0", "task-0")
        self.http.return_value = self.response(usage=None)
        self.control.sync("job-0")
        entry = self.ledger()["entries"][0]
        self.assertEqual(entry["usage_basis"], "estimated_official_fixed_success")
        self.assertIsNone(entry["reported_usage_tokens"])
        self.assertEqual(self.control.status()["batch_accounted_tokens"], 30000)

    def test_unexpected_usage_stops_new_submissions(self):
        self.control.adopt("job-0", "task-0")
        self.http.return_value = self.response(usage=31000)
        self.control.sync("job-0")
        with self.assertRaises(batch.BatchError):
            self.control.submit("job-1")
        self.assertEqual(self.http.call_count, 1)

    def test_later_status_does_not_discard_reported_terminal_evidence(self):
        self.control.adopt("job-0", "task-0")
        self.http.return_value = self.response()
        self.control.sync("job-0")
        self.http.return_value = self.response(usage=None)
        self.control.sync("job-0")
        self.assertEqual(self.ledger()["entries"][0]["reported_usage_tokens"], 30000)
        self.http.return_value = self.response(status="failed", usage=0)
        with self.assertRaises(batch.BatchError):
            self.control.sync("job-0")
        self.assertEqual(self.control.status()["batch_accounted_tokens"], 30000)

    def test_network_query_failure_does_not_release_or_resubmit(self):
        self.control.adopt("job-0", "task-0")
        self.http.side_effect = TimeoutError(self.key)
        with self.assertRaises(batch.BatchError):
            self.control.sync("job-0")
        self.assertEqual(self.control.status()["batch_accounted_tokens"], 30000)
        self.assertEqual(self.http.call_args[0][0], "GET")

    def test_secrets_not_written_and_official_signed_url_remains_private(self):
        url = "https://ark-content-generation-cn-beijing.tos-cn-beijing.volces.com/x?signature=signed"
        self.http.return_value = {"id": "task-0", "echo": self.key, "Authorization": "Bearer " + self.key}
        self.control.submit("job-0")
        self.http.return_value = self.response(content={"file_url": url}, echoed_key=self.key)
        self.control.sync("job-0")
        for path in self.root.rglob("*.json"):
            self.assertNotIn(self.key, path.read_text())
        self.assertNotIn(url, json.dumps(self.ledger()))
        private = json.loads(self.control.raw_path("job-0").read_text())
        self.assertEqual(private["content"]["file_url"], url)
        self.assertNotIn("signed", json.dumps(self.control.status()))

    def test_main_sanitizes_errors(self):
        output = io.StringIO()
        with patch.object(batch.Controller, "status", side_effect=batch.BatchError("Bearer " + self.key)), contextlib.redirect_stderr(output):
            self.assertEqual(batch.main(["--root", str(self.root), "status"]), 1)
        self.assertNotIn(self.key, output.getvalue())

    def test_changed_reference_cannot_create_task(self):
        (self.root / "assets/reference.png").write_bytes(b"changed")
        with self.assertRaises(batch.BatchError):
            self.control.submit("job-0")
        self.http.assert_not_called()
        self.assertFalse((self.root / "production/seed3d/usage-ledger.json").exists())

    def make_zip(self, name, entries):
        archive = self.root / name
        with zipfile.ZipFile(archive, "w") as bundle:
            for path, value in entries.items():
                bundle.writestr(path, value)
        return archive

    def test_zip_traversal_and_windows_escape_rejected(self):
        for i, unsafe in enumerate(("../outside.obj", "/absolute.obj", "C:/outside.obj", "..\\outside.obj")):
            archive = self.make_zip("bad-%d.zip" % i, {unsafe: "v 0 0 0"})
            with self.assertRaises(batch.BatchError):
                batch.extract_archive(archive, self.root / ("extract-%d" % i))

    def test_zip_symlink_rejected(self):
        archive = self.root / "symlink.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            info = zipfile.ZipInfo("model.obj")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            bundle.writestr(info, "/outside")
        with self.assertRaises(batch.BatchError):
            batch.extract_archive(archive, self.root / "unpacked")

    def test_mesh_material_cannot_escape_bundle(self):
        archive = self.make_zip("external.zip", {"model.obj": "mtllib material.mtl\nv 0 0 0", "material.mtl": "map_Kd ../../outside.png"})
        with self.assertRaises(batch.BatchError):
            batch.extract_archive(archive, self.root / "external")

    def test_obj_include_command_rejected(self):
        archive = self.make_zip("command.zip", {"model.obj": "call ../../outside.obj\nv 0 0 0"})
        with self.assertRaises(batch.BatchError):
            batch.extract_archive(archive, self.root / "command")

    def test_glb_cannot_fetch_external_texture(self):
        archive = self.make_zip("remote.zip", {"model.glb": glb_bytes({"asset": {"version": "2.0"}, "images": [{"uri": "https://example.org/x.png"}]})})
        with self.assertRaises(batch.BatchError):
            batch.extract_archive(archive, self.root / "remote")

    def test_download_retains_archive_hashes_and_is_idempotent(self):
        archive = self.make_zip("valid.zip", {"nested/model.glb": glb_bytes(), "nested/info.txt": "source"})
        self.control.adopt("job-0", "task-0")
        self.http.return_value = self.response(content={"file_url": "https://example.volces.com/output.zip?signature=private"})
        self.control.sync("job-0")
        self.control.downloader = Mock(side_effect=lambda url, target: shutil.copyfile(archive, target))
        result = self.control.download("job-0")
        self.assertEqual(result["status"], "downloaded")
        manifest = json.loads((self.root / result["manifest"]).read_text())
        self.assertIn("source.zip", [x["path"] for x in manifest["files"]])
        self.assertEqual(manifest["meshes"], ["files/nested/model.glb"])
        self.assertEqual(self.control.download("job-0")["status"], "already_downloaded")
        self.assertEqual(self.control.downloader.call_count, 1)

    def test_http_and_nonofficial_download_urls_rejected(self):
        for url in ("http://example.volces.com/x", "https://example.org/x", "https://example.volces.com@evil.example/x"):
            with self.assertRaises(batch.BatchError):
                batch.allowed_url(url)


if __name__ == "__main__":
    unittest.main()
