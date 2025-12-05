"""
MTG Commander Bracket Analyzer - Synergy Analyzer
==================================================

Analyzes deck synergy to help differentiate:
- Theme/art decks (low synergy due to restricted card pool) -> Bracket 1
- Average decks (moderate synergy) -> Bracket 2-3
- Highly synergistic decks (tribal, dedicated engines) -> Bracket 3-4

Key insight for tribal detection:
- Type line tells you what a card IS (often incidental)
- Oracle text tells you what the deck CARES ABOUT (intentional)

Example: Brion "Elder" deck has 30 Humans but 0 oracle mentions of "Human"
         Kyler Human tribal has 20 Humans AND 15+ cards mentioning "Human"
"""

import re
from collections import Counter
from typing import List, Dict, Any, Set, Tuple


class SynergyAnalyzer:
    """
    Calculates how synergistic a deck is based on:
    1. Tribal density (creature type concentration, weighted by intent)
    2. Mechanical themes (keywords and oracle text patterns)
    """
    
    # Creature types that commonly have tribal support
    TRIBAL_TYPES = {
        "Elf", "Elves", "Goblin", "Goblins", "Zombie", "Zombies",
        "Human", "Humans", "Vampire", "Vampires", "Angel", "Angels",
        "Dragon", "Dragons", "Demon", "Demons", "Merfolk", "Wizard", "Wizards",
        "Soldier", "Soldiers", "Knight", "Knights", "Cleric", "Clerics",
        "Warrior", "Warriors", "Shaman", "Shamans", "Druid", "Druids",
        "Beast", "Beasts", "Bird", "Birds", "Cat", "Cats", "Dog", "Dogs",
        "Dinosaur", "Dinosaurs", "Elemental", "Elementals", "Spirit", "Spirits",
        "Sliver", "Slivers", "Ally", "Allies", "Pirate", "Pirates",
        "Rat", "Rats", "Snake", "Snakes", "Spider", "Spiders",
        "Treefolk", "Fungus", "Saproling", "Saprolings",
        "Faerie", "Faeries", "Giant", "Giants", "Kithkin",
        "Artificer", "Artificers", "Rogue", "Rogues", "Assassin", "Assassins",
        "Wolf", "Wolves", "Werewolf", "Werewolves",
        "Sphinx", "Sphinxes", "Horror", "Horrors",
        "Squirrel", "Squirrels", "Frog", "Frogs",
        "Tyranid", "Tyranids", "Astartes", "Phyrexian", "Phyrexians",
        "Ninja", "Ninjas", "Samurai", "Monk", "Monks",
        "Skeleton", "Skeletons", "Insect", "Insects",
    }
    
    def __init__(self):
        # Synergy theme packages
        self.SYNERGY_THEMES = {
            "counters": {
                "keywords": {"counter", "counters", "proliferate", "modified", "adapt"},
                "weight": 1.0,
            },
            "tokens": {
                "keywords": {"token", "tokens", "populate", "convoke"},
                "weight": 0.9,
            },
            "sacrifice": {
                "keywords": {"sacrifice", "sacrificed", "dies", "death", "dying"},
                "weight": 1.2,
            },
            "graveyard": {
                "keywords": {"graveyard", "graveyards", "reanimate", "unearth", "flashback", "escape", "dredge", "delve"},
                "weight": 1.0,
            },
            "etb": {
                "keywords": {"enters the battlefield", "enters", "blink", "flicker"},
                "weight": 1.0,
            },
            "artifacts": {
                "keywords": {"artifact", "artifacts", "equipment", "equip", "vehicle", "crew", "treasure", "clue", "food"},
                "weight": 0.9,
            },
            "enchantments": {
                "keywords": {"enchantment", "enchantments", "aura", "constellation", "enchanted"},
                "weight": 1.0,
            },
            "spells": {
                "keywords": {"instant", "sorcery", "prowess", "magecraft", "storm"},
                "weight": 1.0,
            },
            "combat": {
                "keywords": {"attacks", "attacking", "combat damage", "blocked", "fight", "fights"},
                "weight": 0.8,
            },
            "lifegain": {
                "keywords": {"gain life", "gains life", "lifelink"},
                "weight": 1.0,
            },
            "mill": {
                "keywords": {"mill", "milled", "mills"},
                "weight": 1.3,
            },
            "discard": {
                "keywords": {"discard", "discards", "discarded", "madness", "hellbent"},
                "weight": 1.0,
            },
            "draw": {
                "keywords": {"draw a card", "draw cards", "draws a card", "wheel"},
                "weight": 0.6,
            },
        }
    
    @staticmethod
    def _normalize_type(t: str) -> str:
        """Normalize creature type to singular lowercase form."""
        t = t.lower().strip()
        if t.endswith("ies"):
            return t[:-3] + "y"
        elif t.endswith("ves"):
            return t[:-3] + "f"
        elif t == "zombies":
            return "zombie"
        elif t.endswith("es") and len(t) > 4:
            return t[:-2]
        elif t.endswith("s") and len(t) > 3:
            return t[:-1]
        return t
    
    def calculate_synergy_score(self, deck_cards: List[Dict[str, Any]]) -> float:
        """
        Calculate overall deck synergy score (0-100).
        
        - 0-15: Low synergy (theme deck or unfocused)
        - 15-35: Average synergy (typical commander deck)
        - 35-60: Good synergy (focused strategy)
        - 60-100: High synergy (tribal or dedicated engine)
        """
        non_basics = [c for c in deck_cards if "Basic" not in c.get("type_line", "")]
        
        if len(non_basics) < 20:
            return 0.0
        
        tribal_score = self._get_tribal_density(non_basics)
        theme_score = self._get_theme_concentration(non_basics)
        
        primary_score = max(tribal_score, theme_score)
        secondary_score = min(tribal_score, theme_score)
        
        if secondary_score > 20:
            final_score = primary_score + (secondary_score * 0.15)
        else:
            final_score = primary_score
        
        return min(100.0, round(final_score, 2))
    
    def _get_tribal_density(self, cards: List[Dict[str, Any]]) -> float:
        """
        Calculate tribal synergy weighted by INTENT.
        
        - Oracle text mentions = strong signal (3 points per card)
        - Type line creatures = only count if oracle shows intent
        
        This distinguishes:
        - Incidental Humans (elder deck): 30 type line, 0 oracle -> low score
        - Intentional Humans (Kyler): 20 type line, 15 oracle -> high score
        """
        # Step 1: Count oracle text mentions (INTENT)
        oracle_mentions = Counter()
        
        for card in cards:
            oracle = card.get("oracle_text", "")
            if not oracle:
                continue
            oracle_lower = oracle.lower()
            
            card_types = set()
            for tribal_type in self.TRIBAL_TYPES:
                if tribal_type.lower() in oracle_lower:
                    card_types.add(self._normalize_type(tribal_type))
            
            for t in card_types:
                oracle_mentions[t] += 1
        
        # Step 2: Count type line creatures
        type_line_counts = Counter()
        creature_count = 0
        
        for card in cards:
            type_line = card.get("type_line", "")
            if "Creature" not in type_line:
                continue
            
            creature_count += 1
            
            for sep in ["—", "–", " - "]:
                if sep in type_line:
                    for subtype in type_line.split(sep)[1].strip().split():
                        type_line_counts[self._normalize_type(subtype)] += 1
                    break
        
        if creature_count < 5:
            return 0.0
        
        # Step 3: Calculate score per type
        best_score = 0.0
        all_types = set(oracle_mentions.keys()) | set(type_line_counts.keys())
        
        for creature_type in all_types:
            oracle_count = oracle_mentions.get(creature_type, 0)
            type_line_count = type_line_counts.get(creature_type, 0)
            
            # Oracle = 3 points per card (strong intent signal)
            oracle_score = oracle_count * 3
            
            # Type line only matters if oracle shows intent
            if oracle_count >= 5:
                # Strong intent: full type line credit
                type_line_score = (type_line_count / creature_count) * 50
            elif oracle_count >= 2:
                # Some intent: partial credit
                type_line_score = (type_line_count / creature_count) * 25
            else:
                # No intent: type line is incidental
                type_line_score = 0
            
            total = oracle_score + type_line_score
            best_score = max(best_score, total)
        
        return min(80.0, best_score)
    
    def _get_theme_concentration(self, cards: List[Dict[str, Any]]) -> float:
        """Calculate mechanical synergy from keyword concentration."""
        deck_size = len(cards)
        theme_hits = {theme: set() for theme in self.SYNERGY_THEMES}
        
        for i, card in enumerate(cards):
            oracle = card.get("oracle_text", "").lower()
            name = card.get("name", f"card_{i}")
            
            for theme_name, data in self.SYNERGY_THEMES.items():
                for kw in data["keywords"]:
                    if kw in oracle:
                        theme_hits[theme_name].add(name)
                        break
        
        scores = []
        for theme, cards_set in theme_hits.items():
            if cards_set:
                conc = len(cards_set) / deck_size
                weight = self.SYNERGY_THEMES[theme]["weight"]
                scores.append((theme, conc * 100 * weight, len(cards_set)))
        
        if not scores:
            return 0.0
        
        scores.sort(key=lambda x: x[1], reverse=True)
        primary = scores[0][1]
        
        if len(scores) > 1 and scores[1][1] > 15:
            primary += scores[1][1] * 0.2
        
        return min(80.0, primary)
    
    def get_detected_themes(self, cards: List[Dict[str, Any]]) -> List[Tuple[str, int, float]]:
        """Return detected themes as (name, card_count, percentage) tuples."""
        non_basics = [c for c in cards if "Basic" not in c.get("type_line", "")]
        if not non_basics:
            return []
        
        deck_size = len(non_basics)
        theme_hits = {t: set() for t in self.SYNERGY_THEMES}
        
        for i, card in enumerate(non_basics):
            oracle = card.get("oracle_text", "").lower()
            name = card.get("name", f"card_{i}")
            
            for theme, data in self.SYNERGY_THEMES.items():
                for kw in data["keywords"]:
                    if kw in oracle:
                        theme_hits[theme].add(name)
                        break
        
        results = [(t, len(s), len(s)/deck_size*100) for t, s in theme_hits.items() if len(s) >= 5]
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def get_tribal_breakdown(self, cards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get detailed tribal analysis for debugging."""
        non_basics = [c for c in cards if "Basic" not in c.get("type_line", "")]
        
        oracle_mentions = Counter()
        type_line_counts = Counter()
        creature_count = 0
        
        for card in non_basics:
            oracle = card.get("oracle_text", "")
            if oracle:
                for t in self.TRIBAL_TYPES:
                    if t.lower() in oracle.lower():
                        oracle_mentions[self._normalize_type(t)] += 1
            
            type_line = card.get("type_line", "")
            if "Creature" in type_line:
                creature_count += 1
                for sep in ["—", "–", " - "]:
                    if sep in type_line:
                        for sub in type_line.split(sep)[1].strip().split():
                            type_line_counts[self._normalize_type(sub)] += 1
                        break
        
        return {
            "creature_count": creature_count,
            "oracle_mentions": dict(oracle_mentions.most_common(10)),
            "type_line_counts": dict(type_line_counts.most_common(10)),
        }


if __name__ == "__main__":
    print("Synergy Analyzer Test")
    print("=" * 50)
    
    analyzer = SynergyAnalyzer()
    
    # Test: Elf tribal (intentional)
    elf_tribal = [
        {"name": f"Elf {i}", "type_line": "Creature — Elf Druid", 
         "oracle_text": "Whenever an Elf enters the battlefield, add G."}
        for i in range(20)
    ] + [
        {"name": f"Elf Lord {i}", "type_line": "Creature — Elf", 
         "oracle_text": "Other Elves you control get +1/+1."}
        for i in range(5)
    ] + [
        {"name": f"Spell {i}", "type_line": "Sorcery", "oracle_text": "Draw cards equal to Elves you control."}
        for i in range(5)
    ] + [
        {"name": f"Land {i}", "type_line": "Land", "oracle_text": ""}
        for i in range(30)
    ]
    
    score = analyzer.calculate_synergy_score(elf_tribal)
    breakdown = analyzer.get_tribal_breakdown(elf_tribal)
    print(f"\nElf Tribal (intentional):")
    print(f"  Score: {score}")
    print(f"  Oracle mentions: {breakdown['oracle_mentions']}")
    
    # Test: Incidental humans (like Brion elder deck)
    incidental_humans = [
        {"name": f"Human {i}", "type_line": "Creature — Human Wizard", 
         "oracle_text": "Draw a card."}  # No mention of "Human"
        for i in range(30)
    ] + [
        {"name": f"Land {i}", "type_line": "Land", "oracle_text": ""}
        for i in range(30)
    ]
    
    score = analyzer.calculate_synergy_score(incidental_humans)
    breakdown = analyzer.get_tribal_breakdown(incidental_humans)
    print(f"\nIncidental Humans (elder-style deck):")
    print(f"  Score: {score}")
    print(f"  Oracle mentions: {breakdown['oracle_mentions']}")
    print(f"  Type line: {breakdown['type_line_counts']}")
    
    print("\n✅ Tests complete!")