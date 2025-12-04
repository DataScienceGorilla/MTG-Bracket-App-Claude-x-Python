"""
MTG Commander Bracket Analyzer - Deck Analysis Engine
=====================================================

This module analyzes a Commander deck and calculates various metrics
that determine which bracket the deck belongs to.

It checks for:
- Game Changers cards
- Infinite combo potential
- Mass land denial
- Extra turn effects
- Tutor density
- Overall strategy/archetype
"""

from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass
from config import (
    GAME_CHANGERS, MASS_LAND_DENIAL, EXTRA_TURN_CARDS,
    ARCHETYPE_KEYWORDS, BRACKET_DEFINITIONS
)
from scryfall_client import ScryfallClient, parse_decklist


@dataclass
class DeckAnalysis:
    """
    Container for all the analysis results of a deck.
    
    This dataclass holds everything we learn about a deck,
    making it easy to pass around and display.
    """
    # Basic deck info
    commander: str
    total_cards: int
    
    # Bracket-relevant counts
    game_changers_found: List[str]  # List of Game Changer cards in the deck
    game_changers_count: int
    
    # Strategy detection
    mass_land_denial_cards: List[str]
    extra_turn_cards: List[str]
    tutor_cards: List[str]
    
    # Card categorization
    creatures: List[Dict[str, Any]]
    artifacts: List[Dict[str, Any]]
    enchantments: List[Dict[str, Any]]
    instants: List[Dict[str, Any]]
    sorceries: List[Dict[str, Any]]
    lands: List[Dict[str, Any]]
    planeswalkers: List[Dict[str, Any]]
    
    # Detected archetypes and themes
    detected_archetypes: List[str]
    color_identity: List[str]
    
    # Mana curve statistics
    mana_curve: Dict[int, int]  # CMC -> count
    average_cmc: float
    
    # Calculated bracket
    suggested_bracket: int
    bracket_reasoning: List[str]
    
    # All card data (for LLM analysis)
    all_cards: List[Dict[str, Any]]


class DeckAnalyzer:
    """
    Analyzes Commander decks for bracket classification.
    
    This is the main analysis engine. It takes a decklist,
    fetches card data from Scryfall, and computes all the
    metrics needed to determine the deck's bracket.
    """
    
    def __init__(self, scryfall_client: ScryfallClient = None):
        """
        Initialize the analyzer with an optional Scryfall client.
        
        Args:
            scryfall_client: Pre-configured Scryfall client. If None,
                           a new one will be created.
        """
        self.scryfall = scryfall_client or ScryfallClient()
        
        # Cache the official Game Changers list from Scryfall
        # This ensures we're using the most up-to-date list
        self._game_changers_cache = None
    
    @property
    def game_changers_set(self) -> Set[str]:
        """
        Get the current Game Changers list (cached).
        
        We normalize to lowercase for easier matching.
        """
        if self._game_changers_cache is None:
            # First, try to get from Scryfall (most up-to-date)
            try:
                official_list = self.scryfall.get_game_changers_list()
                self._game_changers_cache = {name.lower() for name in official_list}
            except Exception:
                # Fall back to our config file list
                print("  ⚠️  Couldn't fetch official Game Changers, using local list")
                self._game_changers_cache = {name.lower() for name in GAME_CHANGERS}
        
        return self._game_changers_cache
    
    def analyze_deck(self, decklist_text: str, commander_name: str = None) -> DeckAnalysis:
        """
        Perform a complete analysis of a Commander deck.
        
        Args:
            decklist_text: Raw decklist text (one card per line)
            commander_name: Optional explicit commander name. If None,
                          will try to detect from decklist.
        
        Returns:
            DeckAnalysis object with all computed metrics
        """
        print("\n🔮 Starting deck analysis...")
        
        # Step 1: Parse the decklist
        print("  📝 Parsing decklist...")
        parsed_cards = parse_decklist(decklist_text)
        
        # Step 2: Fetch card data from Scryfall
        print("  🌐 Fetching card data from Scryfall...")
        card_names = [card["name"] for card in parsed_cards]
        card_data_map = self.scryfall.get_cards_bulk(card_names)
        
        # Step 3: Match parsed cards with fetched data
        all_cards = []
        for parsed_card in parsed_cards:
            name = parsed_card["name"]
            quantity = parsed_card["quantity"]
            
            # Look up the card (case-insensitive)
            card_info = card_data_map.get(name.lower())
            
            if card_info:
                # Add quantity info to the card data
                card_info["_quantity"] = quantity
                all_cards.append(card_info)
        
        print(f"  ✅ Found data for {len(all_cards)}/{len(parsed_cards)} cards")
        
        # Step 4: Detect commander (if not provided)
        commander = commander_name
        if not commander and all_cards:
            # Look for legendary creatures that are commonly commanders
            commander = self._detect_commander(all_cards)
        
        # Step 5: Categorize cards by type
        categorized = self._categorize_cards(all_cards)
        
        # Step 6: Find Game Changers
        game_changers = self._find_game_changers(all_cards)
        
        # Step 7: Find problematic cards
        mass_ld = self._find_cards_by_name(all_cards, MASS_LAND_DENIAL)
        extra_turns = self._find_cards_by_name(all_cards, EXTRA_TURN_CARDS)
        tutors = self._find_tutors(all_cards)
        
        # Step 8: Detect archetypes
        archetypes = self._detect_archetypes(all_cards)
        
        # Step 9: Calculate mana curve
        mana_curve, avg_cmc = self._calculate_mana_curve(all_cards)
        
        # Step 10: Determine color identity
        color_identity = self._get_color_identity(all_cards)
        
        # Step 11: Calculate suggested bracket
        bracket, reasoning = self._calculate_bracket(
            game_changers_count=len(game_changers),
            has_mass_ld=len(mass_ld) > 0,
            extra_turn_count=len(extra_turns),
            tutor_count=len(tutors),
            archetypes=archetypes
        )
        
        print(f"  🎯 Analysis complete! Suggested bracket: {bracket}")
        
        return DeckAnalysis(
            commander=commander or "Unknown",
            total_cards=len(all_cards),
            game_changers_found=game_changers,
            game_changers_count=len(game_changers),
            mass_land_denial_cards=mass_ld,
            extra_turn_cards=extra_turns,
            tutor_cards=tutors,
            creatures=categorized["creatures"],
            artifacts=categorized["artifacts"],
            enchantments=categorized["enchantments"],
            instants=categorized["instants"],
            sorceries=categorized["sorceries"],
            lands=categorized["lands"],
            planeswalkers=categorized["planeswalkers"],
            detected_archetypes=archetypes,
            color_identity=color_identity,
            mana_curve=mana_curve,
            average_cmc=avg_cmc,
            suggested_bracket=bracket,
            bracket_reasoning=reasoning,
            all_cards=all_cards
        )
    
    def _detect_commander(self, cards: List[Dict[str, Any]]) -> str:
        """
        Try to automatically detect the commander from the deck.
        
        Commanders are typically legendary creatures (or other legendary
        permanents with special rules text).
        """
        for card in cards:
            type_line = card.get("type_line", "").lower()
            
            # Check if it's legendary and a creature
            if "legendary" in type_line and "creature" in type_line:
                return card.get("name", "Unknown")
            
            # Some commanders have special text like "can be your commander"
            oracle_text = card.get("oracle_text", "").lower()
            if "can be your commander" in oracle_text:
                return card.get("name", "Unknown")
        
        return None
    
    def _categorize_cards(self, cards: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Sort cards into categories by their primary type.
        
        This helps with deck composition analysis.
        """
        categories = {
            "creatures": [],
            "artifacts": [],
            "enchantments": [],
            "instants": [],
            "sorceries": [],
            "lands": [],
            "planeswalkers": [],
            "other": []
        }
        
        for card in cards:
            type_line = card.get("type_line", "").lower()
            
            # Check each type (order matters for multi-type cards)
            if "creature" in type_line:
                categories["creatures"].append(card)
            elif "instant" in type_line:
                categories["instants"].append(card)
            elif "sorcery" in type_line:
                categories["sorceries"].append(card)
            elif "artifact" in type_line:
                categories["artifacts"].append(card)
            elif "enchantment" in type_line:
                categories["enchantments"].append(card)
            elif "land" in type_line:
                categories["lands"].append(card)
            elif "planeswalker" in type_line:
                categories["planeswalkers"].append(card)
            else:
                categories["other"].append(card)
        
        return categories
    
    def _find_game_changers(self, cards: List[Dict[str, Any]]) -> List[str]:
        """
        Find all Game Changers in the deck.
        
        Returns the names of Game Changer cards found.
        """
        found = []
        
        for card in cards:
            name = card.get("name", "").lower()
            
            if name in self.game_changers_set:
                found.append(card.get("name"))
        
        return found
    
    def _find_cards_by_name(self, cards: List[Dict[str, Any]], target_list: List[str]) -> List[str]:
        """
        Find cards whose names match a target list.
        
        Used for finding mass land denial, extra turns, etc.
        """
        # Normalize the target list to lowercase for matching
        target_set = {name.lower() for name in target_list}
        
        found = []
        for card in cards:
            name = card.get("name", "").lower()
            if name in target_set:
                found.append(card.get("name"))
        
        return found
    
    def _find_tutors(self, cards: List[Dict[str, Any]]) -> List[str]:
        """
        Find cards that function as tutors (search your library).
        
        We look for cards with "search your library" in their text,
        excluding basic land tutors like Rampant Growth.
        """
        tutors = []
        
        # Words that indicate it's just a land ramp spell, not a real tutor
        
        ramp_phrases_to_ignore = [
        # Targets (Singular & Plural)
        "basic land cards",
        "basic land card",
        "card with a basic land type",
        "forest card", "island card", "swamp card", "mountain card", "plains card",
        "forest cards", "island cards", "swamp cards", "mountain cards", "plains cards",
        
        # Procedural Noise (The key fix for Cultivate/Ash Barrens)
        "reveal those cards",
        "reveal that card",
        "discard this card",
        "discard a card",
        "exile a card",
        "shuffle your library", # Sometimes "library" triggers false positives in other logic
        "put that card onto the battlefield",
        "card from your hand",
        "card from your library",
        
        # --- State Changes / Self-Reference (Fixes Glacier Godmaw) ---
        "When this creature",
        "sacrifice this creature",  # <--- Fixes Sakura-Tribe Elder (removes "creature" from cost)
        "creatures you control",    # <--- Fixes Glacier Godmaw (removes "creatures" from landfall)         # Removes "becomes a... artifact creature"
        "it's an artifact",    # Removes "It's an artifact in addition..."
        "is an artifact",
        "it's a creature",
        "is a creature",
        "living artifact"      # Specific to Godmaw's flavor text
    ]

    # 2. CRITICAL STEP: SORT BY LENGTH
    # We must remove "basic land cards" (len 16) BEFORE "basic land card" (len 15).
    # If we don't, "basic land cards" becomes "s" (because the first part was removed), leaving debris.
        ramp_phrases_to_ignore.sort(key=len, reverse=True)
        
        for card in cards:
            oracle_text = card.get("oracle_text", "").lower()
            
            # Check if it searches the library
            if "search your library" in oracle_text:
                # Check if it's NOT just a basic land tutor
                cleanoracle = oracle_text
                for phrase in ramp_phrases_to_ignore:
                    cleanoracle = cleanoracle.replace(phrase, "")
                
                # Also check if it can find other things
                can_find_nonland = (
                    "creature" in cleanoracle or
                    "artifact" in cleanoracle or
                    "enchantment" in cleanoracle or
                    "instant" in cleanoracle or
                    "sorcery" in cleanoracle or
                    "planeswalker" in cleanoracle or
                    "card" in cleanoracle  # Generic "card" often means any card
                )
                
                if can_find_nonland:
                    tutors.append(card.get("name"))
        
        return tutors
    
    def _detect_archetypes(self, cards: List[Dict[str, Any]]) -> List[str]:
        """
        Detect what archetypes/strategies the deck is built around.
        
        This uses keyword matching on oracle text to identify
        common Commander archetypes.
        """
        # Count how many cards match each archetype's keywords
        archetype_scores = {archetype: 0 for archetype in ARCHETYPE_KEYWORDS}
        
        for card in cards:
            oracle_text = card.get("oracle_text", "").lower()
            keywords = card.get("keywords", [])
            
            # Combine oracle text and keywords for searching
            searchable = oracle_text + " " + " ".join(kw.lower() for kw in keywords)
            
            for archetype, indicators in ARCHETYPE_KEYWORDS.items():
                for indicator in indicators:
                    if indicator.lower() in searchable:
                        archetype_scores[archetype] += 1
                        break  # Don't double-count same card
        
        # Return archetypes with significant presence (at least 5 cards)
        threshold = 5
        detected = [
            archetype for archetype, score in archetype_scores.items()
            if score >= threshold
        ]
        
        # Sort by score (most prominent first)
        detected.sort(key=lambda a: archetype_scores[a], reverse=True)
        
        return detected
    
    def _calculate_mana_curve(self, cards: List[Dict[str, Any]]) -> Tuple[Dict[int, int], float]:
        """
        Calculate the mana value distribution of the deck.
        
        Returns:
            Tuple of (curve_dict, average_cmc)
            curve_dict maps mana value to count of cards
        """
        curve = {}
        total_cmc = 0
        nonland_count = 0
        
        for card in cards:
            type_line = card.get("type_line", "").lower()
            
            # Skip lands for mana curve calculation
            if "land" in type_line:
                continue
            
            cmc = int(card.get("cmc", 0))
            quantity = card.get("_quantity", 1)
            
            # Group 7+ together as "7+"
            display_cmc = min(cmc, 7)
            curve[display_cmc] = curve.get(display_cmc, 0) + quantity
            
            total_cmc += cmc * quantity
            nonland_count += quantity
        
        # Calculate average
        average = total_cmc / nonland_count if nonland_count > 0 else 0
        
        return curve, round(average, 2)
    
    def _get_color_identity(self, cards: List[Dict[str, Any]]) -> List[str]:
        """
        Determine the deck's color identity.
        
        In Commander, color identity is the union of all colors
        used by all cards (including mana symbols in text).
        """
        all_colors = set()
        
        for card in cards:
            colors = card.get("color_identity", [])
            all_colors.update(colors)
        
        # Return in WUBRG order
        order = ["W", "U", "B", "R", "G"]
        return [c for c in order if c in all_colors]
    
    def _calculate_bracket(
        self,
        game_changers_count: int,
        has_mass_ld: bool,
        extra_turn_count: int,
        tutor_count: int,
        archetypes: List[str]
    ) -> Tuple[int, List[str]]:
        """
        Calculate the suggested bracket based on deck characteristics.
        
        This is the core bracket determination logic.
        
        Returns:
            Tuple of (bracket_number, list_of_reasons)
        """
        reasons = []
        bracket = 2  # Start at Core (default precon level)
        
        # Check Game Changers
        if game_changers_count > 3:
            bracket = max(bracket, 4)
            reasons.append(f"Has {game_changers_count} Game Changers (>3 requires Bracket 4+)")
        elif game_changers_count > 0:
            bracket = max(bracket, 3)
            reasons.append(f"Has {game_changers_count} Game Changer(s) (requires Bracket 3+)")
        
        # Check mass land denial
        if has_mass_ld:
            bracket = max(bracket, 4)
            reasons.append("Contains mass land denial (requires Bracket 4+)")
        
        # Check extra turns
        if extra_turn_count >= 3:
            bracket = max(bracket, 4)
            reasons.append(f"Has {extra_turn_count} extra turn cards (high density requires Bracket 4+)")
        elif extra_turn_count >= 1:
            bracket = max(bracket, 3)
            reasons.append(f"Has {extra_turn_count} extra turn card(s)")
        
        # Check tutor density
        if tutor_count >= 8:
            bracket = max(bracket, 4)
            reasons.append(f"Has {tutor_count} tutors (heavy tutor presence)")
        elif tutor_count >= 5:
            bracket = max(bracket, 3)
            reasons.append(f"Has {tutor_count} tutors (moderate tutor presence)")
        
        # Check for combo indicators
        if "combo" in archetypes:
            bracket = max(bracket, 3)
            reasons.append("Deck has combo elements")
        
        # If no issues found, explain why it's bracket 2
        if not reasons:
            reasons.append("No Game Changers, combo pieces, or problematic cards found")
            reasons.append("Deck appears to be at precon power level")
        
        return bracket, reasons


# ============================================================================
# Test the analyzer if run directly
# ============================================================================
if __name__ == "__main__":
    print("Testing Deck Analyzer...")
    
    # Sample decklist for testing
    sample_deck = """
    1 Sol Ring
    1 Arcane Signet
    1 Command Tower
    1 Demonic Tutor
    1 Vampiric Tutor
    1 Rhystic Study
    1 Cyclonic Rift
    1 Force of Will
    35 Island
    25 Swamp
    """
    
    analyzer = DeckAnalyzer()
    result = analyzer.analyze_deck(sample_deck, commander_name="Test Commander")
    
    print(f"\n📊 Analysis Results:")
    print(f"  Commander: {result.commander}")
    print(f"  Total Cards: {result.total_cards}")
    print(f"  Game Changers: {result.game_changers_count}")
    print(f"  Game Changers Found: {result.game_changers_found}")
    print(f"  Suggested Bracket: {result.suggested_bracket}")
    print(f"  Reasoning:")
    for reason in result.bracket_reasoning:
        print(f"    - {reason}")
