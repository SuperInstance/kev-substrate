---
canon: 1
name: kev-substrate
mission: "kev (Jev-like small decision models by jaredpalmer) interweaved with Quilt substrate. Webnative + TUI + CLI drive one shared cell graph; each surface is a 'view' onto the same canonical state. Apache-2.0 (forked from jaredpalmer/kev 2026-09-22)."
state: scaffolding
family: applications
vessel: SuperInstance
born_from: [jaredpalmer/kev]
feeds: [superinstance/cargo-line-tycoon, superinstance/jev-oracle]
owed_by: [superinstance/quilt]
canonical_docs: [README.md, docs/INTERWEAVE.md, kev/substrate.py]
ledger: git-log
verified: 2026-09-22
---

# kev-substrate

**Forked from [jaredpalmer/kev](https://github.com/jaredpalmer/kev) (Apache-2.0) on 2026-09-22.**

## What this is

kev is a small "Jev-like" family of decision models built on Qwen3.5, with a TypeSafe-compatible `/v1/systemone` API for asking yes/no, multiple-choice, and rating questions of a state.

This fork interweaves kev's inference engine with Quilt's cell-substrate doctrine:

- **Original kev**: question → probabilities → answer
- **kev-substrate**: question → cell transition → substrate state → probabilities → answer + witness entry → next cell

The interweave turns each inference call into a substrate event: every question produces a cell with `prev_hash`, witness-log entry, and JEV-comparable embedding. The same cell graph is queryable from three surfaces:

| Surface | Runtime | Audience |
|---|---|---|
| `/v1/systemone` HTTP API (preserved from kev) | FastAPI | Existing TypeSafe SDKs, curl, scripts |
| **CLI** (`kev-substrate eval/run/drill`) | Python + curses fallback | Shell users, scripts, CI |
| **TUI** (terminal UI with live cell-graph) | Python + Textual | Interactive exploration |
| **Webnative** (browser-first PWA) | HTML + WASM (Qwen2.5 ONNX fallback) | End users, no install |

All four surfaces are "openers" onto the same canonical cell graph stored in D1/Vectorize.

## Why this matters

kev's "Jev-like architecture" overlaps with our JEV (Joint Embedding Validator) at the conceptual level — both are about extracting structured judgments from state. Forking lets us explore whether the substrate can host inference as a first-class substrate operation, not a black-box HTTP call.

## Plan

See `docs/INTERWEAVE.md` for the architecture and roadmap.
