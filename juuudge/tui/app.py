import webbrowser
from pathlib import Path
from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Input, Static, Markdown as TextualMarkdown
from juuudge.config import get_config, get_app_dir
from juuudge.storage.db import Database
from juuudge.storage.vector import VectorStore
from juuudge.agent.providers.anthropic_provider import AnthropicProvider
from juuudge.agent.providers.ollama_provider import OllamaProvider
from juuudge.agent.judge_loop import JudgeAgent
from juuudge.tui.widgets import HelpModal, CardInspectorWidget, RuleInspectorWidget
from juuudge.models import Card, Rule

class JuuudgeApp(App):
    CSS = """
    Screen {
        background: #121214;
        color: #E1E1E6;
    }
    #main-container {
        height: 1fr;
    }
    #chat-pane {
        width: 60%;
        border-right: solid #29292E;
        padding: 1 2;
    }
    #side-pane {
        width: 40%;
    }
    #card-pane {
        height: 50%;
        border-bottom: solid #29292E;
        padding: 1;
    }
    #rule-pane {
        height: 50%;
        padding: 1;
    }
    #input-box {
        dock: bottom;
        margin: 1;
        border: tall #00875F;
    }
    .dim-text {
        color: #7C7C8A;
    }
    #help-dialog {
        background: #202024;
        border: thick #00875F;
        padding: 2;
        width: 60;
        height: auto;
        align: center middle;
    }
    #help-title {
        text-style: bold;
        color: #00B37E;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("question_mark", "show_help", "Help (?)"),
        ("ctrl+l", "clear_chat", "Clear Chat"),
        ("ctrl+o", "open_link", "Open Link"),
        ("ctrl+k", "focus_input", "Focus Input"),
        ("slash", "focus_input", "Focus Input (/)"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, db: Optional[Database] = None, vec_store: Optional[VectorStore] = None):
        super().__init__()
        self.cfg = get_config()
        app_dir = get_app_dir()
        self.db = db or Database(app_dir / "juuudge.db")
        self.vec_store = vec_store or VectorStore(app_dir / "lancedb")
        self.db.init_schema()

        if self.cfg.llm.provider == "ollama":
            provider = OllamaProvider(host=self.cfg.llm.ollama_host, model=self.cfg.llm.model)
        else:
            provider = AnthropicProvider(api_key=self.cfg.llm.api_key, model=self.cfg.llm.model)

        self.agent = JudgeAgent(self.db, self.vec_store, provider, max_rounds=self.cfg.llm.max_tool_rounds)
        self.chat_history: list[str] = []
        self.last_cards: list[Card] = []
        self.last_rules: list[Rule] = []

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
