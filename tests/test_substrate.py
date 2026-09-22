"""
Tests for kev.substrate.SubstrateClient — focused on the substrate side.
Uses a mock HTTP server (via http.server) to stand in for kev and the substrate worker.
No external dependencies.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import unittest

from kev.substrate import SubstrateClient, _fnv1a64, _hash16


class _MockState:
    """Shared state between mock handler and tests."""
    requests = []
    kev_response = None
    substrate_response = None


class MockHandler(BaseHTTPRequestHandler):
    """Mock server that records requests and returns canned responses."""
    
    def log_message(self, *a, **kw):
        pass
    
    def _read(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        return body
    
    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read()
        _MockState.requests.append((self.command, path, body))
        
        if path == "/v1/systemone":
            resp = _MockState.kev_response or {
                "model": "kev-latest",
                "answers": {"department": {"type": "choice", "choice": "returns"}},
                "latency_ms": 123,
            }
        elif path == "/api/cell":
            resp = _MockState.substrate_response or {
                "ok": True,
                "cellId": "mock-cell",
                "hash": "0xdeadbeef",
                "embeddingId": "mock-emb",
            }
        elif path.startswith("/api/cell/"):
            resp = {"ok": True, "cell": {"id": path.split("/")[-1]}, "witnesses": []}
        elif path == "/api/jev/search":
            resp = {"ok": True, "matches": []}
        else:
            resp = {"ok": False, "error": "unknown path"}
        
        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _start_servers():
    """Spin up two mock servers: one for kev, one for the substrate worker."""
    _MockState.requests = []
    
    kev_server = HTTPServer(("127.0.0.1", 0), MockHandler)
    sub_server = HTTPServer(("127.0.0.1", 0), MockHandler)
    
    kev_thread = threading.Thread(target=kev_server.serve_forever, daemon=True)
    sub_thread = threading.Thread(target=sub_server.serve_forever, daemon=True)
    kev_thread.start()
    sub_thread.start()
    
    return {
        "kev_url": f"http://127.0.0.1:{kev_server.server_address[1]}",
        "substrate_url": f"http://127.0.0.1:{sub_server.server_address[1]}",
        "_kev": kev_server,
        "_sub": sub_server,
    }


class TestFnv1a(unittest.TestCase):
    def test_fnv1a_canary_matches_fleet(self):
        """Our FNV-1a must match the documented fleet canary."""
        text = "café Δ 日本語"
        h = _fnv1a64(text)
        h16 = format(h, "016x")
        # Fleet canary is 0x024a555471370b18d for this exact string
        self.assertEqual(h16, "24a555471370b18d",
                         f"Fleet canary mismatch: 0x{h16}")
    
    def test_hash16_format(self):
        h = _hash16("test")
        self.assertTrue(h.startswith("0x"))
        self.assertEqual(len(h), 18)  # 0x + 16 hex


class TestSubstrateClient(unittest.TestCase):
    def setUp(self):
        self.servers = _start_servers()
    
    def tearDown(self):
        self.servers["_kev"].shutdown()
        self.servers["_sub"].shutdown()
    
    def test_systemone_records_substrate_cell(self):
        _MockState.kev_response = {
            "model": "kev-latest",
            "answers": {
                "department": {"type": "choice", "choice": "billing",
                              "probabilities": {"returns": 0.1, "shipping": 0.2, "billing": 0.7}},
            },
            "latency_ms": 200,
        }
        _MockState.substrate_response = {
            "ok": True,
            "cellId": "cell-test-001",
            "hash": "0xabcdef",
            "embeddingId": "emb-test-001",
        }
        
        client = SubstrateClient(
            kev_url=self.servers["kev_url"],
            substrate_url=self.servers["substrate_url"],
            conversation_id="test",
        )
        
        result = client.systemone(
            state="Customer was charged twice.",
            questions={
                "department": {
                    "type": "choice",
                    "instructions": "Which team?",
                    "criteria": {"returns": "Returns", "shipping": "Shipping", "billing": "Billing"},
                }
            },
        )
        
        # kev response is returned
        self.assertEqual(result.answers["department"]["choice"], "billing")
        
        # Substrate was notified
        sub_calls = [r for r in _MockState.requests if r[1] == "/api/cell"]
        self.assertEqual(len(sub_calls), 1)
        payload = json.loads(sub_calls[0][2])
        self.assertEqual(payload["type"], "kev-inference")
        self.assertEqual(payload["source"], "kev-substrate")
        
        # Cell hash was computed
        self.assertTrue(result.hash.startswith("0x"))
        
        # First call: prev_hash = 0x0...0
        self.assertEqual(result.prev_hash, "0x" + "0" * 16)
    
    def test_systemone_chains_cells(self):
        client = SubstrateClient(
            kev_url=self.servers["kev_url"],
            substrate_url=self.servers["substrate_url"],
            conversation_id="chain-test",
        )
        
        r1 = client.systemone(state="Q1", questions={"x": {"type": "noul", "instructions": "?"}})
        r2 = client.systemone(state="Q2", questions={"x": {"type": "noul", "instructions": "?"}})
        
        # Second call's prev_hash should equal first call's hash
        self.assertEqual(r2.prev_hash, r1.hash)
        self.assertEqual(r1.prev_hash, "0x" + "0" * 16)
    
    def test_jev_search(self):
        client = SubstrateClient(
            kev_url=self.servers["kev_url"],
            substrate_url=self.servers["substrate_url"],
        )
        matches = client.jev("customer charged twice")
        jev_calls = [r for r in _MockState.requests if r[1] == "/api/jev/search"]
        self.assertEqual(len(jev_calls), 1)
        payload = json.loads(jev_calls[0][2])
        self.assertEqual(payload["query"], "customer charged twice")


if __name__ == "__main__":
    unittest.main(verbosity=2)
