"""
kev.substrate — Quilt substrate wrapper for kev inference calls.

Turns every systemone request into a substrate cell:
  - prev_hash: link to previous cell in the same conversation chain
  - state: serialized input state + questions
  - answers: kev's probabilities
  - embedding: 768d BGE embedding (sent to Cloudflare Vectorize)
  - witnesses: appended by external JEV sessions, JPCA scans, or kev-substrate itself

The wrapper is non-breaking: it calls kev's serve.py endpoint as-is.
"""
from __future__ import annotations
import json
import time
import hashlib
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Optional

# Try to import kev's Pydantic models — fall back to dicts if unavailable
try:
    from .api import SystemOneRequest, to_record, to_answers
    HAS_KEV_API = True
except ImportError:
    HAS_KEV_API = False


def _fnv1a64(s: str) -> int:
    """FNV-1a 64-bit (the fleet canary)."""
    h = 0xcbf29ce484222325
    for c in s.encode("utf-8"):
        h ^= c
        h = (h * 0x100000001b3) & 0xffffffffffffffff
    return h


def _hash16(s: str) -> str:
    """16-hex FNV-1a (matches the substrate cell hash format)."""
    return "0x" + format(_fnv1a64(s), "016x")


@dataclass
class SubstrateCell:
    """One systemone call → one cell."""
    cell_id: str
    state: str  # JSON of {state, questions}
    answers: dict  # kev's response
    prev_hash: str
    embedding_id: Optional[str] = None
    witness_count: int = 0
    timestamp: int = 0
    source: str = "kev-substrate"


@dataclass
class SubstrateResult:
    """The result returned to the caller."""
    answers: dict
    cell_id: str
    prev_hash: str
    hash: str
    embedding_id: Optional[str]
    witness_count: int
    latency_ms: float


class SubstrateClient:
    """
    Substrate-aware kev client. Wraps kev's /v1/systemone API and records
    every call as a cell in the Quilt substrate.
    
    Args:
        kev_url: Base URL of a running kev serve.py instance.
        substrate_url: Base URL of a Quilt substrate worker (e.g. quilt-distributed).
        api_key: Bearer token for the substrate worker (if configured).
        embed: If True, send the cell to Vectorize for semantic search.
        conversation_id: Optional conversation key — cells in the same
            conversation chain to each other via prev_hash.
    """
    
    def __init__(
        self,
        kev_url: str = "http://127.0.0.1:8009",
        substrate_url: str = "https://quilt-distributed.casey-digennaro.workers.dev",
        api_key: Optional[str] = None,
        embed: bool = True,
        conversation_id: Optional[str] = None,
    ):
        self.kev_url = kev_url.rstrip("/")
        self.substrate_url = substrate_url.rstrip("/")
        self.api_key = api_key
        self.embed = embed
        self.conversation_id = conversation_id or "default"
        # Local cache of conversation chains: conv_id -> {cell_id -> prev_hash}
        self._chains: dict[str, dict[str, str]] = {}
    
    def _post_kev(self, payload: dict) -> dict:
        """Call kev's /v1/systemone endpoint."""
        req = urllib.request.Request(
            f"{self.kev_url}/v1/systemone",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    
    def _post_substrate(self, path: str, payload: dict) -> dict:
        """Call the Quilt substrate worker."""
        headers = {"Content-Type": "application/json", "User-Agent": "kev-substrate/0.1"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.substrate_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return {"error": e.code, "body": e.read().decode()[:200]}
        except Exception as e:
            return {"error": "transport", "body": str(e)}
    
    def _prev_hash(self, cell_id: str) -> str:
        """Get the prev_hash for this cell from the local chain cache."""
        chain = self._chains.setdefault(self.conversation_id, {})
        if not chain:
            return "0x" + "0" * 16
        # Most recent cell in this conversation
        last_id = list(chain.keys())[-1]
        return chain[last_id]
    
    def systemone(
        self,
        state: Any,
        questions: dict,
        model: str = "kev-latest",
        cell_id: Optional[str] = None,
    ) -> SubstrateResult:
        """
        Call kev's systemone endpoint and record the call as a substrate cell.
        
        Args:
            state: input state (string, dict, list, etc. — passes through to kev).
            questions: dict of question_id -> {type, instructions, criteria}.
            model: kev model name (default: "kev-latest").
            cell_id: optional explicit cell ID; auto-generated if absent.
        
        Returns:
            SubstrateResult with answers + cell metadata.
        """
        t0 = time.time()
        
        # Auto-generate cell ID from state hash if not given
        if cell_id is None:
            state_text = state if isinstance(state, str) else json.dumps(state, sort_keys=True)
            qsig = json.dumps(questions, sort_keys=True)
            cell_id = f"kev-{_hash16(state_text + qsig + str(int(t0)))[2:14]}"
        
        # Call kev
        payload = {"state": state, "questions": questions, "model": model}
        kev_resp = self._post_kev(payload)
        
        # Determine prev_hash
        prev_hash = self._prev_hash(cell_id)
        
        # Compute cell hash (cell_id + state + answers + prev_hash)
        state_json = json.dumps({"state": state, "questions": questions}, sort_keys=True)
        answers_json = json.dumps(kev_resp.get("answers", {}), sort_keys=True)
        cell_hash = _hash16(cell_id + state_json + answers_json + prev_hash)
        
        # Record in substrate (non-blocking on failure)
        cell_payload = {
            "id": cell_id,
            "type": "kev-inference",
            "state": json.dumps({
                "state": state,
                "questions": questions,
                "answers": kev_resp.get("answers"),
                "model": model,
                "kev_latency_ms": kev_resp.get("latency_ms"),
            }),
            "prev_hash": prev_hash,
            "source": "kev-substrate",
        }
        sub_resp = self._post_substrate("/api/cell", cell_payload)
        embedding_id = sub_resp.get("embeddingId") if sub_resp.get("ok") else None
        
        # Update local chain
        self._chains[self.conversation_id][cell_id] = cell_hash
        
        latency_ms = (time.time() - t0) * 1000
        
        return SubstrateResult(
            answers=kev_resp.get("answers", {}),
            cell_id=cell_id,
            prev_hash=prev_hash,
            hash=cell_hash,
            embedding_id=embedding_id,
            witness_count=sub_resp.get("witness_count", 0),
            latency_ms=latency_ms,
        )
    
    def chain(self, cell_id: str) -> list[dict]:
        """Return the full witness chain for a cell (cell + any witnesses)."""
        resp = self._post_substrate(f"/api/cell/{cell_id}", {})
        if not resp.get("ok"):
            return []
        return [resp.get("cell"), *resp.get("witnesses", [])]
    
    def jev(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search across all kev-substrate cells."""
        resp = self._post_substrate("/api/jev/search", {"query": query, "topK": top_k})
        return resp.get("matches", [])


# CLI convenience
def _cli():
    import argparse, sys
    ap = argparse.ArgumentParser(description="kev-substrate CLI — single inference via substrate")
    ap.add_argument("--kev-url", default="http://127.0.0.1:8009")
    ap.add_argument("--substrate-url", default="https://quilt-distributed.casey-digennaro.workers.dev")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--model", default="kev-latest")
    ap.add_argument("--state", required=True, help="Input state text (or @file for file)")
    ap.add_argument("--question", action="append", required=True,
                    help='Question in the form id:type:instructions:option1=value1|option2=value2. '
                         'Example: dept:choice:Which team?:returns=Returns|shipping=Shipping|billing=Billing')
    ap.add_argument("--conversation", default="cli-default")
    args = ap.parse_args()
    
    # Parse questions
    questions = {}
    for q in args.question:
        parts = q.split(":", 3)
        if len(parts) != 4:
            print(f"Bad question: {q}", file=sys.stderr)
            sys.exit(1)
        qid, qtype, instr, opts = parts
        if qtype == "noul":
            questions[qid] = {"type": "noul", "instructions": instr}
        elif qtype == "choice":
            criteria = {}
            for opt in opts.split("|"):
                if "=" in opt:
                    k, v = opt.split("=", 1)
                    criteria[k] = v
            questions[qid] = {"type": "choice", "instructions": instr, "criteria": criteria}
        elif qtype == "score":
            levels = [l for l in opts.split("|") if l]
            questions[qid] = {"type": "score", "instructions": instr, "criteria": levels}
        else:
            print(f"Unknown question type: {qtype}", file=sys.stderr)
            sys.exit(1)
    
    state_text = args.state
    if state_text.startswith("@"):
        with open(state_text[1:]) as f:
            state_text = f.read()
    
    client = SubstrateClient(
        kev_url=args.kev_url,
        substrate_url=args.substrate_url,
        api_key=args.api_key,
        conversation_id=args.conversation,
    )
    
    result = client.systemone(state_text, questions, model=args.model)
    
    print(json.dumps({
        "answers": result.answers,
        "cell_id": result.cell_id,
        "hash": result.hash,
        "prev_hash": result.prev_hash,
        "embedding_id": result.embedding_id,
        "latency_ms": round(result.latency_ms, 2),
    }, indent=2))


if __name__ == "__main__":
    _cli()
