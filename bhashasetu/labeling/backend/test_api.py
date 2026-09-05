"""End-to-end HTTP smoke tests: boot the real server on an ephemeral port with a
temp data root, then drive it exactly like the web UI would.
"""

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from labeling.backend import server
from labeling.backend.store import LabelStore

ROOT = Path(__file__).resolve().parents[2]


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data_root = Path(cls.tmp.name)
        # point the module globals at a temp data root (glossaries stay read-only)
        server.DATA_ROOT = cls.data_root
        server.STORE = LabelStore(server.DATA_ROOT)
        server.GLOSSARIES = server.GlossaryRepo(ROOT / "data" / "glossaries")
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.tmp.cleanup()

    def _req(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = json.dumps(body).encode() if body is not None else None
        conn.request(method, path, payload, {"Content-Type": "application/json"})
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        data = json.loads(raw) if resp.getheader("Content-Type", "").startswith("application/json") else raw
        return resp.status, data

    def test_routes(self):
        status, data = self._req("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])

        status, data = self._req("GET", "/api/config")
        self.assertEqual(status, 200)
        self.assertIn("pds", data["domains"])
        self.assertTrue(data["regions"])

        status, data = self._req("GET", "/api/glossaries")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["domains"]["pds"]["count"], 50)

        status, data = self._req("GET", "/api/stats")
        self.assertEqual(status, 200)
        self.assertIn("samples_total", data)
        self.assertIn("by_domain", data)
        self.assertIn("signer_diversity", data)

        status, data = self._req("GET", "/api/glossaries/pds/search?q=card")
        self.assertEqual(status, 200)
        self.assertTrue(data["results"])

    def test_full_labeling_flow(self):
        # consent
        status, data = self._req("POST", "/api/consent", {
            "signer_id": "S-007", "form_id": "CF-7", "region": "delhi",
            "age_group": "18-30", "gender": "f", "usage": ["training"]})
        self.assertEqual(status, 201)

        # register
        status, data = self._req("POST", "/api/samples", {
            "domain": "pds",
            "signer": {"anon_id": "S-007", "region": "delhi"},
            "gloss_seq": ["pain"],
            "source": {"kind": "self-recorded"},
            "_consent_status": "granted", "_consent_form_id": "CF-7",
        })
        self.assertEqual(status, 201)
        sid = data["sample_id"]
        self.assertTrue(sid.startswith("ISL-PDS-"))

        # first annotator
        status, data = self._req("POST", f"/api/samples/{sid}/labels",
                                 {"annotator": "A1", "gloss": "rice",
                                  "english_sentence": "I need rice."})
        self.assertEqual(status, 200)
        self.assertEqual(data["consensus"]["status"], "needs_voting")

        # second annotator agrees -> consensus reached
        status, data = self._req("POST", f"/api/samples/{sid}/labels",
                                 {"annotator": "A2", "gloss": "rice"})
        self.assertEqual(data["consensus"]["status"], "agreed")

        # qa
        status, data = self._req("POST", f"/api/samples/{sid}/qa",
                                 {"status": "passed", "reviewer": "R1"})
        self.assertEqual(status, 200)
        self.assertTrue(data["eligible_for_manifest"])

        # search shows status
        status, data = self._req("GET", "/api/samples?status=qa_pass")
        self.assertEqual(status, 200)
        self.assertIn(sid, [s["sample_id"] for s in data["samples"]])

        # stats reflect signer diversity
        status, stats = self._req("GET", "/api/stats")
        self.assertEqual(stats["signer_diversity"]["signers"], 1)

        # export
        status, data = self._req("POST", "/api/export", {"version": "v0.1.0"})
        self.assertEqual(status, 200)
        self.assertEqual(data["sample_count"], 1)
        self.assertEqual(data["samples"][0]["sample_id"], sid)

        status, data = self._req("GET", "/api/manifests")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["manifests"]), 1)

    def test_frontend_served(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertIn(b"BhashaSetu", body)

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/static/app.js")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        self.assertEqual(resp.status, 200)

    def test_upload_then_register(self):
        # raw-ish webm body (any bytes are fine; server only saves + registers)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        body = b"\x1a\x45\xdf\xa3fake-webm-bytes" * 100
        conn.request("POST", "/api/upload/video?name=rec-123.webm", body,
                     {"Content-Type": "video/webm"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        self.assertEqual(resp.status, 201)
        self.assertEqual(data["path"], "raw/uploads/rec-123.webm")
        self.assertTrue((server.DATA_ROOT / data["path"]).exists())

        # bad name traversal refused
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/upload/video?name=..%2Fevil.mp4", body)
        resp = conn.getresponse()
        conn.close()
        self.assertEqual(resp.status, 400)

    def test_bad_inputs(self):
        status, data = self._req("POST", "/api/samples", {"domain": "bogus"})
        self.assertEqual(status, 400)
        status, data = self._req("GET", "/api/samples/NOPE")
        self.assertEqual(status, 400)
        status, data = self._req("GET", "/api/samples/ISL-PDS-99999")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()