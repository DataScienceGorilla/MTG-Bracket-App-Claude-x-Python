"""
MTG Commander Bracket Analyzer - Theme/Restriction Detector
============================================================

Detects potential Bracket 1 theme restrictions from card metadata.
These are patterns that suggest intentional deck-building restrictions
rather than power-level optimization.

A high restriction score + low synergy score = likely Bracket 1

Detectable restrictions:
- Single artist (Rebecca Guay tribal)
- Set/block restricted (only Kamigawa cards)
- Rarity restricted (all commons/pauper style)
- Frame restricted (old border only)
- Alphabet deck (one card per letter)
- Color word restriction (all cards mention "fire" in name)
- Mana value restriction (all 3-drops)
"""

from collections import Counter
from typing import List, Dict, Any, Tuple, Optional
import re


class ThemeDetector:
    """
    Analyzes deck metadata to detect intentional theme restrictions.
    
    These restrictions are the hallmark of Bracket 1 decks - players
    choosing cards based on art, flavor, or arbitrary rules rather
    than power level.
    """
    
    # Thresholds for detection (as percentages of non-land cards)
    # These are intentionally high - we want to catch OBVIOUS restrictions
    THRESHOLDS = {
        "artist_concentration": 0.40,      # 40%+ cards by one artist is unusual
        "set_concentration": 0.60,         # 60%+ from one set (non-precon)
        "block_concentration": 0.70,       # 70%+ from one block
        "rarity_concentration": 0.80,      # 80%+ same rarity is intentional
        "cmc_concentration": 1.0,         # 100%+ same CMC is a restriction
        "alphabet_coverage": 1.0,         # 100% of alphabet = alphabet deck
        "frame_concentration": 0.85,       # 85%+ same frame (old border tribal)
    }
    
    # Sets that are precons (high concentration is normal, not a theme)
    PRECON_SETS = {
        "plc", "pca", "c13", "c14", "c15", "c16", "c17", "c18", "c19", "c20", "c21",
        "khc", "afc", "mic", "voc", "nec", "ncc", "brc", "orc", "onc", "moc", "woc",
        "lcc", "pip", "dsc", "fdc", "mh3c", "acr"  # commander precons
    }
    
    # Known blocks for block detection
    BLOCKS = {
        "ravnica": ["rav", "gpt", "dis", "rtr", "gtc", "dgm", "grn", "rna", "war"],
        "innistrad": ["isd", "dka", "avr", "soi", "emn", "mid", "vow"],
        "zendikar": ["zen", "wwk", "roe", "bfz", "ogw", "znr"],
        "mirrodin": ["mrd", "dst", "5dn", "som", "mbs", "nph", "one", "mom"],
        "kamigawa": ["chk", "bok", "sok", "neo"],
        "theros": ["ths", "bng", "jou", "thb"],
        "dominaria": ["dom", "dmu", "bro"],
        "ixalan": ["xln", "rix", "lci"],
        "eldraine": ["eld", "woe"],
        "tarkir": ["ktk", "frf", "dtk"],
        "amonkhet": ["akh", "hou"],
        "kaladesh": ["kld", "aer"],
        "lorwyn": ["lrw", "mor", "shm", "eve"],
        "alara": ["ala", "con", "arb"],
        "time_spiral": ["tsp", "plc", "fut"],
        "ice_age": ["ice", "all", "csp"],
    }
    
    def __init__(self):
        # Build reverse lookup: set code -> block name
        self.set_to_block = {}
        for block_name, sets in self.BLOCKS.items():
            for set_code in sets:
                self.set_to_block[set_code] = block_name
    
    def detect_themes(self, cards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze cards for theme restriction patterns.
        
        Args:
            cards: List of card data dictionaries from Scryfall
            
        Returns:
            {
                "detected_themes": ["single_artist", "set_restricted", ...],
                "theme_details": {
                    "artist": {"name": "Rebecca Guay", "count": 45, "pct": 0.85},
                    ...
                },
                "restriction_score": 0-100,  # How likely theme-restricted
                "restriction_description": "Possible Rebecca Guay artist theme"
            }
        """
        result = {
            "detected_themes": [],
            "theme_details": {},
            "restriction_score": 0,
            "restriction_description": None
        }
        
        # Filter to non-basic-land cards for analysis
        # (Basic lands don't indicate theme choice)
        non_basics = [
            c for c in cards
            if "Basic" not in c.get("type_line", "")
        ]
        
        if len(non_basics) < 20:
            # Too few cards to analyze meaningfully
            return result
        
        # Run all detection methods
        detections = []
        
        artist_result = self._check_artist_concentration(non_basics)
        if artist_result:
            detections.append(("single_artist", artist_result, 35))
            result["theme_details"]["artist"] = artist_result
        
        set_result = self._check_set_concentration(non_basics)
        if set_result:
            detections.append(("set_restricted", set_result, 30))
            result["theme_details"]["set"] = set_result
        
        block_result = self._check_block_concentration(non_basics)
        if block_result:
            detections.append(("block_restricted", block_result, 25))
            result["theme_details"]["block"] = block_result
        
        rarity_result = self._check_rarity_concentration(non_basics)
        if rarity_result:
            detections.append(("rarity_restricted", rarity_result, 20))
            result["theme_details"]["rarity"] = rarity_result
        
        alphabet_result = self._check_alphabet_pattern(non_basics)
        if alphabet_result:
            detections.append(("alphabet_deck", alphabet_result, 15))
            result["theme_details"]["alphabet"] = alphabet_result
        
        cmc_result = self._check_cmc_concentration(non_basics)
        if cmc_result:
            detections.append(("cmc_restricted", cmc_result, 50))
            result["theme_details"]["cmc"] = cmc_result
        
        frame_result = self._check_frame_concentration(non_basics)
        if frame_result:
            detections.append(("frame_restricted", frame_result, 25))
            result["theme_details"]["frame"] = frame_result
        
        word_result = self._check_name_word_pattern(non_basics)
        if word_result:
            detections.append(("name_theme", word_result, 40))
            result["theme_details"]["name_word"] = word_result
        
        # Calculate overall restriction score
        # Each detection adds points, scaled by confidence
        total_score = 0
        descriptions = []
        
        for theme_name, details, base_points in detections:
            result["detected_themes"].append(theme_name)
            
            # Scale points by concentration (higher = more confident)
            concentration = details.get("pct", details.get("coverage", 0.5))
            scaled_points = base_points * (0.5 + concentration * 0.5)
            total_score += scaled_points
            
            # Build description
            if theme_name == "single_artist":
                descriptions.append(f"{details['name']} artist theme ({details['pct']:.0%})")
            elif theme_name == "set_restricted":
                descriptions.append(f"{details['name']} set theme ({details['pct']:.0%})")
            elif theme_name == "block_restricted":
                descriptions.append(f"{details['name'].replace('_', ' ').title()} block theme ({details['pct']:.0%})")
            elif theme_name == "rarity_restricted":
                descriptions.append(f"{details['name'].title()} rarity restriction ({details['pct']:.0%})")
            elif theme_name == "alphabet_deck":
                descriptions.append(f"Alphabet deck ({details['coverage']:.0%} coverage)")
            elif theme_name == "cmc_restricted":
                descriptions.append(f"CMC {details['name']} tribal ({details['pct']:.0%})")
            elif theme_name == "frame_restricted":
                descriptions.append(f"{details['name'].replace('_', ' ').title()} frame theme ({details['pct']:.0%})")
            elif theme_name == "name_theme":
                descriptions.append(f"'{details['word']}' name theme ({details['count']} cards)")
        
        result["restriction_score"] = min(100, total_score)
        
        if descriptions:
            result["restriction_description"] = "; ".join(descriptions)
        
        return result
    
    def _check_artist_concentration(self, cards: List[Dict]) -> Optional[Dict]:
        """Check if deck has unusual artist concentration."""
        artists = []
        for card in cards:
            artist = card.get("artist", "")
            if artist:
                artists.append(artist)
        
        if not artists:
            return None
        
        counts = Counter(artists)
        top_artist, top_count = counts.most_common(1)[0]
        pct = top_count / len(artists)
        
        if pct >= self.THRESHOLDS["artist_concentration"]:
            return {
                "name": top_artist,
                "count": top_count,
                "pct": pct,
                "total_artists": len(counts)
            }
        return None
    
    def _check_set_concentration(self, cards: List[Dict]) -> Optional[Dict]:
        """Check if deck is restricted to a single set."""
        sets = []
        for card in cards:
            set_code = card.get("set", "").lower()
            if set_code and set_code not in self.PRECON_SETS:
                sets.append(set_code)
        
        if not sets:
            return None
        
        counts = Counter(sets)
        top_set, top_count = counts.most_common(1)[0]
        pct = top_count / len(sets)
        
        if pct >= self.THRESHOLDS["set_concentration"]:
            # Get set name if available
            set_name = top_set.upper()  # Default to code
            # Could enhance with Scryfall set lookup
            return {
                "code": top_set,
                "name": set_name,
                "count": top_count,
                "pct": pct
            }
        return None
    
    def _check_block_concentration(self, cards: List[Dict]) -> Optional[Dict]:
        """Check if deck is restricted to a block."""
        blocks = []
        for card in cards:
            set_code = card.get("set", "").lower()
            block = self.set_to_block.get(set_code)
            if block:
                blocks.append(block)
        
        if len(blocks) < len(cards) * 0.5:
            # Less than half the cards are from known blocks
            return None
        
        counts = Counter(blocks)
        top_block, top_count = counts.most_common(1)[0]
        pct = top_count / len(blocks)
        
        if pct >= self.THRESHOLDS["block_concentration"]:
            return {
                "name": top_block,
                "count": top_count,
                "pct": pct
            }
        return None
    
    def _check_rarity_concentration(self, cards: List[Dict]) -> Optional[Dict]:
        """Check for rarity restriction (pauper-style, all rares, etc.)."""
        rarities = []
        for card in cards:
            rarity = card.get("rarity", "").lower()
            if rarity:
                rarities.append(rarity)
        
        if not rarities:
            return None
        
        counts = Counter(rarities)
        top_rarity, top_count = counts.most_common(1)[0]
        pct = top_count / len(rarities)
        
        # Only flag commons and uncommons as restrictions
        # (all rares/mythics is just expensive, not thematic)
        if pct >= self.THRESHOLDS["rarity_concentration"] and top_rarity in ["common", "uncommon"]:
            return {
                "name": top_rarity,
                "count": top_count,
                "pct": pct
            }
        return None
    
    def _check_alphabet_pattern(self, cards: List[Dict]) -> Optional[Dict]:
        """Check for alphabet deck pattern (one card per letter)."""
        first_letters = set()
        letter_counts = Counter()
        
        for card in cards:
            name = card.get("name", "")
            if name:
                first_char = name[0].upper()
                if first_char.isalpha():
                    first_letters.add(first_char)
                    letter_counts[first_char] += 1
        
        # Alphabet deck criteria:
        # 1. High letter coverage (20+ letters)
        # 2. Even distribution (no letter has way more than others)
        coverage = len(first_letters) / 26
        
        if coverage >= self.THRESHOLDS["alphabet_coverage"]:
            # Check for even distribution
            counts = list(letter_counts.values())
            avg = sum(counts) / len(counts)
            max_count = max(counts)
            
            # If max is less than 3x average, it's evenly distributed
            if max_count <= avg * 3:
                return {
                    "coverage": coverage,
                    "letters_used": len(first_letters),
                    "distribution": "even"
                }
        return None
    
    def _check_cmc_concentration(self, cards: List[Dict]) -> Optional[Dict]:
        """Check for CMC restriction (all 3-drops, etc.)."""
        cmcs = []
        for card in cards:
            cmc = card.get("cmc", 0)
            # Exclude lands (CMC 0)
            if "Land" not in card.get("type_line", ""):
                cmcs.append(int(cmc))
        
        if not cmcs:
            return None
        
        counts = Counter(cmcs)
        top_cmc, top_count = counts.most_common(1)[0]
        pct = top_count / len(cmcs)
        
        if pct >= self.THRESHOLDS["cmc_concentration"]:
            return {
                "name": str(top_cmc),
                "count": top_count,
                "pct": pct
            }
        return None
    
    def _check_frame_concentration(self, cards: List[Dict]) -> Optional[Dict]:
        """Check for frame restriction (old border, etc.)."""
        frames = []
        for card in cards:
            frame = card.get("frame", "")
            if frame:
                frames.append(frame)
        
        if not frames:
            return None
        
        counts = Counter(frames)
        top_frame, top_count = counts.most_common(1)[0]
        pct = top_count / len(frames)
        
        # Old border (1993, 1997) is the main thematic choice
        if pct >= self.THRESHOLDS["frame_concentration"] and top_frame in ["1993", "1997"]:
            return {
                "name": "old_border",
                "frame_code": top_frame,
                "count": top_count,
                "pct": pct
            }
        return None
    
    def _check_name_word_pattern(self, cards: List[Dict]) -> Optional[Dict]:
        """
        Check for name-based themes (cards with 'fire' in name, etc.)
        
        Only flags if an unusual word appears in 10+ card names.
        """
        # Common words to ignore
        ignore_words = {
            "the", "of", "and", "to", "a", "in", "for", "is", "on", "that",
            "it", "with", "as", "was", "at", "be", "this", "from", "or", "an"
        }
        
        word_counts = Counter()
        
        for card in cards:
            name = card.get("name", "").lower()
            # Split on non-alpha and filter
            words = re.findall(r'[a-z]{3,}', name)
            for word in words:
                if word not in ignore_words:
                    word_counts[word] += 1
        
        if not word_counts:
            return None
        
        top_word, top_count = word_counts.most_common(1)[0]
        
        # Need at least 10 cards with same word to be a theme
        if top_count >= 10:
            return {
                "word": top_word,
                "count": top_count,
                "pct": top_count / len(cards)
            }
        return None
    
    def calculate_adjusted_synergy(
        self,
        base_synergy_score: float,
        restriction_score: float
    ) -> Tuple[float, str]:
        """
        Adjust synergy score based on detected restrictions.
        
        Bracket 1 decks often have LOW synergy (card pool is restricted)
        but HIGH restriction score (intentional theme).
        
        Args:
            base_synergy_score: Original synergy score (0-100)
            restriction_score: Theme restriction score (0-100)
            
        Returns:
            Tuple of (adjusted_score, explanation)
        """
        # If high restriction detected, low synergy is EXPECTED
        # and shouldn't count against the deck
        
        if restriction_score >= 50:
            # Strong theme detected - synergy doesn't matter as much
            # Bracket 1 candidate
            explanation = "Theme restriction detected - low synergy expected"
            adjusted = base_synergy_score  # Keep as-is, flag separately
        elif restriction_score >= 25:
            # Moderate theme signals
            explanation = "Possible theme restriction"
            adjusted = base_synergy_score
        else:
            # No theme detected - synergy score stands
            explanation = "No theme restriction detected"
            adjusted = base_synergy_score
        
        return adjusted, explanation
    
    def get_bracket1_likelihood(
        self,
        synergy_score: float,
        restriction_score: float,
        game_changers_count: int,
        fast_mana_count: int,
        tutor_count: int,
        has_mass_land_denial: bool = False
    ) -> Tuple[float, str]:
        """
        Calculate likelihood that this is a Bracket 1 deck.
        
        Bracket 1 (Exhibition) requirements per official rules:
        - Theme/restriction intent is PRIMARY
        - Mass Land Denial is the ONLY hard disqualifier
        - Game Changers, Extra Turns, and 2-Card Combos are allowed
          IF they fit the theme ("exceptions for highly thematic cards")
        
        Args:
            synergy_score: How synergistic the cards are (0-100)
            restriction_score: How theme-restricted the deck appears (0-100)
            game_changers_count: Number of Game Changers in deck
            fast_mana_count: Number of fast mana pieces
            tutor_count: Number of tutors
            has_mass_land_denial: Whether deck has MLD (hard disqualifier)
            
        Returns:
            Tuple of (likelihood 0-100, explanation)
        """
        # Hard disqualifier: Mass Land Denial has NO exceptions
        if has_mass_land_denial:
            return 0, "Has Mass Land Denial - cannot be Bracket 1 (no thematic exceptions)"
        
        likelihood = 0
        reasons = []
        
        # Theme restriction is the PRIMARY signal for Bracket 1
        # "decks to prioritize a goal, theme, or idea over power"
        if restriction_score >= 50:
            likelihood += 60
            reasons.append("Strong theme restriction detected")
        elif restriction_score >= 0:
            likelihood += 40
            reasons.append("Possible theme restriction")
        # Low synergy supports Bracket 1 likelihood
        if restriction_score >= 0 and synergy_score < 40:
            likelihood += 10
            reasons.append("Low synergy suggests restricted card pool")
        # Low synergy + theme = more likely Bracket 1
        # (Card pool restriction limits synergy options)
        if restriction_score >= 15 and synergy_score < 40:
            likelihood += 20
            reasons.append("Low synergy with any restriction suggests Bracket 1 intent")
        
        # Game Changers don't disqualify, but many of them without
        # strong theme signals suggest it's NOT a theme deck
        if game_changers_count > 0 and restriction_score < 25:
            # Has power cards but no theme - probably NOT Bracket 1
            penalty = min(30, game_changers_count * 10)
            likelihood -= penalty
            reasons.append(f"Has {game_changers_count} Game Changer(s) without clear theme")
        elif game_changers_count > 0 and restriction_score >= 50:
            # Has power cards WITH theme - could be thematic exceptions
            reasons.append(f"Has {game_changers_count} Game Changer(s) (may be thematic)")
        
        # Absence of competitive elements is suggestive but not required
        if fast_mana_count == 0:
            likelihood += 5
            reasons.append("No fast mana")
        
        if tutor_count == 0:
            likelihood += 5
            reasons.append("No tutors")
        
        # Cap at 100, floor at 0
        likelihood = max(0, min(100, likelihood))
        
        if not reasons:
            explanation = "No Bracket 1 signals detected"
        else:
            explanation = "; ".join(reasons)
        
        return likelihood, explanation


# =============================================================================
# Test the module
# =============================================================================
if __name__ == "__main__":
    print("Theme Detector Test")
    print("=" * 60)
    
    # Create mock cards to test detection
    mock_cards = [
        {"name": "Abundance", "artist": "Rebecca Guay", "set": "c17", "rarity": "rare", "cmc": 4, "frame": "2015", "type_line": "Enchantment"},
        {"name": "Bitterblossom", "artist": "Rebecca Guay", "set": "mm2", "rarity": "mythic", "cmc": 2, "frame": "2015", "type_line": "Enchantment"},
        {"name": "Careful Study", "artist": "Rebecca Guay", "set": "ody", "rarity": "common", "cmc": 1, "frame": "1997", "type_line": "Sorcery"},
        {"name": "Dark Ritual", "artist": "Rebecca Guay", "set": "tmp", "rarity": "common", "cmc": 1, "frame": "1997", "type_line": "Instant"},
    ] * 15  # Repeat to simulate full deck
    
    detector = ThemeDetector()
    result = detector.detect_themes(mock_cards)
    
    print(f"Detected themes: {result['detected_themes']}")
    print(f"Restriction score: {result['restriction_score']}")
    print(f"Description: {result['restriction_description']}")
    print(f"\nDetails: {result['theme_details']}")