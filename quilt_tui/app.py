"""
Quilt TUI for kev-substrate.

A Textual app that lets you:
- See recent cells (top 50 by timestamp) in a sidebar
- Inspect the selected cell's state, questions, answers, witnesses
- Type new questions to send through kev
- Run JEV semantic search across cells

The TUI is one of four surfaces (CLI, HTTP, TUI, webnative) onto the
same canonical cell graph. All four drive the same substrate.
"""
from __future__ import annotations
import asyncio
import json
from datetime import datetime
from typing import Optional

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Input, Static, ListView, ListItem, Label, RichLog, Markdown
    from textual.containers import Horizontal, Vertical
    from textual.reactive import reactive
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

from kev.substrate import SubstrateClient


if HAS_TEXTUAL:
    class CellListItem(ListItem):
        """One row in the cell sidebar."""
        def __init__(self, cell_id: str, source: str, timestamp: str):
            super().__init__(Label(f"{timestamp}  {source:14s}  {cell_id[:24]}"))
            self.cell_id = cell_id


    class CellDetail(Static):
        """The right pane showing the selected cell's full state."""
        def render_cell(self, cell: dict):
            if not cell:
                self.update("Select a cell to inspect")
                return
            text = f"# Cell {cell.get('id', '?')}\n\n"
            text += f"**Type**: {cell.get('type', '?')}\n"
            text += f"**Source**: {cell.get('source', '?')}\n"
            text += f"**Timestamp**: {cell.get('created_at', '?')}\n\n"
            state = cell.get('state')
            if state:
                try:
                    parsed = json.loads(state)
                    text += "## State\n```json\n" + json.dumps(parsed, indent=2)[:800] + "\n```\n"
                except Exception:
                    text += f"## State\n```\n{state[:500]}\n```\n"
            self.update(text)


    class QuiltTUI(App):
        """The main TUI app."""
        
        CSS = """
        Screen { layout: horizontal; }
        #sidebar { width: 40%; border: solid green; }
        #detail { width: 60%; border: solid blue; }
        #question-input { dock: bottom; height: 3; }
        CellDetail { padding: 1; }
        """
        
        BINDINGS = [
            ("ctrl+c", "quit", "Quit"),
            ("ctrl+r", "refresh", "Refresh cells"),
            ("ctrl+j", "jev_search", "JEV search"),
        ]
        
        cells: reactive[list] = reactive(list, recompose=False)
        selected_cell: reactive[Optional[dict]] = reactive(None, recompose=False)
        
        def __init__(self, substrate_client: SubstrateClient, **kwargs):
            super().__init__(**kwargs)
            self.client = substrate_client
        
        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal():
                with Vertical(id="sidebar"):
                    yield Static("Recent cells (Ctrl+R to refresh)", id="sidebar-header")
                    yield ListView(id="cell-list")
                with Vertical(id="detail"):
                    yield CellDetail("Select a cell to inspect", id="cell-detail")
            yield Input(placeholder="Type a question and press Enter...", id="question-input")
            yield Footer()
        
        async def on_mount(self) -> None:
            self.title = "Quilt TUI — kev-substrate"
            self.sub_title = "Press Ctrl+R to refresh, Ctrl+J for JEV search, Ctrl+C to quit"
            await self.refresh_cells()
        
        async def action_refresh(self) -> None:
            await self.refresh_cells()
        
        async def action_jev_search(self) -> None:
            query = self.query_one("#question-input", Input).value
            if not query.strip():
                return
            loop = asyncio.get_event_loop()
            matches = await loop.run_in_executor(None, self.client.jev, query)
            detail = self.query_one(CellDetail)
            if not matches:
                detail.update(f"# JEV search: '{query}'\n\nNo matches.")
            else:
                md = f"# JEV search: '{query}'\n\n"
                for m in matches[:10]:
                    md += f"- **{m['id']}** (score {m.get('score', 0):.3f}): {m.get('metadata', {}).get('topic', m['id'])}\n"
                detail.update(md)
        
        async def refresh_cells(self):
            """Fetch recent cells from the substrate."""
            loop = asyncio.get_event_loop()
            cells = await loop.run_in_executor(None, self._fetch_cells)
            self.cells = cells
            list_view = self.query_one("#cell-list", ListView)
            await list_view.clear()
            for c in cells[:50]:
                item = CellListItem(
                    cell_id=c["id"],
                    source=c.get("source", "?"),
                    timestamp=c.get("created_at", "")[:19],
                )
                await list_view.append(item)
        
        def _fetch_cells(self):
            """Sync helper to fetch recent cells."""
            try:
                req_url = f"{self.client.substrate_url}/api/cells?limit=50"
                import urllib.request
                with urllib.request.urlopen(req_url, timeout=10) as r:
                    data = json.loads(r.read())
                return data.get("cells", [])
            except Exception as e:
                return [{"id": f"error-{e}", "source": "error", "created_at": ""}]
        
        async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
            if event.item is None or not isinstance(event.item, CellListItem):
                return
            loop = asyncio.get_event_loop()
            cell = await loop.run_in_executor(None, self.client.chain, event.item.cell_id)
            detail = self.query_one(CellDetail)
            if cell:
                detail.render_cell(cell[0] if cell else None)
        
        async def on_input_submitted(self, event: Input.Submitted) -> None:
            """Send a kev question through the substrate."""
            text = event.value.strip()
            if not text:
                return
            # Parse as simple state-only question
            detail = self.query_one(CellDetail)
            detail.update(f"# Sending question: '{text}'\n\nCalling kev...")
            loop = asyncio.get_event_loop()
            
            # Simple CLI: send the text as state, ask "intent"
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: self.client.systemone(
                        state=text,
                        questions={
                            "intent": {"type": "noul", "instructions": "Is this a question or statement?"},
                            "topic": {"type": "choice", "instructions": "Topic area",
                                      "criteria": {"tech": "Tech", "billing": "Billing", "support": "Support", "other": "Other"}},
                        },
                    ),
                )
                detail.update(
                    f"# Cell recorded: {result.cell_id}\n\n"
                    f"**Hash**: {result.hash}\n"
                    f"**prev_hash**: {result.prev_hash}\n\n"
                    f"## Answers\n```json\n{json.dumps(result.answers, indent=2)}\n```\n"
                )
                await self.refresh_cells()
            except Exception as e:
                detail.update(f"# Error: {e}")
            self.query_one("#question-input", Input).value = ""


def main():
    """Entry point for the TUI."""
    if not HAS_TEXTUAL:
        print("Textual not installed. Install with: pip install textual")
        print("Falling back to simple text mode...")
        return fallback_main()
    
    import argparse
    ap = argparse.ArgumentParser(description="Quilt TUI — kev-substrate cell-graph explorer")
    ap.add_argument("--kev-url", default="http://127.0.0.1:8009")
    ap.add_argument("--substrate-url", default="https://quilt-distributed.casey-digennaro.workers.dev")
    args = ap.parse_args()
    
    client = SubstrateClient(
        kev_url=args.kev_url,
        substrate_url=args.substrate_url,
    )
    
    app = QuiltTUI(client)
    app.run()


def fallback_main():
    """Simple text fallback when textual isn't available."""
    print("Quilt TUI (fallback mode)")
    print("Recent cells in substrate:")
    print("-" * 60)
    
    client = SubstrateClient()
    try:
        cells = client.jev("recent cell")[:5]
        for m in cells:
            print(f"  {m['id']}: {m.get('metadata', {}).get('topic', '?')}")
    except Exception as e:
        print(f"  (could not fetch: {e})")
    
    print()
    print("Install textual for the full TUI: pip install textual")


if __name__ == "__main__":
    main()
