import webbrowser
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button, Label, Markdown as TextualMarkdown
from juuudge.models import Card, Rule

class HelpModal(ModalScreen):
    """Interactive help modal showing keybindings."""
    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("juuudge - MTG Rules Judge Keybindings", id="help-title"),
            Static("""
- [b]Enter[/b]: Submit question or command
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
