import re
from typing import List, Tuple
from juuudge.models import Rule, GlossaryTerm

RULE_ID_PATTERN = re.compile(r'^(\d{3})\.(\d+[a-z]?)\.?\s+(.*)$')
SECTION_HEADER_PATTERN = re.compile(r'^(\d{3})\.\s+(.+)$')
CHAPTER_HEADER_PATTERN = re.compile(r'^(\d)\.\s+(.+)$')

def parse_comprehensive_rules(text: str) -> Tuple[List[Rule], List[GlossaryTerm]]:
    lines = text.splitlines()
    rules: List[Rule] = []
    glossary_terms: List[GlossaryTerm] = []

    current_chapter = ""
    current_section = ""
    current_parent_rule = ""
    current_rule: Rule | None = None
    
    in_glossary = False
    in_contents = False
    current_glossary_term = ""
    current_glossary_def: List[str] = []

    for line in lines:
        raw_line = line.strip()
        if not raw_line:
            continue

        if raw_line == "Contents":
            in_contents = True
            continue

        # Chapter header (e.g. "1. Game Concepts" or "6. Spells, Abilities, and Effects")
        chap_match = CHAPTER_HEADER_PATTERN.match(raw_line)
        if chap_match and in_contents and not current_chapter:
            # We are still in the table of contents until we hit the first chapter body
            pass

        if raw_line == "Glossary" and current_chapter:
            in_glossary = True
            if current_rule:
                rules.append(current_rule)
                current_rule = None
            continue

        if in_glossary:
            # Glossary entries: A line without indentation or leading lowercase is a term, following indented/normal lines are definition
            if not line.startswith(" ") and not line.startswith("\t") and len(raw_line) < 60 and not raw_line.endswith("."):
                if current_glossary_term and current_glossary_def:
                    glossary_terms.append(GlossaryTerm(
                        term=current_glossary_term,
                        definition=" ".join(current_glossary_def)
                    ))
                current_glossary_term = raw_line
                current_glossary_def = []
            else:
                if current_glossary_term:
                    current_glossary_def.append(raw_line)
            continue

        # Section header (e.g. "613. Interaction of Continuous Effects" or "100. General")
        sec_match = SECTION_HEADER_PATTERN.match(raw_line)
        if sec_match:
            in_contents = False
            if current_rule:
                rules.append(current_rule)
                current_rule = None
            current_section = raw_line
            current_parent_rule = sec_match.group(1)
            # Create a Rule record for the section header
            chap_num = current_chapter.split(".")[0].strip() if current_chapter else ""
            rules.append(Rule(
                rule_id=sec_match.group(1),
                chapter=current_chapter or "Rules",
                section=raw_line,
                parent_rule=chap_num,
                text=sec_match.group(2),
                examples=[]
            ))
            continue

        # Chapter header outside contents
        if chap_match and not in_contents:
            current_chapter = raw_line
            continue

        if in_contents:
            continue

        # Examples (e.g. "Example: Blood Moon makes nonbasic lands Mountains.")
        if raw_line.startswith("Example:") or raw_line.startswith("Example 1:") or raw_line.startswith("Example 2:"):
            if current_rule:
                current_rule.examples.append(raw_line)
            continue

        # Numbered Rule (e.g. "613.1d Layer 4: Type-changing...")
        rule_match = RULE_ID_PATTERN.match(raw_line)
        if rule_match:
            if current_rule:
                rules.append(current_rule)

            rule_num = f"{rule_match.group(1)}.{rule_match.group(2)}"
            rule_text = rule_match.group(3)
            parent = rule_match.group(1)
            if "." in rule_match.group(2):
                parent = f"{rule_match.group(1)}.{rule_match.group(2).split('.')[0]}"
            else:
                base_sub = re.match(r'^\d+', rule_match.group(2))
                if base_sub:
                    parent = f"{rule_match.group(1)}.{base_sub.group(0)}"

            current_rule = Rule(
                rule_id=rule_num,
                chapter=current_chapter or "Rules",
                section=current_section or current_chapter or "General",
                parent_rule=parent,
                text=rule_text,
                examples=[]
            )
        else:
            # Continuation of existing rule text
            if current_rule:
                current_rule.text += " " + raw_line

    if current_rule:
        rules.append(current_rule)

    if in_glossary and current_glossary_term and current_glossary_def:
        glossary_terms.append(GlossaryTerm(
            term=current_glossary_term,
            definition=" ".join(current_glossary_def)
        ))

    return rules, glossary_terms
