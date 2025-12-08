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

import requests
import time
from typing import Dict, List, Any, Set, Tuple, Optional
from dataclasses import dataclass, field
from config import (
    GAME_CHANGERS, MASS_LAND_DENIAL, EXTRA_TURN_CARDS,
    ARCHETYPE_KEYWORDS, BRACKET_DEFINITIONS,
    # New imports for enhanced bracket calculation
    CEDH_COMMANDERS_TIER1, CEDH_COMMANDERS_TIER2,
    FAST_MANA, FREE_INTERACTION, COMPETITIVE_STAX,
    CEDH_COMBO_PIECES, HIGH_POWER_STAPLES,
    TUTORS_PREMIUM, TUTORS_EFFICIENT, TUTORS_STANDARD, TUTORS_SLOW,
    BRACKET_SCORING,
    # Singleton exception cards
    UNLIMITED_COPIES_CARDS, LIMITED_COPIES_CARDS, BASIC_LAND_NAMES
)


# =============================================================================
# Helper function for counting cards with quantities
# =============================================================================

def count_cards_with_quantity(cards: List[Dict[str, Any]]) -> int:
    """
    Count total cards in a list, respecting quantities.
    
    Cards with _quantity field are counted that many times.
    This correctly handles:
    - Basic lands (e.g., 10x Island)
    - "Any number" cards (e.g., 30x Shadowborn Apostle)
    
    Example:
        30x Shadowborn Apostle stored as one dict with _quantity=30
        → returns 30, not 1
    
    Args:
        cards: List of card dicts, each may have _quantity field
        
    Returns:
        Total card count (sum of quantities)
    """
    return sum(card.get("_quantity", 1) for card in cards)
from scryfall_client import ScryfallClient, parse_decklist

# Optional import for combo detection
try:
    from spellbook_client import SpellbookClient, DeckCombos
    SPELLBOOK_AVAILABLE = True
    SPELLBOOK_IMPORT_ERROR = None
except ImportError as e:
    SPELLBOOK_AVAILABLE = False
    SPELLBOOK_IMPORT_ERROR = str(e)

# Optional import for theme detection
try:
    from theme_detector import ThemeDetector
    THEME_DETECTOR_AVAILABLE = True
except ImportError:
    THEME_DETECTOR_AVAILABLE = False


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
    
    # === NEW FIELDS FOR ENHANCED ANALYSIS ===
    
    # Tiered tutor breakdown
    tutors_premium: List[str] = field(default_factory=list)
    tutors_efficient: List[str] = field(default_factory=list)
    tutors_standard: List[str] = field(default_factory=list)
    tutors_slow: List[str] = field(default_factory=list)
    tutor_score: float = 0.0  # Weighted tutor score
    
    # Power level indicators
    fast_mana_cards: List[str] = field(default_factory=list)
    free_interaction_cards: List[str] = field(default_factory=list)
    high_power_staples: List[str] = field(default_factory=list)
    competitive_stax_cards: List[str] = field(default_factory=list)
    
    # cEDH signals
    cedh_signals: int = 0
    cedh_signal_breakdown: Dict[str, int] = field(default_factory=dict)
    is_cedh_commander: bool = False
    cedh_commander_tier: int = 0  # 0 = not cEDH, 1 = tier 1, 2 = tier 2
    
    # Combo data (from Commander Spellbook)
    verified_combos: List[Dict[str, Any]] = field(default_factory=list)
    combo_count: int = 0
    has_cedh_combos: bool = False
    near_miss_combos: List[Dict[str, Any]] = field(default_factory=list)
    
    # Theme/Synergy data (for Bracket 1 detection)
    synergy_score: float = 0.0           # How synergistic the cards are (0-100)
    restriction_score: float = 0.0        # How theme-restricted the deck is (0-100)
    detected_themes: List[str] = field(default_factory=list)  # e.g., ["single_artist", "set_restricted"]
    theme_description: Optional[str] = None  # Human-readable theme description
    bracket1_likelihood: float = 0.0      # Likelihood this is a Bracket 1 deck (0-100)
    
    # Legality warnings (illegal duplicates, banned cards, etc.)
    legality_warnings: List[str] = field(default_factory=list)
    
    # MDFC tracking (Modal Double-Faced Cards with land backs)
    # These are categorized by their front face but can be played as lands
    mdfc_lands: List[Dict[str, Any]] = field(default_factory=list)  # Cards with land on back
    mdfc_land_count: int = 0  # Count of MDFCs that have land backs
    effective_land_count: int = 0  # lands + mdfc_lands for consistency calculations


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
        
        # Cache for tutor list from Scryfall (fetched once per session)
        # This avoids hitting the API repeatedly for large analyses
        self._tutor_cache = None
    
    def _count_cards(self, cards: List[Dict[str, Any]]) -> int:
        """
        Count total cards in a list, respecting quantities.
        
        Wrapper around module-level count_cards_with_quantity().
        """
        return count_cards_with_quantity(cards)
    
    def _validate_card_quantities(self, parsed_cards: List[Dict[str, Any]]) -> List[str]:
        """
        Check for illegal duplicate cards in Commander.
        
        Commander is singleton format - only 1 copy of each card allowed,
        with exceptions for:
        - Basic lands (unlimited)
        - "Any number" cards like Relentless Rats (unlimited)
        - Special cases like Seven Dwarves (up to 7) and Nazgûl (up to 9)
        
        Args:
            parsed_cards: List of {"name": str, "quantity": int} dicts
            
        Returns:
            List of warning strings for illegal duplicates
        """
        warnings = []
        
        for card in parsed_cards:
            name = card.get("name", "")
            name_lower = name.lower()
            quantity = card.get("quantity", 1)
            
            if quantity <= 1:
                continue  # No issue
            
            # Check if it's a basic land (unlimited allowed)
            if name_lower in BASIC_LAND_NAMES:
                continue
            
            # Check if it's an "any number" card (unlimited allowed)
            if name_lower in UNLIMITED_COPIES_CARDS:
                continue
            
            # Check if it's a limited-copies card
            if name_lower in LIMITED_COPIES_CARDS:
                limit = LIMITED_COPIES_CARDS[name_lower]
                if quantity > limit:
                    warnings.append(
                        f"⚠️ ILLEGAL: {quantity}x {name} (max {limit} allowed)"
                    )
                continue
            
            # Any other card with >1 copy is illegal in Commander
            warnings.append(
                f"⚠️ ILLEGAL: {quantity}x {name} (Commander is singleton - only 1 copy allowed)"
            )
        
        return warnings
    
    def _find_mdfc_lands(self, cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find Modal Double-Faced Cards (MDFCs) that have a land on the back.
        
        These cards are categorized by their front face (spell) but can
        also be played as lands, contributing to mana consistency.
        
        Examples:
        - Malakir Rebirth // Malakir Mire (Instant // Land)
        - Bala Ged Recovery // Bala Ged Sanctuary (Sorcery // Land)
        - Agadeem's Awakening // Agadeem, the Undercrypt (Sorcery // Land)
        
        Args:
            cards: List of card data dicts from Scryfall
            
        Returns:
            List of cards that are MDFCs with land backs
        """
        mdfc_lands = []
        
        for card in cards:
            # Check if it's a modal DFC
            layout = card.get("layout", "")
            if layout != "modal_dfc":
                continue
            
            # Check if the back face is a land
            card_faces = card.get("card_faces", [])
            if len(card_faces) >= 2:
                back_face = card_faces[1]
                front_face = card_faces[0]
                back_type = back_face.get("type_line", "")
                front_type = front_face.get("type_line", "")
                # If back face is a land, this is an MDFC land
                if "Land" in back_type and "Land" not in front_type:
                    mdfc_lands.append(card)
        
        return mdfc_lands
    
    def fetch_non_ramp_tutors(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch all tutor cards from Scryfall using oracle tags.
        
        Uses Scryfall's curated tags to find tutors while excluding:
        - Ramp spells (land tutors like Rampant Growth)
        - Fetchlands (Polluted Delta, etc.)
        
        Falls back to hardcoded tutor lists from config.py if Scryfall
        is unavailable.
        
        Returns:
            Dictionary mapping card names to their data:
            {
                "Demonic Tutor": {
                    "mana_cost": "{1}{B}",
                    "cmc": 2,
                    "type": "Sorcery",
                    "oracle_text": "Search your library...",
                    "scryfall_uri": "https://..."
                },
                ...
            }
        
        Note: Results are cached after first fetch to avoid repeated API calls.
        """
        # Return cached results if available
        if self._tutor_cache is not None:
            return self._tutor_cache
        
        print("  📚 Fetching tutor database from Scryfall...")
        
        # Query for tutors that aren't ramp or fetchlands
        # otag = oracle tag, curated by Scryfall
        query = 'otag:tutor -otag:ramp -otag:fetchland'
        
        url = "https://api.scryfall.com/cards/search"
        params = {
            'q': query,
            'unique': 'cards',
            'order': 'name'
        }
        
        tutor_dictionary = {}
        api_success = False
        
        while url:
            try:
                response = requests.get(url, params=params, timeout=10)
                
                # Handle rate limiting
                if response.status_code == 429:
                    print("  ⏳ Rate limited, waiting...")
                    time.sleep(5)
                    continue
                
                if response.status_code != 200:
                    print(f"  ⚠️  Scryfall error: {response.status_code}")
                    break
                
                api_success = True
                data = response.json()
                
                # Process the batch of cards
                for card in data.get('data', []):
                    name = card.get('name')
                    
                    # Handle Mana Cost (check faces for MDFCs)
                    if 'mana_cost' in card:
                        mana_cost = card['mana_cost']
                    elif 'card_faces' in card:
                        mana_cost = card['card_faces'][0].get('mana_cost', "")
                    else:
                        mana_cost = ""
                    
                    tutor_dictionary[name] = {
                        "mana_cost": mana_cost,
                        "cmc": card.get("cmc", 0),
                        "type": card.get("type_line", ""),
                        "oracle_text": card.get("oracle_text", "See Card Faces"),
                        "scryfall_uri": card.get("scryfall_uri", "")
                    }
                
                # Pagination: Scryfall returns up to 175 cards per page
                if data.get('has_more'):
                    url = data.get('next_page')
                    params = {}  # next_page URL already has params
                    
                    # Be polite to the API (Scryfall asks for 50-100ms delay)
                    time.sleep(0.1)
                else:
                    url = None
                    
            except requests.exceptions.RequestException as e:
                print(f"  ⚠️  Network error fetching tutors: {e}")
                break
            except Exception as e:
                print(f"  ⚠️  Error fetching tutors: {e}")
                break
        
        # If API failed or returned no results, fall back to hardcoded lists
        if not api_success or len(tutor_dictionary) == 0:
            print("  ⚠️  Using fallback tutor list from config...")
            tutor_dictionary = self._build_fallback_tutor_dict()
        else:
            print(f"  ✅ Loaded {len(tutor_dictionary)} tutors from Scryfall")
        
        # Cache the results
        self._tutor_cache = tutor_dictionary
        return tutor_dictionary
    
    def _build_fallback_tutor_dict(self) -> Dict[str, Dict[str, Any]]:
        """
        Build a tutor dictionary from our hardcoded config lists.
        
        Used as fallback when Scryfall API is unavailable.
        """
        tutor_dict = {}
        
        # Estimated CMCs for our categorized tutors
        # (We don't have exact data without Scryfall, so we estimate by tier)
        tier_cmcs = {
            "premium": 1.5,    # Premium tutors average ~1-2 CMC
            "efficient": 2.5,  # Efficient tutors average ~2-3 CMC
            "standard": 3.5,   # Standard tutors average ~3-4 CMC
            "slow": 5.0        # Slow tutors average ~5+ CMC
        }
        
        for name in TUTORS_PREMIUM:
            tutor_dict[name] = {"cmc": tier_cmcs["premium"], "type": "Unknown", "mana_cost": "", "oracle_text": ""}
        
        for name in TUTORS_EFFICIENT:
            tutor_dict[name] = {"cmc": tier_cmcs["efficient"], "type": "Unknown", "mana_cost": "", "oracle_text": ""}
        
        for name in TUTORS_STANDARD:
            tutor_dict[name] = {"cmc": tier_cmcs["standard"], "type": "Unknown", "mana_cost": "", "oracle_text": ""}
        
        for name in TUTORS_SLOW:
            tutor_dict[name] = {"cmc": tier_cmcs["slow"], "type": "Unknown", "mana_cost": "", "oracle_text": ""}
        
        print(f"  ✅ Loaded {len(tutor_dict)} tutors from fallback list")
        return tutor_dict
    
    def _find_tutors(self, cards: List[Dict[str, Any]]) -> List[str]:
        """
        Find cards that function as tutors using Scryfall's oracle tags.
        
        This is more accurate than text parsing because Scryfall curates
        which cards are actually tutors vs. just having "search your library"
        text (e.g., fetchlands, ramp spells).
        
        Args:
            cards: List of card data dictionaries
            
        Returns:
            List of tutor card names found in the deck
        """
        tutors = []
        
        # Get the tutor list from Scryfall (cached after first call)
        tutor_list = self.fetch_non_ramp_tutors()
        
        for card in cards:
            name = card.get("name", "")
            
            # Check if this card is in our tutor database
            if name in tutor_list:
                tutors.append(name)
            
            # Also check for DFCs (double-faced cards) - check front face name
            # Some tutors like "Bala Ged Recovery // Bala Ged Sanctuary" might
            # be in the list under just the front face name
            if " // " in name:
                front_face = name.split(" // ")[0]
                if front_face in tutor_list and name not in tutors:
                    tutors.append(name)
        
        return tutors
    
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
        
        # Step 1.5: Validate card quantities (check for illegal duplicates)
        legality_warnings = self._validate_card_quantities(parsed_cards)
        if legality_warnings:
            print(f"  ⚠️ Found {len(legality_warnings)} legality issue(s):")
            for warning in legality_warnings:
                print(f"      {warning}")
        
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
            commander = self._detect_commander(all_cards)
        
        # Step 5: Categorize cards by type
        categorized = self._categorize_cards(all_cards)
        
        # Step 5.5: Find MDFCs with land backs (for mana base evaluation)
        mdfc_lands = self._find_mdfc_lands(all_cards)
        mdfc_land_count = self._count_cards(mdfc_lands)
        land_count = self._count_cards(categorized["lands"])
        effective_land_count = land_count + mdfc_land_count
        
        if mdfc_lands:
            mdfc_names = [c.get("name", "").split(" // ")[0] for c in mdfc_lands]
            print(f"  🃏 Found {len(mdfc_lands)} MDFC(s) with land backs: {', '.join(mdfc_names[:3])}{'...' if len(mdfc_names) > 3 else ''}")
            print(f"      Lands: {land_count} ({effective_land_count} effective including MDFCs)")
        
        # Step 6: Find Game Changers
        game_changers = self._find_game_changers(all_cards)
        
        # Step 7: Find problematic cards (original)
        mass_ld = self._find_cards_by_name(all_cards, MASS_LAND_DENIAL)
        extra_turns = self._find_cards_by_name(all_cards, EXTRA_TURN_CARDS)
        
        # Step 8: ENHANCED - Classify tutors by tier
        print("  🔍 Analyzing tutor density...")
        tutor_breakdown = self._classify_tutors(all_cards)
        tutor_score = self._calculate_tutor_score(tutor_breakdown)
        all_tutors = (tutor_breakdown["premium"] + tutor_breakdown["efficient"] + 
                      tutor_breakdown["standard"] + tutor_breakdown["slow"])
        
        # Step 9: ENHANCED - Find power level indicators
        print("  ⚡ Detecting power level indicators...")
        power_cards = self._find_power_level_cards(all_cards)
        
        # Step 10: ENHANCED - Check cEDH commander status
        cedh_commander_tier = self._check_cedh_commander(commander)
        
        # Step 11: Detect archetypes
        archetypes = self._detect_archetypes(all_cards)
        
        # Step 12: Calculate mana curve
        mana_curve, avg_cmc = self._calculate_mana_curve(all_cards)
        
        # Step 13: Determine color identity
        color_identity = self._get_color_identity(all_cards)
        
        # Step 14: ENHANCED - Fetch combos from Commander Spellbook
        combo_data = self._fetch_combos(all_cards, commander)
        
        # Step 15: ENHANCED - Calculate cEDH signals
        print("  🎯 Calculating cEDH signals...")
        cedh_signals, cedh_breakdown = self._calculate_cedh_signals(
            commander=commander,
            cedh_commander_tier=cedh_commander_tier,
            fast_mana_count=len(power_cards["fast_mana"]),
            free_interaction_count=len(power_cards["free_interaction"]),
            stax_count=len(power_cards["competitive_stax"]),
            avg_cmc=avg_cmc,
            land_count=effective_land_count,  # Use effective count (includes MDFCs)
            combo_data=combo_data,
            tutor_score=tutor_score
        )
        
        # Step 16: ENHANCED - Theme/Synergy detection for Bracket 1
        theme_data = self._detect_theme_restrictions(all_cards)
        synergy_score = self._calculate_synergy_score(all_cards)
        
        # Calculate Bracket 1 likelihood
        bracket1_likelihood = 0.0
        if THEME_DETECTOR_AVAILABLE:
            detector = ThemeDetector()
            bracket1_likelihood, b1_reason = detector.get_bracket1_likelihood(
                synergy_score=synergy_score,
                restriction_score=theme_data.get("restriction_score", 0),
                game_changers_count=len(game_changers),
                fast_mana_count=len(power_cards["fast_mana"]),
                tutor_count=len(all_tutors),
                has_mass_land_denial=len(mass_ld) > 0  # Only hard disqualifier for B1
            )
            if bracket1_likelihood >= 50:
                print(f"  🎨 Bracket 1 signals detected: {bracket1_likelihood:.0f}% likelihood")
                print(f"      {b1_reason}")
        
        # Step 17: ENHANCED - Calculate bracket with all new data
        bracket, reasoning = self._calculate_bracket_enhanced(
            game_changers_count=len(game_changers),
            has_mass_ld=len(mass_ld) > 0,
            extra_turn_count=len(extra_turns),
            tutor_score=tutor_score,
            fast_mana_count=len(power_cards["fast_mana"]),
            staple_count=len(power_cards["high_power_staples"]),
            cedh_signals=cedh_signals,
            combo_data=combo_data,
            archetypes=archetypes,
            theme_data=theme_data,
            synergy_score=synergy_score,
            bracket1_likelihood=bracket1_likelihood
        )
        
        print(f"  🎯 Analysis complete! Suggested bracket: {bracket}")
        if cedh_signals >= BRACKET_SCORING["cedh_signal_threshold"]:
            print(f"  ⚠️  cEDH signals detected: {cedh_signals} points")
        
        return DeckAnalysis(
            commander=commander or "Unknown",
            total_cards=self._count_cards(all_cards),
            game_changers_found=game_changers,
            game_changers_count=len(game_changers),
            mass_land_denial_cards=mass_ld,
            extra_turn_cards=extra_turns,
            tutor_cards=all_tutors,
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
            all_cards=all_cards,
            # New fields
            tutors_premium=tutor_breakdown["premium"],
            tutors_efficient=tutor_breakdown["efficient"],
            tutors_standard=tutor_breakdown["standard"],
            tutors_slow=tutor_breakdown["slow"],
            tutor_score=tutor_score,
            fast_mana_cards=power_cards["fast_mana"],
            free_interaction_cards=power_cards["free_interaction"],
            high_power_staples=power_cards["high_power_staples"],
            competitive_stax_cards=power_cards["competitive_stax"],
            cedh_signals=cedh_signals,
            cedh_signal_breakdown=cedh_breakdown,
            is_cedh_commander=cedh_commander_tier > 0,
            cedh_commander_tier=cedh_commander_tier,
            verified_combos=combo_data.get("included", []),
            combo_count=combo_data.get("combo_count", 0),
            has_cedh_combos=combo_data.get("has_cedh_combos", False),
            near_miss_combos=combo_data.get("almost_included", []),
            # Theme/synergy fields
            synergy_score=synergy_score,
            restriction_score=theme_data.get("restriction_score", 0),
            detected_themes=theme_data.get("detected_themes", []),
            theme_description=theme_data.get("restriction_description"),
            bracket1_likelihood=bracket1_likelihood,
            # Legality
            legality_warnings=legality_warnings,
            # MDFC tracking
            mdfc_lands=mdfc_lands,
            mdfc_land_count=mdfc_land_count,
            effective_land_count=effective_land_count
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
        threshold = 15
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
    
    # =========================================================================
    # NEW ENHANCED ANALYSIS METHODS
    # =========================================================================
    
    def _classify_tutors(self, cards: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Classify tutors into tiers based on efficiency.
        
        Uses Scryfall's oracle tags to identify tutors, then classifies them:
        - Premium: 1-2 mana, flexible (Demonic Tutor, Vampiric Tutor)
        - Efficient: Cheap or powerful but more limited (Green Sun's Zenith)
        - Standard: 3-4 mana, functional (Diabolic Intent)
        - Slow: 5+ mana or very restricted (Diabolic Revelation)
        
        For tutors not in our predefined lists, we auto-classify by CMC.
        """
        result = {
            "premium": [],
            "efficient": [],
            "standard": [],
            "slow": []
        }
        
        # Build lookup sets from config (lowercase for matching)
        premium_set = {name.lower() for name in TUTORS_PREMIUM}
        efficient_set = {name.lower() for name in TUTORS_EFFICIENT}
        standard_set = {name.lower() for name in TUTORS_STANDARD}
        slow_set = {name.lower() for name in TUTORS_SLOW}
        
        # Get authoritative tutor list from Scryfall
        scryfall_tutors = self.fetch_non_ramp_tutors()
        
        for card in cards:
            name = card.get("name", "")
            name_lower = name.lower()
            
            # Check if this card is a tutor (using Scryfall's tags)
            is_tutor = name in scryfall_tutors
            
            # Also check DFC front face
            if not is_tutor and " // " in name:
                front_face = name.split(" // ")[0]
                is_tutor = front_face in scryfall_tutors
            
            if not is_tutor:
                continue
            
            # Now classify the tutor by tier
            # First check our predefined lists
            if name_lower in premium_set:
                result["premium"].append(name)
            elif name_lower in efficient_set:
                result["efficient"].append(name)
            elif name_lower in standard_set:
                result["standard"].append(name)
            elif name_lower in slow_set:
                result["slow"].append(name)
            else:
                # Tutor not in our lists - auto-classify by CMC
                # Get CMC from Scryfall data or card data
                if name in scryfall_tutors:
                    cmc = scryfall_tutors[name].get("cmc", 4)
                else:
                    cmc = card.get("cmc", 4)
                
                # Classify by mana cost
                if cmc <= 1:
                    result["premium"].append(name)
                elif cmc <= 2:
                    result["efficient"].append(name)
                elif cmc <= 3:
                    result["standard"].append(name)
                else:
                    result["slow"].append(name)
        
        return result
    
    def _calculate_tutor_score(self, tutor_breakdown: Dict[str, List[str]]) -> float:
        """
        Calculate a weighted tutor score.
        
        Premium tutors count for more since they enable faster, more consistent wins.
        """
        score = 0.0
        score += len(tutor_breakdown["premium"]) * BRACKET_SCORING["tutor_premium_weight"]
        score += len(tutor_breakdown["efficient"]) * BRACKET_SCORING["tutor_efficient_weight"]
        score += len(tutor_breakdown["standard"]) * BRACKET_SCORING["tutor_standard_weight"]
        score += len(tutor_breakdown["slow"]) * BRACKET_SCORING["tutor_slow_weight"]
        return score
    
    def _find_power_level_cards(self, cards: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Find cards that indicate high power level or cEDH.
        
        Returns lists of: fast_mana, free_interaction, high_power_staples, competitive_stax
        """
        result = {
            "fast_mana": [],
            "free_interaction": [],
            "high_power_staples": [],
            "competitive_stax": []
        }
        
        # Build lookup sets
        fast_mana_set = {name.lower() for name in FAST_MANA}
        free_int_set = {name.lower() for name in FREE_INTERACTION}
        staples_set = {name.lower() for name in HIGH_POWER_STAPLES}
        stax_set = {name.lower() for name in COMPETITIVE_STAX}
        
        for card in cards:
            name = card.get("name", "")
            name_lower = name.lower()
            
            if name_lower in fast_mana_set:
                result["fast_mana"].append(name)
            if name_lower in free_int_set:
                result["free_interaction"].append(name)
            if name_lower in staples_set:
                result["high_power_staples"].append(name)
            if name_lower in stax_set:
                result["competitive_stax"].append(name)
        
        return result
    
    def _check_cedh_commander(self, commander: str) -> int:
        """
        Check if the commander is known as a cEDH commander.
        
        Returns:
            0 = Not a known cEDH commander
            1 = Tier 1 cEDH commander (almost exclusively competitive)
            2 = Tier 2 cEDH commander (often competitive, sometimes casual)
        """
        if not commander:
            return 0
        
        commander_lower = commander.lower()
        
        # Check tier 1
        for name in CEDH_COMMANDERS_TIER1:
            if name.lower() in commander_lower or commander_lower in name.lower():
                return 1
        
        # Check tier 2
        for name in CEDH_COMMANDERS_TIER2:
            if name.lower() in commander_lower or commander_lower in name.lower():
                return 2
        
        return 0
    
    def _detect_theme_restrictions(self, cards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect potential Bracket 1 theme restrictions from card metadata.
        
        Uses ThemeDetector to analyze:
        - Artist concentration (Rebecca Guay tribal)
        - Set restriction (Kamigawa only)
        - Rarity restriction (pauper style)
        - Frame restriction (old border)
        - Alphabet patterns
        - Name word patterns
        
        Returns:
            Dict with detected_themes, restriction_score, restriction_description
        """
        if not THEME_DETECTOR_AVAILABLE:
            return {
                "detected_themes": [],
                "theme_details": {},
                "restriction_score": 0,
                "restriction_description": None
            }
        
        print("  🎨 Checking for theme restrictions...")
        detector = ThemeDetector()
        result = detector.detect_themes(cards)
        
        if result["detected_themes"]:
            print(f"      Detected: {', '.join(result['detected_themes'])}")
            print(f"      Restriction score: {result['restriction_score']:.1f}")
        
        return result
    
    def _calculate_synergy_score(self, cards: List[Dict[str, Any]]) -> float:
        """
        Calculate how synergistic the deck's cards are.
        
        Uses keyword/mechanic analysis to detect:
        - Tribal density (creature type concentration)
        - Mechanical density (keyword concentration)
        
        A LOW synergy score combined with HIGH restriction score
        suggests a Bracket 1 theme deck (restricted card pool).
        
        Returns:
            Score from 0-100
            < 15: Low synergy (possible Bracket 1)
            15-30: Average synergy
            > 30: High synergy (tribal or dedicated engine)
        """
        # Import synergy analyzer if available
        try:
            from synergy import SynergyAnalyzer
            analyzer = SynergyAnalyzer()
            score = analyzer.calculate_synergy_score(cards)
            print(f"  🔗 Synergy score: {score:.1f}")
            return score
        except ImportError:
            # Fallback: basic synergy calculation
            return self._calculate_basic_synergy(cards)
    
    def _calculate_basic_synergy(self, cards: List[Dict[str, Any]]) -> float:
        """
        Fallback synergy calculation if synergy.py isn't available.
        
        Looks for:
        - Creature type concentration (tribal)
        - Keyword concentration
        """
        from collections import Counter
        
        # Get creature subtypes
        subtypes = []
        creature_count = 0
        
        for card in cards:
            type_line = card.get("type_line", "")
            if "Creature" in type_line and "Basic" not in type_line:
                creature_count += 1
                if "—" in type_line:
                    parts = type_line.split("—")[1].strip().split()
                    subtypes.extend(parts)
        
        if creature_count < 10:
            return 0.0
        
        # Find most common subtype
        if subtypes:
            counts = Counter(subtypes)
            _, top_count = counts.most_common(1)[0]
            tribal_density = (top_count / creature_count) * 100
            return tribal_density
        
        return 0.0
    
    def _fetch_combos(self, cards: List[Dict[str, Any]], commander: str) -> Dict[str, Any]:
        """
        Fetch verified combos from Commander Spellbook.
        
        Returns dict with:
            - included: List of combos fully in the deck
            - almost_included: List of combos missing 1-2 cards
            - combo_count: Number of verified combos
            - has_cedh_combos: Whether any combos are cEDH-level
        """
        result = {
            "included": [],
            "almost_included": [],
            "combo_count": 0,
            "has_cedh_combos": False,
            "cedh_combo_count": 0,
            "bracket_impact": 0  # Highest bracket any combo pushes to
        }
        
        if not SPELLBOOK_AVAILABLE:
            error_msg = SPELLBOOK_IMPORT_ERROR or "Unknown error"
            print(f"  ⚠️  Commander Spellbook client not available: {error_msg}")
            print(f"      Make sure spellbook_client.py is in the same directory")
            return result
        
        print("  🔍 Checking Commander Spellbook for combos...", flush=True)
        
        try:
            client = SpellbookClient()
            card_names = [card.get("name", "") for card in cards]
            
            # Filter out empty names
            card_names = [n for n in card_names if n]
            
            combos = client.find_combos(
                card_names=card_names,
                commanders=[commander] if commander else None
            )
            
            if combos:
                result["combo_count"] = len(combos.included)
                
                # Process included combos
                for combo in combos.included:
                    combo_info = {
                        "cards": combo.card_names,
                        "produces": combo.produces,
                        "bracket_tag": combo.bracket_tag,
                        "suggested_bracket": combo.suggested_bracket,
                        "description": combo.description,
                        "popularity": combo.popularity
                    }
                    result["included"].append(combo_info)
                    
                    # Check if it's a cEDH-level combo (Ruthless tag)
                    if combo.bracket_tag == "R":
                        result["has_cedh_combos"] = True
                        result["cedh_combo_count"] += 1
                    
                    # Track highest bracket impact
                    result["bracket_impact"] = max(
                        result["bracket_impact"], 
                        combo.suggested_bracket
                    )
                
                # Process near-miss combos
                for combo in combos.almost_included[:10]:  # Limit to 10
                    combo_info = {
                        "cards": combo.card_names,
                        "produces": combo.produces,
                        "bracket_tag": combo.bracket_tag
                    }
                    result["almost_included"].append(combo_info)
                
                if result["combo_count"] > 0:
                    print(f"  ✅ Found {result['combo_count']} verified combo(s)")
                else:
                    print(f"  ✅ No combos found in Spellbook database")
            else:
                print(f"  ✅ No combos found in Spellbook database")
                
        except Exception as e:
            print(f"  ⚠️  Error fetching combos: {e}")
        
        return result
    
    def _calculate_cedh_signals(
        self,
        commander: str,
        cedh_commander_tier: int,
        fast_mana_count: int,
        free_interaction_count: int,
        stax_count: int,
        avg_cmc: float,
        land_count: int,
        combo_data: Dict[str, Any],
        tutor_score: float
    ) -> Tuple[int, Dict[str, int]]:
        """
        Calculate cEDH signals - indicators that a deck is competitive EDH.
        
        Returns:
            Tuple of (total_signals, breakdown_dict)
        """
        signals = 0
        breakdown = {}
        
        # Commander signal (+4 for tier 1, +2 for tier 2)
        if cedh_commander_tier == 1:
            signals += 4
            breakdown["cedh_commander_tier1"] = 4
        elif cedh_commander_tier == 2:
            signals += 2
            breakdown["cedh_commander_tier2"] = 2
        
        # Fast mana signals (+1 per piece)
        if fast_mana_count >= BRACKET_SCORING["fast_mana_cedh_threshold"]:
            bonus = fast_mana_count
            signals += bonus
            breakdown["fast_mana"] = bonus
        elif fast_mana_count >= 3:
            signals += fast_mana_count - 2
            breakdown["fast_mana"] = fast_mana_count - 2
        
        # Free interaction signals
        if free_interaction_count >= BRACKET_SCORING["free_interaction_cedh_threshold"]:
            bonus = free_interaction_count
            signals += bonus
            breakdown["free_interaction"] = bonus
        
        # Low average CMC signals
        if avg_cmc < BRACKET_SCORING["avg_cmc_cedh"]:
            signals += 2
            breakdown["low_avg_cmc"] = 2
        elif avg_cmc < BRACKET_SCORING["avg_cmc_optimized"]:
            signals += 1
            breakdown["optimized_curve"] = 1
        
        # Low land count signal
        if land_count <= BRACKET_SCORING["lands_cedh_max"]:
            signals += 1
            breakdown["low_land_count"] = 1
        
        # cEDH combo signals
        if combo_data.get("has_cedh_combos"):
            cedh_combos = combo_data.get("cedh_combo_count", 0)
            bonus = min(cedh_combos * 2, 4)  # Cap at +4
            signals += bonus
            breakdown["cedh_combos"] = bonus
        
        # High tutor density signal
        if tutor_score >= 15:
            signals += 2
            breakdown["heavy_tutors"] = 2
        elif tutor_score >= 10:
            signals += 1
            breakdown["moderate_tutors"] = 1
        
        # Competitive stax density
        if stax_count >= 5:
            signals += 2
            breakdown["stax_density"] = 2
        elif stax_count >= 3:
            signals += 1
            breakdown["stax_density"] = 1
        
        return signals, breakdown
    
    def _calculate_bracket_enhanced(
        self,
        game_changers_count: int,
        has_mass_ld: bool,
        extra_turn_count: int,
        tutor_score: float,
        fast_mana_count: int,
        staple_count: int,
        cedh_signals: int,
        combo_data: Dict[str, Any],
        archetypes: List[str],
        theme_data: Dict[str, Any] = None,
        synergy_score: float = 0.0,
        bracket1_likelihood: float = 0.0
    ) -> Tuple[int, List[str]]:
        """
        Calculate the suggested bracket based on comprehensive deck analysis.
        
        This is the enhanced bracket determination logic that uses:
        - Game Changers (official list)
        - Weighted tutor scoring
        - Fast mana density
        - High-power staple density
        - Verified combo data from Commander Spellbook
        - cEDH signals for Bracket 5 detection
        - Theme/synergy analysis for Bracket 1 detection
        
        Returns:
            Tuple of (bracket_number, list_of_reasons)
        """
        reasons = []
        bracket = 2  # Start at Core (default precon level)
        theme_data = theme_data or {}
        
        # =====================================================================
        # CHECK FOR BRACKET 1 (Theme/Exhibition) FIRST
        # =====================================================================
        # Bracket 1 is defined by THEME, not by absence of power cards
        # Only Mass Land Denial is a hard disqualifier (no thematic exceptions)
        # Game Changers, Extra Turns, 2-Card Combos CAN be allowed if thematic
        
        if not has_mass_ld and bracket1_likelihood >= 70:
            bracket = 1
            restriction_desc = theme_data.get("restriction_description", "Theme detected")
            reasons.append(f"🎨 Theme deck detected: {restriction_desc}")
            reasons.append(f"  Bracket 1 likelihood: {bracket1_likelihood:.0f}%")
            if game_changers_count > 0:
                reasons.append(f"  Note: {game_changers_count} Game Changer(s) may be thematic exceptions")
            if synergy_score < 20:
                reasons.append(f"  Low synergy ({synergy_score:.1f}) suggests restricted card pool")
            # Bracket 1 decks don't get bumped up by other signals - theme is intent
        elif not has_mass_ld and bracket1_likelihood >= 50:
            # Possible Bracket 1, but not confident enough to auto-assign
            reasons.append(f"🎨 Possible theme deck ({bracket1_likelihood:.0f}% likelihood)")
            if theme_data.get("restriction_description"):
                reasons.append(f"  Detected: {theme_data['restriction_description']}")
            if game_changers_count > 0:
                reasons.append(f"  Has {game_changers_count} Game Changer(s) - verify if thematic")
        
        # =====================================================================
        # CHECK FOR BRACKET 5 (cEDH)
        # =====================================================================
        if cedh_signals >= BRACKET_SCORING["cedh_signal_threshold"]:
            bracket = 5
            reasons.append(f"⚡ cEDH signals detected ({cedh_signals} points)")
            reasons.append("  Deck appears optimized for competitive play")
            # Still add other reasons for context
        
        # =====================================================================
        # COMBO ANALYSIS (from Commander Spellbook)
        # =====================================================================
        combo_count = combo_data.get("combo_count", 0)
        combo_bracket_impact = combo_data.get("bracket_impact", 0)
        
        if combo_data.get("has_cedh_combos"):
            bracket = max(bracket, 4)
            cedh_combo_count = combo_data.get("cedh_combo_count", 0)
            reasons.append(f"🎯 Has {cedh_combo_count} cEDH-level combo(s) (Ruthless tier)")
        
        if combo_bracket_impact >= 4 and combo_count > 0:
            bracket = max(bracket, 4)
            reasons.append(f"🎯 Has {combo_count} verified combo(s) (Bracket {combo_bracket_impact} impact)")
        elif combo_count >= 2:
            bracket = max(bracket, 3)
            reasons.append(f"🎯 Has {combo_count} verified combo(s)")
        elif combo_count == 1:
            reasons.append(f"🎯 Has 1 verified combo")
        else:
            # Always show combo status so user knows it was checked
            reasons.append(f"🎯 Verified combos: {combo_count} found")
        
        # =====================================================================
        # GAME CHANGERS
        # =====================================================================
        if game_changers_count > 3:
            bracket = max(bracket, 4)
            reasons.append(f"📜 Has {game_changers_count} Game Changers (>3 requires Bracket 4+)")
        elif game_changers_count > 0:
            bracket = max(bracket, 3)
            reasons.append(f"📜 Has {game_changers_count} Game Changer(s) (requires Bracket 3+)")
        
        # =====================================================================
        # MASS LAND DENIAL
        # =====================================================================
        if has_mass_ld:
            bracket = max(bracket, 4)
            reasons.append("💥 Contains mass land denial (requires Bracket 4+)")
        
        # =====================================================================
        # EXTRA TURNS
        # =====================================================================
        if extra_turn_count >= 3:
            bracket = max(bracket, 4)
            reasons.append(f"⏰ Has {extra_turn_count} extra turn cards (high density)")
        elif extra_turn_count >= 1:
            bracket = max(bracket, 3)
            reasons.append(f"⏰ Has {extra_turn_count} extra turn card(s)")
        
        # =====================================================================
        # TUTOR SCORE (Weighted)
        # =====================================================================
        if tutor_score >= BRACKET_SCORING["tutor_bracket4_threshold"]:
            bracket = max(bracket, 4)
            reasons.append(f"🔍 High tutor density (score: {tutor_score:.1f})")
        elif tutor_score >= BRACKET_SCORING["tutor_bracket3_threshold"]:
            bracket = max(bracket, 3)
            reasons.append(f"🔍 Moderate tutor density (score: {tutor_score:.1f})")
        
        # =====================================================================
        # FAST MANA
        # =====================================================================
        if fast_mana_count >= BRACKET_SCORING["fast_mana_bracket4_threshold"]:
            bracket = max(bracket, 4)
            reasons.append(f"💎 High fast mana count ({fast_mana_count} pieces)")
        elif fast_mana_count >= 2:
            bracket = max(bracket, 3)
            reasons.append(f"💎 Has {fast_mana_count} fast mana pieces")
        
        # =====================================================================
        # HIGH-POWER STAPLES
        # =====================================================================
        if staple_count >= BRACKET_SCORING["staples_bracket4_threshold"]:
            bracket = max(bracket, 4)
            reasons.append(f"⭐ High staple density ({staple_count} high-power cards)")
        elif staple_count >= BRACKET_SCORING["staples_bracket3_threshold"]:
            bracket = max(bracket, 3)
            reasons.append(f"⭐ Has {staple_count} high-power staples")
        
        # =====================================================================
        # COMBO ARCHETYPE (from detection)
        # =====================================================================
        if "combo" in archetypes and bracket < 3:
            bracket = max(bracket, 3)
            reasons.append("🔄 Deck has combo elements")
        
        # =====================================================================
        # DEFAULT EXPLANATION
        # =====================================================================
        if bracket == 2:
            reasons.append("✅ No significant power indicators found")
            reasons.append("   Deck appears to be at precon power level")
        
        return bracket, reasons
    
    # Keep the old method for backwards compatibility but mark as deprecated
    def _calculate_bracket(
        self,
        game_changers_count: int,
        has_mass_ld: bool,
        extra_turn_count: int,
        tutor_count: int,
        archetypes: List[str]
    ) -> Tuple[int, List[str]]:
        """
        DEPRECATED: Use _calculate_bracket_enhanced instead.
        
        This method is kept for backwards compatibility only.
        """
        # Convert old tutor count to approximate score
        tutor_score = tutor_count * 1.5  # Rough approximation
        
        return self._calculate_bracket_enhanced(
            game_changers_count=game_changers_count,
            has_mass_ld=has_mass_ld,
            extra_turn_count=extra_turn_count,
            tutor_score=tutor_score,
            fast_mana_count=0,
            staple_count=0,
            cedh_signals=0,
            combo_data={},
            archetypes=archetypes
        )


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
