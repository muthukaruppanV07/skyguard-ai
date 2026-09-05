"""BhashaSetu labeling server (Python stdlib only â€” runs offline, no installs).

Start:
    python labeling/backend/server.py --port 8123
Open http://localhost:8123/  (SPA lives in labeling/frontend/)

API (all under /api, JSON):
    GET    /api/health
    GET    /api/config
    GET    /api/glossaries
    GET    /api/glossaries/{domain}
    GET    /api/glossaries/{domain}/search?q=...
    GET    /api/samples?domain=&status=&limit=&offset=
    GET    /api/samples/{id}
    GET    /api/samples/{id}/keypoints
    POST   /api/samples                         register a sample
    POST   /api/samples/{id}/labels             annotator vote
    POST   /api/samples/{id}/qa                 QA pass|reject
    GET    /api/consent/{signer_id}
    POST   /api/consent                         register consent
    POST   /api/consent/withdraw                withdraw signer
    GET    /api/stats
    POST   /api/export                          build versioned manifest
    GET    /api/manifests                       list shipped manifests
Static: / (SPA), /static/* (frontend assets), /media/* (data/ raw+keypoints+video)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]

try:  # `python -m labeling.backend.server`
    from .consensus import AGREEMENT_THRESHOLD, MIN_ANNOTATORS, compute_consensus
    from .glossary import GlossaryRepo
    from .manifest import DATASET_VERSION, write_manifest
    from .store import LabelStore
except ImportError:  # `python labeling/backend/server.py`
    sys.path.insert(0, str(ROOT))
    from labeling.backend.consensus import AGREEMENT_THRESHOLD, MIN_ANNOTATORS, compute_consensus
    from labeling.backend.glossary import GlossaryRepo
    from labeling.backend.manifest import DATASET_VERSION, write_manifest
    from labeling.backend.store import LabelStore

DATA_ROOT = ROOT / "data"
FRONTEND = ROOT / "labeling" / "frontend"
GLOSSARY_DIR = DATA_ROOT / "glossaries"

STORE = LabelStore(DATA_ROOT)
GLOSSARIES = GlossaryRepo(DATA_ROOT / "glossaries")

SAMPLE_ID_RE = re.compile(r"^ISL-(PDS|HTH|LEG)-\d{5}$")

UPLOAD_DIR = DATA_ROOT / "raw" / "uploads"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv", ".m4v"}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}


def _safe_join(root: Path, rel: str) -> Path | None:
    """Resolve rel under root, refusing traversal."""
    target = (root / rel).resolve()
    root_r = root.resolve()
    if root_r != target and root_r not in target.parents:
        return None
    return target


def _project_sample(sample: dict, latest_labels: list[dict], consensus: dict) -> dict:
    return {
        "sample_id": sample["sample_id"],
        "domain": sample["domain"],
        "status": sample["status"],
        "created_at": sample["created_at"],
        "version": sample["version"],
        "gloss_seq": sample.get("gloss_seq", []),
        "english_sentence": sample.get("english_sentence", ""),
        "dialect": sample.get("dialect", {}),
        "signer": sample.get("signer", {}),
        "source": sample.get("source"),
        "video": sample.get("video"),
        "keypoints": sample.get("keypoints"),
        "consent": sample.get("consent", {}),
        "labels": latest_labels,
        "consensus": consensus,
        "qa": sample.get("qa", {}),
        "eligible_for_manifest": (
            sample.get("consent", {}).get("status") == "granted"
            and consensus.get("status") == "agreed"
            and sample.get("qa", {}).get("status") == "passed"
            and sample.get("status") != "withdrawn"
        ),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "BhashaSetuLabeling/0.1"

    # ------------------------------------------------------------- helpers
    def _send_json(self, obj, code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str):
        self._send_json({"error": message}, code)

    def _send_file(self, path: Path):
        if not path.exists() or not path.is_file():
            return self._send_error(404, "not found")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(path.suffix.lower(), "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("invalid JSON body")
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _path_parts(self) -> list[str]:
        path = unquote(urlsplit(self.path).path)
        return [seg for seg in path.split("/") if seg]

    def _query(self) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ------------------------------------------------------------- routing
    def do_GET(self):
        parts = self._path_parts()
        q = self._query()
        try:
            if not parts:
                return self._serve_index()
            if parts[0] == "static":
                return self._serve_static(parts[1:])
            if parts[0] == "media":
                return self._serve_media(parts[1:])
            if parts[0] == "api":
                return self._api_get(parts[1:], q)
            return self._send_error(404, "unknown path")
        except (KeyError, ValueError) as exc:
            return self._send_error(400, str(exc))

    def do_POST(self):
        parts = self._path_parts()
        try:
            if parts[0] == "api":
                return self._api_post(parts[1:])
            return self._send_error(404, "unknown path")
        except (KeyError, ValueError) as exc:
            return self._send_error(400, str(exc))

    # ------------------------------------------------------------- static
    def _serve_index(self):
        idx = FRONTEND / "index.html"
        if not idx.exists():
            return self._send_error(500, "frontend missing")
        body = idx.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, parts: list[str]):
        target = _safe_join(FRONTEND, "/".join(parts))
        if target is None:
            return self._send_error(403, "forbidden")
        return self._send_file(target)

    def _serve_media(self, parts: list[str]):
        target = _safe_join(DATA_ROOT, "/".join(parts))
        if target is None:
            return self._send_error(403, "forbidden")
        return self._send_file(target)

    # ------------------------------------------------------------- api get
    def _api_get(self, parts: list[str], q: dict):
        if not parts:
            return self._send_error(404, "api subpath required")

        head = parts[0]

        if head == "health":
            return self._send_json({"ok": True, "dataset_version": DATASET_VERSION})

        if head == "config":
            return self._send_json(_config())

        if head == "glossaries":
            if len(parts) == 1:
                return self._send_json({
                    "domains": {d: {"count": len(GLOSSARIES.entries(d))}
                                for d in GLOSSARIES.domains()},
                })
            domain = parts[1]
            if len(parts) == 2:
                return self._send_json(GLOSSARIES._load(domain))
            if parts[2] == "search":
                return self._send_json({"results": GLOSSARIES.search(
                    domain, q.get("q", ""), int(q.get("limit", 25)))})
            return self._send_error(404, "unknown glossary route")

        if head == "samples":
            if len(parts) >= 2:
                sid = parts[1]
                if not SAMPLE_ID_RE.match(sid):
                    raise ValueError("bad sample_id")
                sample = STORE.get_sample(sid)
                if sample is None:
                    return self._send_error(404, "sample not found")
                if len(parts) == 3 and parts[2] == "keypoints":
                    return self._serve_media(["keypoints", sid + ".json"])
                return self._send_json(_project_sample(
                    sample, STORE.latest_labels_for(sid),
                    _consensus_for(sid)))
            return self._send_json(_sample_list(q))

        if head == "consent":
            if len(parts) < 2:
                return self._send_error(404, "signer_id required")
            rec = STORE.get_consent(parts[1])
            return self._send_json(rec or {"signer_id": parts[1], "status": "unknown"})

        if head == "stats":
            return self._send_json(STORE.stats())

        if head == "manifests":
            mdir = DATA_ROOT / "manifests"
            files = sorted(mdir.glob("*.json"), key=lambda p: p.name)
            return self._send_json({"manifests": [p.name for p in files]})

        return self._send_error(404, "unknown api route")

    # ------------------------------------------------------------- uploads
    def _api_upload_video(self):
        """Accepts a raw video body (e.g. webm from the browser recorder).

        POST /api/upload/video?name=<file.webm>  Content-Type: video/webm

        Saves under data/raw/uploads/ (consent is enforced at registration, not
        upload â€” the recorder UI blocks save until consent is acknowledged).
        """
        q = self._query()
        name = q.get("name", "")
        if not name or name != Path(name).name:  # no slashes / traversal
            raise ValueError("filename must be a plain file name")
        if Path(name).suffix.lower() not in ALLOWED_VIDEO_EXT:
            raise ValueError("unsupported video extension")
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            raise ValueError("empty upload body")
        if length > MAX_UPLOAD_BYTES:
            return self._send_error(413, f"upload too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)}MB)")
        upload_dir = DATA_ROOT / "raw" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        target = upload_dir / name
        body = self.rfile.read(length)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(body)
        os.replace(tmp, target)
        rel = f"raw/uploads/{name}"
        self._send_json({"path": rel, "size": length}, 201)
        return None

    # ------------------------------------------------------------- api post
    def _api_post(self, parts: list[str]):
        if not parts:
            return self._send_error(404, "api subpath required")
        head = parts[0]

        if head == "upload" and len(parts) == 2:
            return self._api_upload_video()

        if head == "samples" and len(parts) == 1:
            body = self._read_json()
            sample = STORE.register_sample(body, actor=body.get("_actor", "web"))
            return self._send_json(_project_sample(
                sample, [], _consensus_for(sample["sample_id"])), 201)

        if head == "consent" and len(parts) == 1:
            body = self._read_json()
            rec = STORE.register_consent(body, actor=body.get("_actor", "web"))
            return self._send_json(rec, 201)

        if head == "export" and len(parts) == 1:
            body = self._read_json()
            version = body.get("version", DATASET_VERSION)
            out = write_manifest(STORE, DATA_ROOT, version)
            manifest = json.loads(out.read_text(encoding="utf-8"))
            manifest["manifest_file"] = out.name
            return self._send_json(manifest)

        if head == "consent" and parts[1] == "withdraw":
            body = self._read_json()
            impacted = STORE.withdraw(body.get("signer_id"),
                                      actor=body.get("_actor", "web"))
            return self._send_json({"withdrawn_samples": impacted})

        if len(parts) < 3:
            return self._send_error(404, "unknown api route")
        sid = parts[1]
        if not SAMPLE_ID_RE.match(sid):
            raise ValueError("bad sample_id")

        if head == "samples":
            if parts[2] == "labels":
                body = self._read_json()
                STORE.add_label(sid, body, actor=body.get("_actor", "web"))
                return self._send_json(_project_sample(
                    STORE.get_sample(sid), STORE.latest_labels_for(sid),
                    _consensus_for(sid)))
            if parts[2] == "qa":
                body = self._read_json()
                STORE.set_qa(sid, body, actor=body.get("_actor", "web"))
                return self._send_json(_project_sample(
                    STORE.get_sample(sid), STORE.latest_labels_for(sid),
                    _consensus_for(sid)))

        return self._send_error(404, "unknown api route")


def _config() -> dict:
    meta = json.loads((GLOSSARY_DIR / "meta.json").read_text(encoding="utf-8"))
    return {
        "dataset_version": DATASET_VERSION,
        "consensus_threshold": AGREEMENT_THRESHOLD,
        "min_annotators": MIN_ANNOTATORS,
        "domains": {d: {"label": meta["domains"][d]["label"],
                        "count": len(GLOSSARIES.entries(d))}
                    for d in GLOSSARIES.domains()},
        "regions": meta["regions"],
        "media_root": str(DATA_ROOT),
    }


def _glossary(domain: str) -> dict:
    return GLOSSARIES._load(domain)


def _consensus_for(sid: str) -> dict:
    return compute_consensus(STORE.latest_labels_for(sid))


def _sample_list(q: dict) -> dict:
    samples = STORE.all_samples()
    if "domain" in q:
        samples = [s for s in samples if s["domain"] == q["domain"]]
    if "status" in q:
        samples = [s for s in samples if s["status"] == q["status"]]
    samples.sort(key=lambda s: s["sample_id"])
    offset = int(q.get("offset", 0))
    limit = int(q.get("limit", 100))
    page = samples[offset:offset + limit]
    out = [_project_sample(s, STORE.latest_labels_for(s["sample_id"]),
                           _consensus_for(s["sample_id"])) for s in page]
    return {"total": len(samples), "offset": offset, "limit": limit, "samples": out}


def main(argv=None):
    parser = argparse.ArgumentParser(description="BhashaSetu labeling server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8123)
    args = parser.parse_args(argv)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"BhashaSetu labeling server on http://{args.host}:{args.port}/")
    print(f"  data root  : {DATA_ROOT}")
    print(f"  annot log  : {DATA_ROOT / 'annotations' / 'audit.log'}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")


if __name__ == "__main__":
    main()