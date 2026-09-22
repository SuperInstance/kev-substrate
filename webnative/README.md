# kev-substrate/webnative

Browser-first PWA surface for kev-substrate. Lets you ask kev questions
and have each interaction recorded as a substrate cell — same cell graph
as the CLI, TUI, and HTTP API.

## Run locally

```bash
# 1. Start kev (if you have it running)
uv run --extra serve python -m kev.serve --run runs/kev --port 8009

# 2. Serve this directory (any static server works)
python3 -m http.server 8000

# 3. Open in browser
open http://localhost:8000/webnative
```

## Configuration

URL params let you point to a different kev or substrate:

```
?kev=http://my-kev:8009&substrate=https://my-substrate.workers.dev
```

## What it does

- Three question types: choice, noul (yes/no), score (rating)
- Each question becomes a substrate cell with prev_hash chain
- Live cell list refreshes every 10 seconds
- Falls back to simulated kev responses if no local kev is running,
  so the substrate still records cells for testing

## Surfaces

This is one of four views onto the same cell graph:

| Surface | How to use |
|---|---|
| **Webnative** (this) | Open `index.html` in a browser |
| **CLI** | `bin/kev-substrate --state "..." --question ...` |
| **TUI** | `python -m quilt_tui` (requires `pip install textual`) |
| **HTTP** | `POST /v1/systemone` (via the substrate wrapper) |

All four call the same kev instance and record into the same substrate.

## Why this surface

Webnative means: works in the browser without installation. The PWA
manifest + service worker make it installable to the home screen on
mobile and desktop, with offline support for reading past cells.
