# Design Document: `juuudge` - Magic: The Gathering Rules AI Agent CLI

**Date:** 2026-09-04  
**Status:** Approved  
**Author:** Antigravity & User  

---

## 1. Overview & Goals

`juuudge` is a high-performance terminal CLI and interactive TUI (Terminal User Interface) AI assistant specialized in adjudicating Magic: The Gathering (MTG) rules, interactions, priority timing, and layer system mechanics.

### Primary Objectives
1. **Accurate & Authoritative MTG Rules Grounding:** Prevent AI hallucinations by grounding all answers with official WotC Comprehensive Rules (CR) text, Scryfall Oracle card texts, and Gatherer rulings.
2. **Fast & Intuitive 3-Pane Textual TUI:** Deliver a split-pane interface showing the chat verdict, active card oracle/rulings, and cited comprehensive rules side-by-side.
3. **Rich Web References:** Automatically embed clickable links to Scryfall for card lookups and official online rules resources (e.g. Yawgatog / WotC anchors) for rule verification.
4. **Offline-Capable Local RAG Engine:** Cache Scryfall bulk cards and WotC Comprehensive Rules locally in SQLite with FTS5 lexical indexing and local CPU embeddings (`fastembed`).
5. **Multi-Model Support:** Native integration with Anthropic Claude (`claude-3-7-sonnet`, `claude-3-5-haiku`), Google Gemini, OpenAI, and local Ollama models. Default configured for Anthropic API key during development.

---

## 2. Architecture & Data Ingestion

```
+-----------------------------------------------------------------------------+
|                           DATA INGESTION (`juuudge sync`)                   |
|                                                                             |
|  [Scryfall Bulk API]                  [Wizards of the Coast (WotC)]         |
|  (default-cards.json & rulings)       (MagicCompRules.txt)                  |
|          │                                     │                            |
|          ▼                                     ▼                            |
|  ┌──────────────┐                     ┌──────────────────────────┐          |
|  │ Card Parser  │                     │ Hierarchical CR Parser   │          |
|  └──────┬───────┘                     └────────────┬─────────────┘          |
|         │                                          │                        |
|         │                                ┌─────────┴──────────┐             |
|         │                                ▼                    ▼             |
|         │                        ┌──────────────┐     ┌──────────────┐      |
|         │                        │ Rules Tree   │     │ Local Vector │      |
|         │                        │ & Glossary   │     │ Embedder     │      |
|         │                        └──────┬───────┘     └──────┬───────┘      |
|         ▼                               ▼                    ▼              |
|  ╔═══════════════════════════════════════════════════════════════════════╗  |
|  ║              Local Storage SQLite DB (~/.juuudge/juuudge.db)          ║  |
|  ║  • cards & cards_fts (Oracle, Mana, Types, Rulings, Scryfall URIs)    ║  |
|  ║  • rules & rules_fts (Chapter, Section, Rule ID, Text, Examples)      ║  |
|  ║  • glossary & glossary_fts (MTG Legal Definitions)                    ║  |
|  ║  • vector_index (Dense embeddings for semantic rule retrieval)        ║  |
|  ╚═══════════════════════════════════════════════════════════════════════╝  |
+-----------------------------------------------------------------------------+
```

### 2.1 Storage Layout
* Directory: `~/.juuudge/` (or `$XDG_DATA_HOME/juuudge/`)
  * `juuudge.db`: SQLite database holding cards, rulings, rules, glossary, and vector tables.
  * `config.toml`: User configuration.
  * `cache/`: Downloaded raw Scryfall bulk JSON and `MagicCompRules.txt` with checksum tracking.

### 2.2 Hierarchical Comprehensive Rules (CR) Chunking
Rather than naive token-window splitting, `juuudge` parses the CR along its natural legal hierarchy:
* **Sub-rule Records:** Atomic rules (`613.1a`, `704.5s`, `603.3`) linked to parent sections and chapters with examples attached.
* **Section Records:** Macro-sections (e.g. `613. Interaction of Continuous Effects`) for high-level conceptual matching.
* **Glossary Records:** Dedicated entries for ~400 defined terms (*"Active Player"*, *"Priority"*, *"Replacement Effect"*, *"State-Based Action"*).

---

## 3. Query Processing & Hybrid RAG Engine

```
User Query: "Does Blood Moon kill Urza's Saga?"
    │
    ├──► 1. Card Name Extractor
    │    ├── Regex & `[[Card Name]]` syntax
    │    ├── Trigram / Levenshtein fuzzy matching ("bowmasters" -> "Orcish Bowmasters")
    │    ├── Community slang mapping ("Bob" -> "Dark Confidant", "Swat" -> "Deflecting Swat")
    │    └── Output: [Blood Moon], [Urza's Saga] -> Emit CardEvent to TUI Card Pane
    │
    ├──► 2. Hybrid Rules Retriever
    │    ├── Lexical BM25 (SQLite FTS5) on rules and glossary
    │    ├── Semantic Dense Vector Search via `fastembed` (bge-small-en-v1.5)
    │    ├── Reciprocal Rank Fusion (RRF) deduplication
    │    └── Output: Top-K CR Rules (e.g. CR 613.1d, CR 704.5s) -> Emit RuleEvent to TUI Rule Pane
    │
    └──► 3. Prompt Assembler & LLM Engine
         ├── Persona: Certified Level 2/3 MTG Judge
         ├── Grounding: Injected Oracle Texts, Card Rulings, and CR Rule Chunks
         └── Output: Structured Verdict streamed to TUI Chat Pane with Markdown Links
```

### 3.1 Verdict Output Format
1. **Verdict (TL;DR):** Immediate direct ruling.
2. **Step-by-Step Breakdown:** Ordered mechanics resolution (Layers $\to$ Priority $\to$ Triggers $\to$ SBAs).
3. **Official Links & Citations:**
   * Card names formatted with Scryfall URLs: `[Card Name](https://scryfall.com/search?q=%21"Card+Name")`.
   * Rule citations formatted with anchor links: `[CR 613.1d](https://yawgatog.com/resources/magic-rules/#R6131d)`.

---

## 4. User Interface & Experience (Textual TUI & CLI)

### 4.1 3-Pane Responsive Layout
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

### 4.2 Keybindings & Navigation
* `Tab` / `Shift+Tab`: Cycle focus across Chat, Card Inspector, and Rules Inspector.
* `Enter`: Submit question.
* `?` / `Shift + ?`: Open full **Help & Keybindings Modal**.
* `Ctrl+O`: Open selected Card (Scryfall) or Rule (Yawgatog) in user's default browser.
* `Ctrl+L`: Clear active chat history.
* `Ctrl+K` or `/`: Focus question input bar.
* `Esc` / `q`: Close modals or exit.

### 4.3 CLI Commands & Scripting Interface
* `juuudge`: Launch interactive TUI.
* `juuudge ask "..."`: One-shot query printed directly to stdout with colors and links.
* `juuudge card "<name>"`: Instant offline card oracle & rulings lookup.
* `juuudge rule "<id or query>"`: Instant offline rule text lookup.
* `juuudge sync [--force]`: Syncs card and rules databases.

---

## 5. Configuration & Multi-Provider Support

### 5.1 Configuration File (`~/.juuudge/config.toml`)
```toml
[general]
theme = "dark" # "dracula", "nord", "gruvbox", "monokai"

[llm]
provider = "anthropic" # "anthropic", "gemini", "openai", "ollama"
model = "claude-3-7-sonnet"
api_key = "" # Automatically loads from ANTHROPIC_API_KEY environment variable
temperature = 0.0

[rag]
top_k_rules = 5
top_k_glossary = 2
embedder = "fastembed"
```

### 5.2 Error Handling & First-Run Experience
* **Auto-Sync Prompt:** If run with an unpopulated database, `juuudge` shows an onboarding progress bar to sync Scryfall and CR data before proceeding.
* **Graceful Degradation:** If offline and no local Ollama model is active, `juuudge card` and `juuudge rule` remain 100% operational as an instant offline MTG reference manual.
* **Disambiguation Modal:** If a card name matches multiple candidates ambiguously, an interactive selector lets the user pick the intended card.

---

## 6. Testing & Quality Strategy
* **Unit Tests (`pytest`):**
  * CR hierarchical parser correctness (chapter, section, sub-rule, and example grouping).
  * Card extractor regex, fuzzy matcher, and slang dictionary accuracy.
  * SQLite FTS5 search and RRF ranking algorithms.
* **Judge Verification Test Suite:**
  * 30+ canonical MTG rules edge-case scenarios:
    - Blood Moon + Urza's Saga (Layer 4 / SBA 704.5s)
    - Humility + Opalescence (Layer 6/7b dependency & timestamp loops)
    - Deflecting Swat targeting Counterspell (Legal spell target switching)
    - Replacement effects ordering (Doubling Season + Hardened Scales on AP/NAP)
    - Commander Zone change rules (CR 903.9a/b vs dies triggers)
* **TUI Integration Tests:** Textual `Pilot` automated headless UI interaction tests.
