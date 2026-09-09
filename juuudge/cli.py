from typing import Optional
import asyncio
import click
from rich.console import Console
from rich.markdown import Markdown
from juuudge.config import get_config, get_app_dir, validate_provider_setup
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.ingest.sync import sync_all_data
from juuudge.agent.providers.anthropic_provider import AnthropicProvider
from juuudge.agent.providers.ollama_provider import OllamaProvider
from juuudge.agent.judge_loop import JudgeAgent
from juuudge.constants import (
    DEFAULT_DB_FILENAME,
    DEFAULT_LANCEDB_DIRNAME,
    DEFAULT_CACHE_DIRNAME,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_HOST,
)

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
@click.option("--provider", type=click.Choice(["anthropic", "ollama", "llama"], case_sensitive=False), help="Provider to configure.")
@click.option("--api-key", help="Anthropic API key.")
@click.option("--model", help="LLM Model name.")
@click.option("--host", help="Ollama host URL.")
@click.option("--show", is_flag=True, help="Display current provider configuration.")
def setup(provider: Optional[str], api_key: Optional[str], model: Optional[str], host: Optional[str], show: bool = False):
    """Configure LLM provider and credentials for juuudge."""
    app_dir = get_app_dir()
    db = Database(app_dir / DEFAULT_DB_FILENAME)
    db.init_schema()

    if show:
        cfg = get_config(db)
        console.print("[bold cyan]══════════════════════════════════════════════════════[/bold cyan]")
        console.print("[bold white]          Current juuudge Provider Configuration[/bold white]")
        console.print("[bold cyan]══════════════════════════════════════════════════════[/bold cyan]\n")
        if not db.is_provider_configured() and not cfg.setup_completed:
            console.print("[yellow]No provider configured yet.[/yellow]")
            console.print("Run [bold green]juuudge setup[/bold green] to configure your provider.\n")
            return

        active_provider = cfg.llm.provider
        console.print(f"[bold white]Provider:[/bold white]     [green]{active_provider}[/green]")
        console.print(f"[bold white]Model:[/bold white]        [green]{cfg.llm.model}[/green]")
        if active_provider == "anthropic":
            key_display = cfg.llm.api_key if cfg.llm.api_key else "[dim]<not set>[/dim]"
            console.print(f"[bold white]API Key:[/bold white]      [yellow]{key_display}[/yellow]")
        elif active_provider in ("ollama", "llama"):
            console.print(f"[bold white]Host:[/bold white]         [green]{cfg.llm.ollama_host}[/green]")
        console.print("")
        return

    console.print("[bold cyan]══════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold white]            juuudge Provider Setup[/bold white]")
    console.print("[bold cyan]══════════════════════════════════════════════════════[/bold cyan]\n")

    if not provider:
        console.print("Select your LLM provider:")
        console.print("  [1] Anthropic (Claude 3.7 Sonnet, etc.)")
        console.print("  [2] Ollama / Llama (Local LLM)\n")
        choice = click.prompt("Enter choice", type=click.Choice(["1", "2", "anthropic", "ollama", "llama"]), default="1")
        if choice in ("1", "anthropic"):
            provider = "anthropic"
        else:
            provider = "ollama"

    provider = provider.lower()
    if provider == "llama":
        provider = "ollama"

    if provider == "anthropic":
        if not api_key:
            api_key = click.prompt("Enter your Anthropic API Key (input is hidden)", hide_input=True, type=str)
        if not model:
            model = click.prompt("Model name", default=DEFAULT_ANTHROPIC_MODEL)
        
        db.save_provider_config(provider="anthropic", api_key=api_key, model=model)
        console.print("\n[bold green]✓ Anthropic provider configured successfully![/bold green]")
        console.print(f"[dim]API key encrypted and saved. Model: {model}[/dim]\n")

    elif provider == "ollama":
        if not host:
            host = click.prompt("Ollama Host URL", default=DEFAULT_OLLAMA_HOST)
        if not model:
            model = click.prompt("Model name", default=DEFAULT_OLLAMA_MODEL)

        db.save_provider_config(provider="ollama", host=host, model=model)
        console.print("\n[bold green]✓ Ollama provider configured successfully![/bold green]")
        console.print(f"[dim]Host: {host} | Model: {model}[/dim]\n")

@main.command()
@click.argument("question")
def ask(question: str):
    """Ask a rules question directly from stdout."""
    async def _run():
        app_dir = get_app_dir()
        db = Database(app_dir / DEFAULT_DB_FILENAME)
        db.init_schema()
        cfg = get_config(db)

        valid, error_msg = validate_provider_setup(cfg)
        if not valid:
            console.print(f"[bold red]Error:[/bold red] {error_msg}")
            return

        vec_store = VectorStore(app_dir / DEFAULT_LANCEDB_DIRNAME)
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
    db = Database(app_dir / DEFAULT_DB_FILENAME)
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
    db = Database(app_dir / DEFAULT_DB_FILENAME)
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
        db = Database(app_dir / DEFAULT_DB_FILENAME)
        db.init_schema()
        vec_store = VectorStore(app_dir / DEFAULT_LANCEDB_DIRNAME)
        
        with console.status("[bold green]Starting sync...") as status:
            def on_progress(msg: str):
                status.update(f"[bold green]{msg}")
            
            await sync_all_data(db, vec_store, cache_dir=app_dir / DEFAULT_CACHE_DIRNAME, on_progress=on_progress)
            console.print("[bold green]✓ Database sync complete![/bold green]")

    asyncio.run(_run())
