# INTERWEAVE — kev ↔ Quilt Substrate

**Status**: scaffolding (2026-09-22)
**Author**: Mavis (Casey's AI assistant)
**License**: Apache-2.0 (inherited from jaredpalmer/kev)

## Core idea

kev answers questions about state. Quilt's cell substrate records state transitions with cryptographic witness chains. The interweave turns kev's `systemone` calls into substrate events:

```
                  ┌────────────────────────────────────────┐
                  │  Canonical cell graph (the substrate)  │
                  │                                        │
                  │   cell_001 ──prev_hash── cell_002       │
                  │      ▲                  │              │
                  │      │ question         │ answer       │
                  │      │ state            │ witnesses    │
                  │      ▼                  ▼              │
                  │   cell_003 ──prev_hash── cell_004       │
                  │                                        │
                  └────────┬──────────────┬────────────────┘
                           │              │
              ┌────────────┴──┐       ┌────┴────────────┐
              ▼               ▼       ▼                 ▼
         ┌─────────┐    ┌─────────┐  ┌─────────┐  ┌──────────────┐
         │ /v1/sys │    │  CLI    │  │  TUI    │  │  Webnative   │
         │ temone  │    │ (Python)│  │(Textual)│  │  (PWA + ONNX)│
         │  HTTP   │    │ curses  │  │ ratatui │  │              │
         └─────────┘    └─────────┘  └─────────┘  └──────────────┘
              ▲                              ▲              ▲
              └──────── existing TypeSafe ───┴──── new ─────┘
                          SDKs work unchanged
```

## Substrate additions to kev

### 1. `kev/substrate.py` — substrate wrapper

Wraps every inference call:

```python
from kev.substrate import SubstrateClient

client = SubstrateClient(
    kev_url="http://localhost:8009",
    substrate_url="https://quilt-distributed.casey-digennaro.workers.dev",
    api_key=os.environ["KEV_SUBSTRATE_KEY"],
)

# Same shape as SystemOneRequest, but each call becomes a cell
result = client.systemone(
    state="Customer ticket text...",
    questions={
        "department": {"type": "choice", "criteria": {...}},
        "escalate":   {"type": "noul", "instructions": "..."},
    },
    cell_id="ticket-001-q-department",  # optional, auto-generated if absent
)
# result.answers — same as kev's
# result.cell_id — substrate cell that recorded this
# result.prev_hash — chain link
# result.witness_count — number of witness attestations on this cell
```

### 2. Cell model

Each `systemone` call → one cell:
- `id`: derived from state hash + question set
- `state`: JSON-serialised state (text + questions)
- `answers`: the probabilities kev returned
- `embedding`: 768d BGE embedding of state + answers (via Cloudflare Vectorize)
- `prev_hash`: link to most-recent cell with same `state_id` (chain over the same conversation)
- `witnesses`: appended as cells reference this one (e.g. JEV session queries it)

### 3. CLI surface (`kev-substrate`)

```
$ kev-substrate eval tickets.csv --state-col body --question department
$ kev-substrate drill "What's the sentiment?" --type noul
$ kev-substrate chain <cell-id>     # show full witness chain for a cell
$ kev-substrate jev <cell-id>       # JEV-style semantic search across cells
```

### 4. TUI surface (Textual)

A live cell-graph explorer:
- Sidebar: list of recent cells (top 50 by timestamp)
- Center: probabilities + witnesses for the selected cell
- Bottom: chat-like input to ask new questions
- The TUI reads from substrate, not from kev directly — same cell graph as the webnative.

### 5. Webnative surface (PWA)

Browser-first, no install:
- ONNX-quantised kev-0.8B for in-browser inference (3-5 second latency on M1)
- Cell-graph visualisation via WebGPU compute
- Live substrate sync via Cloudflare Worker
- Works offline; queues questions when disconnected, syncs when reconnected

## Implementation order

1. **Substrate wrapper** (`kev/substrate.py`) — non-breaking, additive on top of kev's `serve.py`. PR against this fork.
2. **CLI** (`kev-substrate` entry point) — depends on substrate wrapper. Python + curses fallback.
3. **TUI** (Textual) — depends on substrate wrapper + CLI for some commands.
4. **Webnative** (PWA + ONNX) — depends on substrate wrapper. Pairs with Cloudflare Worker for substrate sync.
5. **Cross-surface witness** — when a question is asked in one surface and viewed in another, both record witness entries. The "multidimensional recording" Casey's doctrine describes.

## Why fork instead of upstream PR

- The interweave is opinionated (cellular substrate) and may not match kev's broader roadmap.
- Apache-2.0 allows forking; we keep credit and the original commits preserved (per no-deletion doctrine).
- The fork can be upstreamed piece-by-piece if Jared agrees (e.g. the substrate wrapper as an opt-in plugin).

## Synergy with existing JEV work

Our `superinstance/jev-oracle` does JEV (Joint Embedding Validator) on canon cells. kev's Jev is a different thing — a decision model architecture. But they share the "JEV" name and similar concept (extracting structured judgments from state). The interweave is a chance to:

1. Reconcile the two meanings of "JEV" in one substrate (one is a validator, the other a model).
2. Use our JEV to score the *quality* of kev's outputs (a JEV cell attests: "this kev prediction is well-calibrated").
3. Let kev's models inform canon promotion (high-confidence kev cells → canon candidates).

This is the kind of cross-domain synthesis the no-deletion doctrine rewards — both "JEV"s preserved, both contributions visible in the substrate.
