import asyncio
import click
from rich.console import Console
from rich.markdown import Markdown
from juuudge.config import get_config, get_app_dir
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.ingest.sync import sync_all_data
from juuudge.agent.providers.anthropic_provider import AnthropicProvider
from juuudge.agent.providers.ollama_provider import OllamaProvider
from juuudge.agent.judge_loop import JudgeAgent

console = Console()

@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context):
    """juuudge - Magic: The Gathering Rules Judge CLI & TUI Agent."""
    if ctx.invoked_subcommand is None:
        from juuudge.tui.app import JuuudgeApp
        app = JuuudgeApp()
        app.run()

@main.command()
@click.argument("question")
def ask(question: str):
    """Ask a rules question directly from stdout."""
    async def _run():
        cfg = get_config()
        app_dir = get_app_dir()
        db = Database(app_dir / "juuudge.db")
        vec_store = VectorStore(app_dir / "lancedb")
        db.init_schema()

        if cfg.llm.provider == "ollama":
            provider = OllamaProvider(host=cfg.llm.ollama_host, model=cfg.llm.model)
        else:
            provider = AnthropicProvider(api_key=cfg.llm.api_key, model=cfg.llm.model)

        agent = JudgeAgent(db, vec_store, provider, max_rounds=cfg.llm.max_tool_rounds)
        
        with console.status("[bold green]Adjudicating MTG rules..."):
            tokens = []
            async for event in agent.ask_stream(question):
                if event["type"] == "token":
                    tokens.append(event["text"])
            
            console.print(Markdown("".join(tokens)))

    asyncio.run(_run())

@main.command()
@click.argument("name")
def card(name: str):
    """Look up card oracle text and Gatherer rulings."""
    app_dir = get_app_dir()
    db = Database(app_dir / "juuudge.db")
    db.init_schema()
    c = db.get_card_by_name(name)
    if not c:
        matches = db.search_cards(name, limit=1)
        c = matches[0] if matches else None
    if not c:
        console.print(f"[red]Card '{name}' not found in local database. Run `juuudge sync` first.[/red]")
        return
    rulings_str = "\n".join([f"* ({r['date']}) {r['text']}" for r in c.rulings])
    md = f"""# {c.name} {c.mana_cost}
*{c.type_line}*

{c.oracle_text}

---
**Gatherer Rulings:**
{rulings_str or '_No rulings on record._'}

[Scryfall]({c.scryfall_search_url})
"""
    console.print(Markdown(md))

@main.command()
@click.argument("rule_id")
def rule(rule_id: str):
    """Look up an official MTG Comprehensive Rule by ID (e.g. 613.1d)."""
    app_dir = get_app_dir()
    db = Database(app_dir / "juuudge.db")
    db.init_schema()
    r = db.get_rule_by_id(rule_id)
    if not r:
        console.print(f"[red]Rule '{rule_id}' not found. Run `juuudge sync` first.[/red]")
        return
    examples_str = "\n".join([f"> _{ex}_" for ex in r.examples])
    md = f"""# CR {r.rule_id} ({r.section})
{r.text}

{examples_str}

[Yawgatog Link]({r.yawgatog_url})
"""
    console.print(Markdown(md))

@main.command()
@click.option("--force", is_flag=True, help="Force re-download of all data.")
def sync(force: bool):
    """Download and sync Scryfall cards and MTG Comprehensive Rules."""
    async def _run():
        app_dir = get_app_dir()
        db = Database(app_dir / "juuudge.db")
        db.init_schema()
        vec_store = VectorStore(app_dir / "lancedb")
        
        with console.status("[bold green]Starting sync...") as status:
            def on_progress(msg: str):
                status.update(f"[bold green]{msg}")
            
            await sync_all_data(db, vec_store, cache_dir=app_dir / "cache", on_progress=on_progress)
            console.print("[bold green]✓ Database sync complete![/bold green]")

    asyncio.run(_run())
