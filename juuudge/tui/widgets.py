import webbrowser
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button, Label, Markdown as TextualMarkdown
from juuudge.models import Card, Rule
from juuudge.constants import DEFAULT_ANTHROPIC_MODEL, DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_HOST

class HelpModal(ModalScreen):
    """Interactive help modal showing keybindings."""
    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("juuudge - MTG Rules Judge Keybindings", id="help-title"),
            Static("""
- [b]Enter[/b]: Submit question or command
- [b]Ctrl+S[/b]: Open Provider Setup (Anthropic / Ollama)
- [b]Tab / Shift+Tab[/b]: Switch focus between panels
- [b]?[/b] or [b]Shift+?[/b]: Show this Help modal
- [b]Ctrl+O[/b]: Open selected Card / Rule link in browser
- [b]Ctrl+L[/b]: Clear chat history
- [b]Ctrl+K[/b] or [b]/[/b]: Focus question input
- [b]Esc / q[/b]: Close modal or exit
            """),
            Button("Close", variant="primary", id="close-btn"),
            id="help-dialog"
        )

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss()

class SetupModal(ModalScreen[bool]):
    """Interactive provider setup modal."""
    BINDINGS = [("escape", "dismiss_cancel", "Cancel")]

    def __init__(self, db, on_saved=None):
        super().__init__()
        self.db = db
        self.on_saved = on_saved
        p_cfg = db.get_provider_config() if db else {}
        self.provider = p_cfg.get("provider") or "anthropic"
        self.current_api_key = p_cfg.get("api_key", "")
        self.current_model = p_cfg.get("model", "")
        self.current_host = p_cfg.get("ollama_host", "")

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("juuudge - Provider Setup", id="setup-title"),
            Static("Select your LLM provider and configure credentials:"),
            Horizontal(
                Button("Anthropic", id="btn-prov-anthropic", variant="primary" if self.provider == "anthropic" else "default"),
                Button("Ollama / Llama", id="btn-prov-ollama", variant="primary" if self.provider == "ollama" else "default"),
                classes="setup-field"
            ),
            Label("Anthropic API Key (hidden in DB):", id="lbl-api-key"),
            Input(value=self.current_api_key, placeholder="sk-ant-...", password=True, id="input-api-key"),
            Label("Model Name:", id="lbl-model"),
            Input(value=self.current_model or (DEFAULT_ANTHROPIC_MODEL if self.provider == "anthropic" else DEFAULT_OLLAMA_MODEL), placeholder="Model name", id="input-model"),
            Label("Ollama Host URL (for Ollama only):", id="lbl-host"),
            Input(value=self.current_host or DEFAULT_OLLAMA_HOST, placeholder=DEFAULT_OLLAMA_HOST, id="input-host"),
            Horizontal(
                Button("Save & Apply", variant="success", id="btn-save-setup"),
                Button("Cancel", variant="error", id="btn-cancel-setup"),
                classes="setup-buttons"
            ),
            id="setup-dialog"
        )

    def action_dismiss_cancel(self):
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed):
        btn_id = event.button.id
        if btn_id == "btn-prov-anthropic":
            self.provider = "anthropic"
            self.query_one("#btn-prov-anthropic", Button).variant = "primary"
            self.query_one("#btn-prov-ollama", Button).variant = "default"
            model_input = self.query_one("#input-model", Input)
            if not model_input.value or model_input.value == DEFAULT_OLLAMA_MODEL:
                model_input.value = DEFAULT_ANTHROPIC_MODEL
        elif btn_id == "btn-prov-ollama":
            self.provider = "ollama"
            self.query_one("#btn-prov-anthropic", Button).variant = "default"
            self.query_one("#btn-prov-ollama", Button).variant = "primary"
            model_input = self.query_one("#input-model", Input)
            if not model_input.value or model_input.value == DEFAULT_ANTHROPIC_MODEL:
                model_input.value = DEFAULT_OLLAMA_MODEL
        elif btn_id == "btn-cancel-setup":
            self.dismiss(False)
        elif btn_id == "btn-save-setup":
            api_key = self.query_one("#input-api-key", Input).value.strip()
            model = self.query_one("#input-model", Input).value.strip()
            host = self.query_one("#input-host", Input).value.strip()

            if self.provider == "anthropic":
                self.db.save_provider_config(provider="anthropic", api_key=api_key, model=model or DEFAULT_ANTHROPIC_MODEL)
            else:
                self.db.save_provider_config(provider="ollama", host=host or DEFAULT_OLLAMA_HOST, model=model or DEFAULT_OLLAMA_MODEL)

            if self.on_saved:
                self.on_saved()
            self.dismiss(True)

class CardInspectorWidget(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield TextualMarkdown("No cards currently selected.\nMention cards in `[[brackets]]` or natural language.", id="card-markdown", classes="dim-text")

    def update_cards(self, cards: list[Card]):
        widget = self.query_one("#card-markdown", TextualMarkdown)
        if not cards:
            widget.update("No cards currently selected.\nMention cards in `[[brackets]]` or natural language.")
            return
        cards_md = []
        for card in cards:
            rulings_md = "\n".join([f"* **({r['date']})** {r['text']}" for r in card.rulings])
            cards_md.append(f"""### {card.name} `{card.mana_cost}`
*{card.type_line}*

{card.oracle_text}

---
**Gatherer Rulings:**
{rulings_md or '_No rulings on record._'}

[Scryfall Link]({card.scryfall_search_url})
""")
        widget.update("\n\n---\n\n".join(cards_md))

class RuleInspectorWidget(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield TextualMarkdown("No rules currently cited.", id="rule-markdown", classes="dim-text")

    def update_rules(self, rules: list[Rule]):
        widget = self.query_one("#rule-markdown", TextualMarkdown)
        if not rules:
            widget.update("No rules currently cited.")
            return
        rules_md = []
        for rule in rules:
            examples_md = "\n".join([f"> _{ex}_" for ex in rule.examples])
            rules_md.append(f"""### CR {rule.rule_id}
**{rule.section}**

{rule.text}

{examples_md}

[Yawgatog Link]({rule.yawgatog_url})
""")
        widget.update("\n\n---\n\n".join(rules_md))

class LogInspectorWidget(Static):
    """Widget displaying the 10 most recent application logs with severity styling."""

    SEVERITY_STYLES = {
        "LOG": "dim cyan",
        "INFO": "bold green",
        "WARN": "bold yellow",
        "ERROR": "bold red",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_text = ""

    def on_mount(self):
        from juuudge.logger import add_log_listener
        self.refresh_logs()
        add_log_listener(self._on_new_log)

    def on_unmount(self):
        from juuudge.logger import remove_log_listener
        remove_log_listener(self._on_new_log)

    def _on_new_log(self, entry):
        try:
            self.app.call_from_thread(self.refresh_logs)
        except Exception:
            self.refresh_logs()

    def refresh_logs(self):
        from juuudge.logger import get_recent_logs
        logs = get_recent_logs()
        if not logs:
            self._current_text = "[dim]Live Logs (0/10) - System initialized[/dim]"
            self.update(self._current_text)
            return

        formatted_lines = ["[bold white]── Live Logs (Latest 10) ──[/bold white]"]
        for entry in logs:
            style = self.SEVERITY_STYLES.get(entry.severity, "white")
            time_str = entry.timestamp.split()[1] if " " in entry.timestamp else entry.timestamp
            line = f"[dim]{time_str}[/dim] [{style}][{entry.severity}][/{style}] [dim]{entry.source}[/dim] {entry.message}"
            formatted_lines.append(line)

        self._current_text = "\n".join(formatted_lines)
        self.update(self._current_text)

    @property
    def renderable(self) -> str:
        return self._current_text
