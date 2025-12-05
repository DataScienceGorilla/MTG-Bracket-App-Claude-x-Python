import re
from collections import Counter
from typing import List, Dict, Any

class SynergyAnalyzer:
    def __init__(self):
        # Words that appear on almost every card but don't indicate synergy
        self.MTG_STOPWORDS = {
            "the", "a", "an", "of", "to", "in", "for", "with", "on", "at", 
            "target", "creature", "player", "battlefield", "turn", "end", 
            "beginning", "control", "library", "hand", "graveyard", "card",
            "cards", "mana", "life", "tap", "untap", "add", "cost", "cast",
            "search", "shuffle", "reveal", "game", "face", "up", "down",
            "any", "all", "your", "their", "opponent", "token", "create",
            "sorcery", "instant", "enchantment", "artifact", "planeswalker",
            "land", "this", "that", "it", "is", "be", "as"
        }

    def calculate_synergy_score(self, deck_cards: List[Dict[str, Any]]) -> float:
        """
        Returns a score from 0 to 100.
        < 15: Low Synergy (Likely Theme/Art deck or Pile of Cards -> Bracket 1)
        15-30: Average Synergy (Standard Commander Deck)
        > 30: High Synergy (Tribal or Dedicated Engine)
        """
        
        # Filter out Basic Lands (they skew the data)
        non_basics = [
            c for c in deck_cards 
            if "Basic" not in c.get("type_line", "")
        ]
        
        if not non_basics:
            return 0.0

        deck_size = len(non_basics)

        # 1. Calculate Tribal Score
        # What % of creatures share the most common subtype?
        tribal_score = self._get_tribal_density(non_basics)
        
        # 2. Calculate Mechanical Score
        # What % of cards share the top 3 most common relevant words?
        mechanic_score = self._get_text_density(non_basics)
        
        # Weighted Score: Mechanics usually matter more than tribe unless it's strictly tribal
        # We take the higher of the two primarily, but blend them.
        final_score = max(tribal_score, mechanic_score)
        
        return round(final_score, 2)

    def _get_tribal_density(self, cards: List[Dict[str, Any]]) -> float:
        subtypes = []
        creature_count = 0
        
        for card in cards:
            type_line = card.get("type_line", "")
            if "Creature" in type_line:
                creature_count += 1
                # formatting: "Legendary Creature — Elf Warrior" -> ["Elf", "Warrior"]
                if "—" in type_line:
                    parts = type_line.split("—")[1].strip().split(" ")
                    subtypes.extend(parts)
        
        if creature_count < 10: 
            return 0.0 # Not enough creatures to care about tribal synergy
            
        # Find most common subtype
        counts = Counter(subtypes)
        if not counts: 
            return 0.0
            
        most_common_type, count = counts.most_common(1)[0]
        
        # Score = Percentage of creatures that are this type
        # e.g., 20 Elves in a deck of 30 creatures = 66.6 score
        density = (count / creature_count) * 100
        
        # Penalize generic types slightly if needed, but usually fine
        return density

    def _get_text_density(self, cards: List[Dict[str, Any]]) -> float:
        all_words = []
        
        for card in cards:
            text = card.get("oracle_text", "").lower()
            if not text: continue
            
            # Remove punctuation and split
            words = re.findall(r'\b[a-z]{3,}\b', text)
            
            # Filter stopwords
            relevant_words = [w for w in words if w not in self.MTG_STOPWORDS]
            all_words.extend(relevant_words)
            
        if not all_words: 
            return 0.0
            
        # Look at the top 3 most frequent mechanical words
        # e.g. "sacrifice", "counter", "exile"
        word_counts = Counter(all_words)
        top_3 = word_counts.most_common(3)
        
        if not top_3:
            return 0.0
            
        # Calculate how "dense" these mechanics are across the deck
        # We sum the top 3 counts and divide by deck size
        total_hits = sum(count for word, count in top_3)
        
        # Score calculation:
        # If the top 3 words appear 50 times in a 60 card (non-land) list, 
        # that's a density of ~0.8 -> Scaled to 80 score.
        score = (total_hits / len(cards)) * 100
        
        return score