from typing import List, Dict, Any
from juuudge.models import Card

def parse_scryfall_cards(cards_data: List[Dict[str, Any]], rulings_data: List[Dict[str, Any]] | None = None) -> List[Card]:
    # Index rulings by oracle_id or card id
    rulings_by_id: Dict[str, List[Dict[str, str]]] = {}
    if rulings_data:
        for r in rulings_data:
            c_id = r.get("oracle_id") or r.get("card_id") or ""
            if c_id:
                rulings_by_id.setdefault(c_id, []).append({
                    "date": r.get("published_at", ""),
                    "text": r.get("comment", "")
                })

    seen_names = set()
    cards: List[Card] = []

    for item in cards_data:
        # Filter non-playable tokens / art cards if needed
        layout = item.get("layout", "")
        if layout in ("token", "art_series", "double_faced_token"):
            continue

        name = item.get("name", "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        # Handle double-faced / multi-face cards
        mana_cost = item.get("mana_cost", "")
        type_line = item.get("type_line", "")
        oracle_text = item.get("oracle_text", "")
        power = item.get("power")
        toughness = item.get("toughness")
        loyalty = item.get("loyalty")
        defense = item.get("defense")

        if "card_faces" in item and not oracle_text:
            face_texts = []
            for face in item["card_faces"]:
                face_name = face.get("name", "")
                face_type = face.get("type_line", "")
                face_oracle = face.get("oracle_text", "")
                face_texts.append(f"[{face_name} - {face_type}]\n{face_oracle}")
            oracle_text = "\n//\n".join(face_texts)

        c_id = item.get("oracle_id") or item.get("id") or ""
        card_rulings = rulings_by_id.get(c_id, [])

        cards.append(Card(
            name=name,
            mana_cost=mana_cost,
            type_line=type_line,
            oracle_text=oracle_text,
            power=power,
            toughness=toughness,
            loyalty=loyalty,
            defense=defense,
            keywords=item.get("keywords", []),
            rulings=card_rulings,
            scryfall_uri=item.get("scryfall_uri", "")
        ))

    return cards
