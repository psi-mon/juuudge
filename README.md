# juuudge ⚖️

**juuudge** is an offline-capable, interactive AI assistant. It combines deterministic entity extraction, hybrid RAG (SQLite FTS5 + LanceDB dense vector embeddings), hierarchical Comprehensive Rules expansion, and a bounded agentic loop to deliver rulings with official citations.

For a detailed breakdown of the system design and execution sequence, see [Architecture & Flow](architecture.md).

---

## Tech Stack

- **Runtime & CLI**: Python 3.12+ (managed with `uv`), [Click](https://click.palletsprojects.com/), [Rich](https://github.com/Textualize/rich)
- **Interactive TUI**: [Textual](https://textual.textualize.io/) (split 4-pane terminal interface)
- **LLM Engine**: [Anthropic Claude](https://www.anthropic.com/) (Claude 3.7 Sonnet default) and local [Ollama](https://ollama.com/) (Llama 3.3)
- **Relational & Search**: SQLite3 with FTS5 BM25 full-text search
- **Vector Database & Embeddings**: [LanceDB](https://lancedb.github.io/lancedb/) + [FastEmbed](https://qdrant.github.io/fastembed/) (`BAAI/bge-small-en-v1.5`)
- **Entity Matching**: [RapidFuzz](https://github.com/maxbachmann/RapidFuzz) for fuzzy card matching
- **Data Ingestion**: Official Wizards of the Coast Comprehensive Rules & Scryfall Bulk Data API

---

## Architecture

```
User Query ──► Card Extraction ──► Hybrid Rule Retrieval ──► Grounded Agent Loop ──► Streamed Verdict
                      │                        │                      │
                      ▼                        ▼                      ▼
                 SQLite + FTS5         LanceDB Vectors        Claude / Ollama
```

See [architecture.md](architecture.md) for full component documentation and end-to-end sequence diagrams.

---

## User Interface & Hotkeys

The interactive TUI provides a 4-pane layout:

- **Chat Pane** (Top-Left): Displays user questions and streamed judge verdicts with step-by-step resolution and citations.
- **Live Logs Inspector** (Bottom-Left): Displays the 10 most recent system logs with severity levels (`LOG`, `INFO`, `WARN`, `ERROR`).
- **Card Inspector** (Top-Right): Shows Oracle text, mana cost, card types, and official Gatherer rulings for cards referenced in the query.
- **Rule Inspector** (Bottom-Right): Shows exact Comprehensive Rules text, section headers, hierarchical sibling rules, and examples.

```
+-----------------------------------------------------------------------------+
| JUUUDGE - MTG Rules Judge CLI                           [claude-3-7-sonnet] |
+----------------------------------------+------------------------------------+
|  CHAT & VERDICT PANE (60% width)       |  CARD INSPECTOR (40% width, Top)   |
|                                        |  [Blood Moon] {2}{R}               |
|  > Does Blood Moon kill Urza's Saga?   |  Enchantment                       |
|                                        |  Nonbasic lands are Mountains.     |
|  VERDICT:                              |  [Scryfall Link] [Gatherer Rulings]|
|  Yes, Urza's Saga will be put into     +------------------------------------+
|  the graveyard as a state-based        |  RULES INSPECTOR (40% width, Bot)  |
|  action immediately after Blood Moon   |  CR 704.5s (State-Based Actions)   |
|  resolves.                             |  If a Saga has lore counters >=    |
|                                        |  final chapter number and isn't... |
|  STEP-BY-STEP BREAKDOWN:               |                                    |
|  1. In Layer 4 (CR 613.1d), Blood...   |  CR 613.1d (Layer 4 - Type Change) |
|  2. Urza's Saga loses all chapter...   |  [Yawgatog Link]                   |
|  3. CR 704.5s puts it into GY...       |                                    |
+----------------------------------------+------------------------------------+
| > Enter rules question or /command...             [?: Help] [Tab: Switch]   |
+-----------------------------------------------------------------------------+
```

### Available Hotkeys

| Hotkey            | Action                                                                  |
| ----------------- | ----------------------------------------------------------------------- |
| `?`               | Open Help dialog with keyboard shortcut guide                           |
| `Ctrl + S`        | Open Provider Setup dialog (switch between Anthropic & Ollama)          |
| `Ctrl + L`        | Clear active chat history                                               |
| `Ctrl + O`        | Open referenced card in Scryfall or rule in Yawgatog in default browser |
| `Ctrl + K` or `/` | Focus the question input box                                            |
| `Esc`             | Dismiss any open modal dialog                                           |
| `q`               | Quit application                                                        |

---

## How to Run

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/psi-mon/juuudge.git
cd juuudge

# Install dependencies with uv
uv sync
```

### 2. Initial Data Sync

Download and index the latest MTG Comprehensive Rules and Scryfall card database:

```bash
# Sync cards and rules into local SQLite and LanceDB
juuudge sync
```

### 3. Provider Setup

Configure your LLM provider (Anthropic or Ollama):

```bash
# Interactive setup
juuudge setup

# Or non-interactive setup:
juuudge setup --provider anthropic --api-key "sk-ant-api03-..."
# Or for local Ollama:
juuudge setup --provider ollama --model llama3.3 --host http://localhost:11434

# View current configuration
juuudge setup --show
```

### 4. Launching the App

```bash
# Launch interactive 4-pane TUI
juuudge

# Or ask a question directly from the CLI
juuudge ask "Does Blood Moon kill Urza's Saga?"

# Inspect a card
juuudge card "Blood Moon"

# Inspect a Comprehensive Rule
juuudge rule 613.1d
```

---

## Testing

Run the test suite:

```bash
.venv/bin/pytest tests/ -v
```
