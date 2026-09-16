# juuudge test prompts

Hard rules questions for manual evaluation. Copy the **Prompt** into the TUI or:

```bash
juuudge ask "$(cat <<'EOF'
PASTE PROMPT HERE
EOF
)"
```

Add new entries below using the same sections. Keep **Prompt** self-contained (board, whose turn, the question) so juuudge does not need this file.

---

## 1. Humility + Opalescence

- **Tags:** layers, type-changing, ability-removing, P/T, timestamps
- **Difficulty:** hard
- **Why it's hard:** Two global static abilities apply in different layers. Type-changing (layer 4) sticks even after the ability is lost in layer 6; power/toughness (layer 7b) does not.

**Board**

- Two-player game, no other relevant effects.
- You control [[Humility]] and [[Opalescence]] (both non-Aura enchantments).
- No other creatures or type-changing effects.

**Prompt**

```
I control Humility and Opalescence. No other type-changing or P/T effects are relevant. What is each permanent right now: card types, subtypes, abilities, and power/toughness? Does the order they entered the battlefield change the answer?
```

**Expected**

- Both are enchantment creatures, 1/1, with no abilities.
- Timestamp order does **not** change the answer under current CR.
- Opalescence applies in layer 4 (they become creatures). Humility then applies in layer 6 (creatures lose abilities) and layer 7b (they are 1/1). Opalescence’s “P/T equal to mana value” is a layer 7b effect from an ability that was already lost in layer 6, so it does not apply. Layer 4 results are not rewound.

**CR to cite**

- 613.1c / 613.1d / 613.1f (layer order: type, then abilities, then P/T)
- 613.3 (P/T sublayers; 7b characteristic-setting)
- 613.5 / 613.6 (later layers do not undo earlier ones; losing an ability after it has applied in an earlier layer)
- Gatherer/oracle: Humility, Opalescence

---

## Template

Copy this block for the next question:

### N. Short title

- **Tags:** comma-separated CR topics
- **Difficulty:** medium | hard | degenerate
- **Why it's hard:** one sentence

**Board**

- Players, objects, zones, counters, timing (stack / APNAP / priority).

**Prompt** (fenced code block, self-contained; `[[Card Name]]` is fine)

**Expected**

- Verdict a competent judge would give.
- What a wrong answer usually misses.

**CR to cite**

- Rule IDs (e.g. 704.5s, 613.1d)