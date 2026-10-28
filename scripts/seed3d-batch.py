#!/usr/bin/env python3
"""Bounded, resumable Seed3D jobs. This ledger measures this batch, not account balance."""
import argparse
import base64
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import struct
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

MODEL = "doubao-seed3d-2-0-260328"
BASE = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
PER_JOB = 30000
MAX_JOBS = 5
MAX_BUDGET = 150000
MAX_DOWNLOAD = 512 * 1024 * 1024
MAX_EXPANDED = 1024 * 1024 * 1024
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,160}\Z")
SECRET = re.compile(r"ark-[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}(?:-[0-9a-f]{3,})?|Bearer\s+[^\s\"']+", re.I)


class BatchError(Exception):
    """Errors deliberately contain no remote response or credential text."""


class HTTPFailure(BatchError):
    def __init__(self, code):
        self.code = code
        super().__init__("Ark returned HTTP %s; no automatic submission retry" % code)


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def clean(value, key=None):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in {"authorization", "api_key", "apikey", "access_key", "secret_key"}
                    else clean(v, key)) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(x, key) for x in value]
    if isinstance(value, str):
        return SECRET.sub("[REDACTED]", value.replace(key, "[REDACTED]") if key else value)
    return value


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def within(path, base):
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def atomic_json(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".seed3d-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(clean(body), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def get_key():
    key = os.environ.get("ARK_API_KEY")
    if not key and os.environ.get("ARK_API_KEY_FILE"):
        try:
            key = Path(os.environ["ARK_API_KEY_FILE"]).read_text().strip()
        except OSError:
            raise BatchError("Cannot read ARK_API_KEY_FILE") from None
    if not key or "\n" in key or "\r" in key:
        raise BatchError("Set ARK_API_KEY or ARK_API_KEY_FILE outside the repository")
    return key


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api_json(method, task_id, payload, key):
    url = BASE + ("/" + task_id if task_id else "")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method,
                                    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=55) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise BatchError("Ark response exceeds size limit")
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise BatchError("Ark returned an invalid response shape")
            return body
    except urllib.error.HTTPError as error:
        raise HTTPFailure(error.code) from None


def allowed_url(url):
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not any(host == suffix or host.endswith("." + suffix)
                       for suffix in ("volces.com", "volcengine.com", "byteimg.com", "bytedance.com", "bytednsdoc.com"))):
        raise BatchError("Output URL must use HTTPS on an expected official media host")


class DownloadRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_url(url, destination):
    allowed_url(url)
    try:
        with urllib.request.build_opener(DownloadRedirect()).open(url, timeout=55) as response:
            allowed_url(response.geturl())
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_DOWNLOAD:
                raise BatchError("Output archive exceeds download limit")
            total = 0
            with open(destination, "xb") as handle:
                os.chmod(destination, 0o600)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_DOWNLOAD:
                        raise BatchError("Output archive exceeds download limit")
                    handle.write(chunk)
    except BatchError:
        raise
    except Exception:
        raise BatchError("Archive download failed; saved task can be queried again without resubmission") from None


def dependency_path(value, parent, base):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme == "data":
        return
    decoded = urllib.parse.unquote(value)
    path = PurePosixPath(decoded)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in decoded
            or path.is_absolute() or ".." in path.parts or ":" in decoded):
        raise BatchError("Mesh dependency escapes its downloaded bundle")
    target = (parent / decoded).resolve()
    if not within(target, base.resolve()) or not target.is_file() or target.is_symlink():
        raise BatchError("Mesh dependency is missing or outside its downloaded bundle")


def check_dependencies(base):
    """Validate OBJ/MTL and glTF URI references before any downstream importer sees them."""
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in (".obj", ".mtl"):
            if path.stat().st_size > MAX_DOWNLOAD:
                raise BatchError("Text mesh exceeds inspection limit")
            with path.open(encoding="utf-8", errors="strict") as handle:
                for line in handle:
                    if len(line) > 1024 * 1024:
                        raise BatchError("Text mesh line exceeds inspection limit")
                    tokens = shlex.split(line, comments=True)
                    if not tokens:
                        continue
                    command = tokens[0].lower()
                    if command in {"call", "csh"}:
                        raise BatchError("OBJ command/include directives are not permitted")
                    refs = tokens[1:] if command == "mtllib" else ([tokens[-1]] if command.startswith("map_") or command in {"bump", "disp", "decal", "refl", "norm"} else [])
                    for ref in refs:
                        dependency_path(ref, path.parent, base)
        elif suffix in (".glb", ".gltf"):
            if suffix == ".gltf":
                if path.stat().st_size > 16 * 1024 * 1024:
                    raise BatchError("glTF JSON exceeds inspection limit")
                model = json.loads(path.read_text())
            else:
                with path.open("rb") as handle:
                    header = handle.read(20)
                    if len(header) != 20:
                        raise BatchError("Invalid GLB header")
                    magic, version, size, chunk_size, chunk_type = struct.unpack("<4sIIII", header)
                    if magic != b"glTF" or version != 2 or size != path.stat().st_size or chunk_type != 0x4E4F534A or chunk_size > 16 * 1024 * 1024:
                        raise BatchError("Invalid GLB header or JSON chunk")
                    model = json.loads(handle.read(chunk_size).decode("utf-8"))
            for group in ("buffers", "images"):
                for item in model.get(group, []):
                    if "uri" in item:
                        dependency_path(item["uri"], path.parent, base)


def extract_archive(archive, destination):
    """Bounded manual extraction: no traversal, symlinks, overwrite, or external mesh URIs."""
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(archive) as bundle:
            infos = bundle.infolist()
            if not infos or len(infos) > 128 or sum(x.file_size for x in infos) > MAX_EXPANDED:
                raise BatchError("Archive entry count or expanded size exceeds limit")
            names = set()
            for info in infos:
                name = info.filename
                relative = PurePosixPath(name)
                mode = info.external_attr >> 16
                kind = stat.S_IFMT(mode)
                if (not name or "\\" in name or ":" in name or "\x00" in name or relative.is_absolute()
                        or ".." in relative.parts or name in names or kind not in (0, stat.S_IFREG, stat.S_IFDIR)
                        or info.flag_bits & 1 or info.file_size > MAX_DOWNLOAD
                        or info.file_size > max(info.compress_size, 1) * 1000):
                    raise BatchError("Unsafe archive entry")
                names.add(name)
                target = destination.joinpath(*relative.parts)
                if not within(target.resolve(), destination.resolve()):
                    raise BatchError("Archive path escapes destination")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if target.suffix.lower() in {".sh", ".py", ".exe", ".app", ".dylib", ".so", ".command", ".bat", ".js"}:
                    raise BatchError("Archive contains executable content")
                target.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with bundle.open(info) as source, open(target, "xb") as output:
                    os.chmod(target, 0o600)
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > info.file_size or written > MAX_DOWNLOAD:
                            raise BatchError("Archive entry expands beyond declared size")
                        output.write(chunk)
                if written != info.file_size:
                    raise BatchError("Incomplete archive entry")
        check_dependencies(destination)
        meshes = [p for p in destination.rglob("*") if p.suffix.lower() in {".glb", ".obj"} and p.is_file()]
        if not meshes:
            raise BatchError("Archive contains no GLB or OBJ mesh for this pipeline")
        return meshes
    except BatchError:
        raise
    except Exception:
        raise BatchError("Archive extraction or dependency validation failed") from None


class Controller:
    def __init__(self, root, plan="library/seed3d-plan.json", ledger="production/seed3d/usage-ledger.json",
                 http=api_json, downloader=download_url, key_provider=get_key):
        self.root = Path(root).resolve()
        self.plan_path = self.local_path(plan)
        self.ledger_path = self.local_path(ledger)
        self.http = http
        self.downloader = downloader
        self.key_provider = key_provider

    def local_path(self, value):
        path = Path(value)
        if not path.is_absolute():
            path = self.root / path
        if not within(path.resolve(), self.root):
            raise BatchError("Path must stay within the project root")
        for part in [path] + list(path.parents):
            if part == self.root:
                break
            if part.is_symlink():
                raise BatchError("Project paths must not use symlinks")
        return path

    @contextlib.contextmanager
    def locked(self):
        lock_path = self.local_path(str(self.ledger_path) + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a") as handle:
            os.chmod(lock_path, 0o600)
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise BatchError("Seed3D controller is busy; no duplicate request was sent") from None
            try:
                self.load()
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def load(self):
        try:
            self.plan = json.loads(self.plan_path.read_text())
            self.ledger = json.loads(self.ledger_path.read_text()) if self.ledger_path.exists() else {
                "schema_version": 1, "model": MODEL, "budget": self.plan.get("budget", {}), "entries": []}
        except (OSError, ValueError):
            raise BatchError("Cannot read valid plan/ledger JSON") from None
        if self.plan.get("model") != MODEL or self.ledger.get("model", MODEL) != MODEL:
            raise BatchError("Plan and ledger must use the fixed Seed3D 2.0 model")
        budget = self.plan.get("budget", {})
        if (budget.get("per_success_tokens") != PER_JOB or type(budget.get("batch_limit_tokens")) is not int
                or not PER_JOB <= budget["batch_limit_tokens"] <= MAX_BUDGET
                or type(budget.get("declared_free_tokens")) is not int
                or budget["declared_free_tokens"] < budget["batch_limit_tokens"]):
            raise BatchError("Plan must enforce the fixed 30000/job and at most 150000 batch budget")
        self.limit = budget["batch_limit_tokens"]
        self.jobs = {}
        for job in self.plan.get("jobs", []):
            job_id = job.get("id", "")
            if not IDENTIFIER.fullmatch(job_id) or job_id in self.jobs:
                raise BatchError("Invalid or duplicate plan job ID")
            if job.get("subdivision_level") not in {"high", "medium", "low"} or job.get("file_format") not in {"glb", "obj"}:
                raise BatchError("This bounded importer supports only valid Seed3D levels and GLB/OBJ")
            self.jobs[job_id] = job
        if not self.jobs or len(self.jobs) > MAX_JOBS:
            raise BatchError("Plan must contain 1 to 5 jobs")
        self.entries = self.ledger.get("entries")
        if not isinstance(self.entries, list):
            raise BatchError("Ledger entries must be an array")
        jobs, tasks = set(), set()
        for entry in self.entries:
            job_id, task_id = entry.get("job_id"), entry.get("task_id")
            if not isinstance(job_id, str) or not IDENTIFIER.fullmatch(job_id) or (task_id is not None and (
                    not isinstance(task_id, str) or not IDENTIFIER.fullmatch(task_id))):
                raise BatchError("Ledger contains an invalid job/task ID")
            if job_id in jobs or (task_id and task_id in tasks):
                raise BatchError("Ledger contains a duplicate job/task; resolve audit before proceeding")
            jobs.add(job_id)
            if task_id:
                tasks.add(task_id)
            for field in ("reserved_tokens", "reported_usage_tokens"):
                value = entry.get(field)
                if value is not None and (type(value) is not int or value < 0):
                    raise BatchError("Invalid ledger token count")

    def save(self):
        self.ledger["updated_at"] = utc_now()
        self.ledger.setdefault("model", MODEL)
        self.ledger["account_remaining_verified"] = False
        atomic_json(self.ledger_path, self.ledger)

    def find(self, job_id):
        if job_id not in self.jobs:
            raise BatchError("Unknown plan job")
        return next((e for e in self.entries if e.get("job_id") == job_id), None)

    @staticmethod
    def charged(entry):
        reported = entry.get("reported_usage_tokens")
        return reported if reported is not None else entry.get("reserved_tokens", PER_JOB)

    def reserve(self, job_id):
        if self.find(job_id):
            raise BatchError("Job already exists; use sync/adopt, never resubmit")
        used = sum(self.charged(e) for e in self.entries)
        if any(e.get("usage_anomaly") for e in self.entries):
            raise BatchError("Unexpected reported usage requires review before further submissions")
        if len(self.entries) >= MAX_JOBS or used + PER_JOB > self.limit:
            raise BatchError("Batch request/token limit would be exceeded")
        job = self.jobs[job_id]
        return {"job_id": job_id, "task_id": None, "status": "reserved", "reserved_tokens": PER_JOB,
                "reported_usage_tokens": None, "usage_basis": "reserved_pending_submission", "created_at": utc_now(),
                "character_id": job.get("character_id"), "source_asset_id": job.get("source_asset_id"),
                "reference_sha256": job.get("reference_sha256"), "version": job.get("version"),
                "license_status": job.get("license_status"), "subdivision_level": job["subdivision_level"],
                "file_format": job["file_format"], "model": MODEL}

    def payload(self, job_id):
        job = self.jobs[job_id]
        path = self.local_path(job["reference_path"])
        if not path.is_file() or path.stat().st_size >= 30 * 1024 * 1024:
            raise BatchError("Missing or oversized local reference")
        if sha256(path) != job.get("reference_sha256"):
            raise BatchError("Reference SHA-256 does not match reviewed plan")
        data = path.read_bytes()
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "png"
            width, height = struct.unpack(">II", data[16:24])
        elif data.startswith((b"GIF87a", b"GIF89a")):
            mime = "gif"
            width, height = struct.unpack("<HH", data[6:10])
        elif data.startswith(b"BM") and len(data) >= 26:
            mime = "bmp"
            width, height = struct.unpack("<ii", data[18:26])
            height = abs(height)
        elif data.startswith(b"\xff\xd8"):
            mime = "jpeg"
            width, height = self.jpeg_size(data)
        elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            mime = "webp"
            width, height = self.webp_size(data)
        else:
            raise BatchError("Reference must be PNG/JPEG/WebP/BMP/GIF; convert format without redrawing if needed")
        if not 300 <= width <= 6000 or not 300 <= height <= 6000 or not 0.4 <= width / height <= 2.5:
            raise BatchError("Reference dimensions/aspect ratio exceed official input bounds")
        payload = {"model": MODEL, "content": [
            {"type": "text", "text": "--subdivisionlevel %s --fileformat %s" % (job["subdivision_level"], job["file_format"])},
            {"type": "image_url", "image_url": {"url": "data:image/%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))}}]}
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        if len(encoded) > 64 * 1024 * 1024:
            raise BatchError("Reference request exceeds official body limit")
        return payload, hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def jpeg_size(data):
        offset = 2
        while offset + 4 <= len(data):
            if data[offset] != 255:
                raise BatchError("Invalid JPEG header")
            while offset < len(data) and data[offset] == 255:
                offset += 1
            marker = data[offset]
            offset += 1
            if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
                continue
            length = int.from_bytes(data[offset:offset + 2], "big")
            if length < 2 or offset + length > len(data):
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                return width, height
            offset += length
        raise BatchError("Cannot inspect JPEG dimensions")

    @staticmethod
    def webp_size(data):
        kind = data[12:16]
        if kind == b"VP8X" and len(data) >= 30:
            return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
        if kind == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
            return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
        if kind == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        raise BatchError("Cannot inspect WebP dimensions")

    def raw_path(self, job_id, kind="status"):
        return self.local_path("assets/private/seed3d/tasks/%s/%s.json" % (job_id, kind))

    def submit(self, job_id):
        with self.locked():
            entry = self.reserve(job_id)
            payload, digest = self.payload(job_id)
            key = self.key_provider()
            entry["request_sha256"] = digest
            entry["submission_attempts"] = 1
            self.entries.append(entry)
            self.save()  # Reservation is durable before the only POST attempt.
            try:
                body = self.http("POST", None, payload, key)
                atomic_json(self.raw_path(job_id, "submit"), clean(body, key))
                task_id = body.get("id", "")
                if not isinstance(task_id, str) or not IDENTIFIER.fullmatch(task_id):
                    raise BatchError("Submission returned no valid task ID")
                if any(e is not entry and e.get("task_id") == task_id for e in self.entries):
                    raise BatchError("Submission returned an existing task ID")
                entry.update(task_id=task_id, status="queued", usage_basis="reserved_pending_terminal_status")
                self.save()
                return self.public_entry(entry)
            except Exception as error:
                entry["status"] = "submission_rejected" if isinstance(error, HTTPFailure) and 400 <= error.code < 500 else "submission_uncertain"
                entry["error_kind"] = "http_%d" % error.code if isinstance(error, HTTPFailure) else "network_or_response_failure"
                self.save()
                raise BatchError("Submission unresolved; reservation kept. Do not resubmit. Adopt a recovered task ID, then sync.") from None

    def adopt(self, job_id, task_id):
        if not IDENTIFIER.fullmatch(task_id):
            raise BatchError("Invalid task ID")
        with self.locked():
            entry = self.find(job_id)
            if any(e.get("task_id") == task_id and e.get("job_id") != job_id for e in self.entries):
                raise BatchError("Task ID already belongs to another job")
            if entry and entry.get("task_id") not in (None, "", task_id):
                raise BatchError("Job already belongs to another task")
            if entry and entry.get("task_id") == task_id:
                return self.public_entry(entry)
            if not entry:
                entry = self.reserve(job_id)
                _, digest = self.payload(job_id)
                entry.update(request_sha256=None, planned_request_sha256=digest,
                             submission_attempts=1, request_origin="externally_submitted")
                self.entries.append(entry)
            entry.update(task_id=task_id, status="adopted_pending_sync", adopted=True)
            self.save()
            return self.public_entry(entry)

    def sync(self, job_id):
        with self.locked():
            entry = self.find(job_id)
            if not entry or not entry.get("task_id"):
                raise BatchError("Job has no task ID; adopt a recovered ID before sync")
            key = self.key_provider()
            try:
                body = self.http("GET", entry["task_id"], None, key)
            except Exception:
                raise BatchError("Status query failed; reservation unchanged and no submission sent") from None
            if body.get("id", entry["task_id"]) != entry["task_id"] or body.get("model", MODEL) != MODEL:
                raise BatchError("Status response does not match this task/model")
            status = body.get("status")
            if status not in {"queued", "running", "succeeded", "failed", "cancelled", "expired"}:
                raise BatchError("Status response has no recognized task state")
            previous_status = entry.get("status")
            if previous_status in {"succeeded", "failed", "cancelled"} and status != previous_status:
                raise BatchError("Status contradicts saved terminal evidence; review before changing accounting")
            atomic_json(self.raw_path(job_id), clean(body, key))
            entry["status"] = status
            entry["synced_at"] = utc_now()
            usage = (body.get("usage") or {}).get("completion_tokens")
            if usage is not None and (type(usage) is not int or usage < 0):
                raise BatchError("Status response has invalid usage")
            if status in {"succeeded", "failed", "cancelled", "expired"}:
                if usage is not None:
                    entry.update(reported_usage_tokens=usage, reserved_tokens=0, usage_basis="reported_terminal_usage")
                elif status == "succeeded":
                    if entry.get("reported_usage_tokens") is None:
                        entry.update(reported_usage_tokens=None, reserved_tokens=PER_JOB, usage_basis="estimated_official_fixed_success", estimated_usage_tokens=PER_JOB)
                elif status in {"failed", "cancelled"}:
                    entry.update(reported_usage_tokens=None, reserved_tokens=0, usage_basis="terminal_without_success_no_charge", estimated_usage_tokens=0)
                # Expiration alone does not prove that no successful file was generated.
            if usage is not None:
                entry["usage_anomaly"] = bool((status == "succeeded" and usage != PER_JOB)
                                              or (status in {"failed", "cancelled"} and usage != 0) or usage > PER_JOB)
            entry["returned_file_format"] = body.get("fileformat")
            entry["returned_subdivision_level"] = body.get("subdivisionlevel")
            self.save()
            return self.public_entry(entry)

    def download(self, job_id):
        with self.locked():
            entry = self.find(job_id)
            if not entry or entry.get("status") != "succeeded":
                raise BatchError("Only a synced successful task can be downloaded")
            target = self.local_path("assets/private/seed3d/models/" + job_id)
            if target.exists():
                report = target / "manifest.json"
                if report.is_file():
                    result = json.loads(report.read_text())
                    if result.get("task_id") == entry.get("task_id") and all(
                            (target / x["path"]).is_file() and sha256(target / x["path"]) == x["sha256"] for x in result.get("files", [])):
                        return {"job_id": job_id, "status": "already_downloaded", "manifest": str(report.relative_to(self.root))}
                raise BatchError("Existing download does not verify; preserve it for review")
            try:
                body = json.loads(self.raw_path(job_id).read_text())
                url = body["content"]["file_url"]
                allowed_url(url)
            except BatchError:
                raise
            except Exception:
                raise BatchError("No saved successful download URL; sync the task first") from None
            target.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix=".download-", dir=str(target.parent)))
            try:
                archive = stage / "source.zip"
                self.downloader(url, archive)
                if archive.stat().st_size > MAX_DOWNLOAD:
                    raise BatchError("Output archive exceeds download limit")
                meshes = extract_archive(archive, stage / "files")
                selected = [str(p.relative_to(stage)) for p in meshes]
                files = [{"path": str(p.relative_to(stage)), "bytes": p.stat().st_size, "sha256": sha256(p)}
                         for p in sorted(stage.rglob("*")) if p.is_file()]
                manifest = {"schema_version": 1, "job_id": job_id, "task_id": entry["task_id"], "model": MODEL,
                            "reference_sha256": entry.get("reference_sha256"), "license_status": entry.get("license_status"),
                            "downloaded_at": utc_now(), "files": files, "meshes": selected,
                            "validation": "archive_paths_and_mesh_dependencies_checked; no importer/code executed",
                            "identity_status": "unreviewed_AI_reconstruction_candidate", "distribution": "local_only_pending_rights_review"}
                atomic_json(stage / "manifest.json", manifest)
                os.replace(stage, target)
                entry["download_manifest"] = str((target / "manifest.json").relative_to(self.root))
                self.save()
                return {"job_id": job_id, "status": "downloaded", "manifest": entry["download_manifest"], "meshes": selected}
            finally:
                if stage.exists():
                    shutil.rmtree(stage)

    @staticmethod
    def public_entry(entry):
        return {k: entry.get(k) for k in ("job_id", "task_id", "status", "reserved_tokens", "reported_usage_tokens", "usage_basis")}

    def status(self):
        with self.locked():
            used = sum(self.charged(e) for e in self.entries)
            return {"model": MODEL, "account_remaining_verified": False,
                    "scope": "this_batch_only; declared allowance is not an account balance query",
                    "submission_slots_used": len(self.entries), "submission_slots_limit": MAX_JOBS,
                    "reported_usage_tokens": sum(e.get("reported_usage_tokens") or 0 for e in self.entries),
                    "reserved_or_estimated_tokens": sum(e.get("reserved_tokens", PER_JOB) for e in self.entries if e.get("reported_usage_tokens") is None),
                    "batch_accounted_tokens": used, "batch_limit_tokens": self.limit,
                    "batch_remaining_tokens": max(0, self.limit - used),
                    "declared_allowance_less_this_batch_tokens": self.plan["budget"]["declared_free_tokens"] - used,
                    "entries": [self.public_entry(e) for e in self.entries]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--plan", default="library/seed3d-plan.json")
    parser.add_argument("--ledger", default="production/seed3d/usage-ledger.json")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("submit", "sync", "download"):
        commands.add_parser(name).add_argument("job")
    adopt = commands.add_parser("adopt")
    adopt.add_argument("job")
    adopt.add_argument("task_id")
    commands.add_parser("status")
    args = parser.parse_args(argv)
    try:
        control = Controller(args.root, args.plan, args.ledger)
        result = getattr(control, args.command)(*([args.job, args.task_id] if args.command == "adopt" else [args.job] if args.command != "status" else []))
        print(json.dumps(clean(result), ensure_ascii=False, indent=2))
        return 0
    except BatchError as error:
        print(json.dumps({"error": clean(str(error)), "automatic_post_retry": False}, ensure_ascii=False), file=sys.stderr)
        return 1
    except Exception:
        print('{"error":"Local validation or storage failure; inspect private records before any retry","automatic_post_retry":false}', file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
