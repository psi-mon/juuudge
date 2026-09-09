import webbrowser
from pathlib import Path
from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Input, Static, Markdown as TextualMarkdown
from juuudge.config import get_config, get_app_dir, validate_provider_setup
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.agent.providers.anthropic_provider import AnthropicProvider
from juuudge.agent.providers.ollama_provider import OllamaProvider
from juuudge.agent.judge_loop import JudgeAgent
from juuudge.tui.widgets import HelpModal, SetupModal, CardInspectorWidget, RuleInspectorWidget
from juuudge.models import Card, Rule
from juuudge.constants import TUI_CSS, DEFAULT_DB_FILENAME, DEFAULT_LANCEDB_DIRNAME

class JuuudgeApp(App):
    CSS = TUI_CSS

    BINDINGS = [
        ("question_mark", "show_help", "Help (?)"),
        ("ctrl+s", "show_setup", "Setup"),
        ("ctrl+l", "clear_chat", "Clear Chat"),
        ("ctrl+o", "open_link", "Open Link"),
        ("ctrl+k", "focus_input", "Focus Input"),
        ("slash", "focus_input", "Focus Input (/)"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, db: Optional[Database] = None, vec_store: Optional[VectorStore] = None):
        super().__init__()
        app_dir = get_app_dir()
        self.db = db or Database(app_dir / DEFAULT_DB_FILENAME)
        self.vec_store = vec_store or VectorStore(app_dir / DEFAULT_LANCEDB_DIRNAME)
        self.db.init_schema()
        self.cfg = get_config(self.db)

        self._init_agent()
        self.chat_history: list[str] = []
        self.last_cards: list[Card] = []
        self.last_rules: list[Rule] = []

    def _init_agent(self):
        if self.cfg.llm.provider == "ollama":
            provider = OllamaProvider(host=self.cfg.llm.ollama_host, model=self.cfg.llm.model)
        else:
            provider = AnthropicProvider(api_key=self.cfg.llm.api_key, model=self.cfg.llm.model)
        self.agent = JudgeAgent(self.db, self.vec_store, provider, max_rounds=self.cfg.llm.max_tool_rounds)

    def _reload_provider(self):
        self.cfg = get_config(self.db)
        self._init_agent()
        chat = self.query_one("#chat-content", Static)
        self.chat_history.append(f"\n\n[bold green]✓ Provider reconfigured:[/bold green] {self.cfg.llm.provider} ({self.cfg.llm.model})")
        chat.update("".join(self.chat_history))

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            with VerticalScroll(id="chat-pane"):
                yield Static("# Welcome to juuudge - MTG Rules Judge CLI\nAsk any rules or card interaction question below.", id="chat-content")
            with Vertical(id="side-pane"):
                yield CardInspectorWidget(id="card-pane")
                yield RuleInspectorWidget(id="rule-pane")
        yield Input(placeholder="Ask a rules question (e.g. 'Does Blood Moon kill Urza's Saga?')...", id="input-box")
        yield Footer()

    def action_show_help(self):
        self.push_screen(HelpModal())

    def action_show_setup(self):
        self.push_screen(SetupModal(self.db, on_saved=self._reload_provider))

    def action_clear_chat(self):
        self.chat_history.clear()
        chat = self.query_one("#chat-content", Static)
        chat.update("Chat cleared.")

    def action_focus_input(self):
        self.query_one("#input-box", Input).focus()

    def action_open_link(self):
        if self.last_cards:
            webbrowser.open(self.last_cards[0].scryfall_search_url)
        elif self.last_rules:
            webbrowser.open(self.last_rules[0].yawgatog_url)

    async def on_input_submitted(self, event: Input.Submitted):
        query = event.value.strip()
        if not query:
            return
        event.input.value = ""

        # Validate provider setup before attempting agent call
        valid, error_msg = validate_provider_setup(self.cfg)
        if not valid:
            chat = self.query_one("#chat-content", Static)
            self.chat_history.append(
                f"\n\n**Player:** {query}\n\n"
                f"[bold red]⚠️ Provider Setup Required:[/bold red] {error_msg}\n"
                f"Opening setup dialog now (or press [bold green]Ctrl+S[/bold green] / run `juuudge setup`)."
            )
            chat.update("".join(self.chat_history))
            self.push_screen(SetupModal(self.db, on_saved=self._reload_provider))
            return
        
        chat = self.query_one("#chat-content", Static)
        self.chat_history.append(f"\n\n**Player:** {query}\n\n**juuudge:** ")
        chat.update("".join(self.chat_history))

        card_widget = self.query_one("#card-pane", CardInspectorWidget)
        rule_widget = self.query_one("#rule-pane", RuleInspectorWidget)

        async for chunk in self.agent.ask_stream(query):
            if chunk["type"] == "cards_found":
                self.last_cards = chunk["cards"]
                card_widget.update_cards(self.last_cards)
            elif chunk["type"] == "rules_found":
                self.last_rules = chunk["rules"]
                rule_widget.update_rules(self.last_rules)
            elif chunk["type"] == "token":
                self.chat_history[-1] += chunk["text"]
                chat.update("".join(self.chat_history))
