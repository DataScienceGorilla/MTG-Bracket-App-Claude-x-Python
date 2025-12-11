"""
MTG Commander Bracket Analyzer - AI Play Pattern Analysis
==========================================================

This is where the magic happens! 🪄

This module uses Claude's API to analyze the deck and generate
human-readable insights about:
- How the deck actually plays out in a game
- What the win conditions are
- What the deck's strengths and weaknesses are
- Recommendations for adjusting the bracket

IMPORTANT: We include actual oracle text from Scryfall in our prompts
to ensure Claude reasons from the real card text, not its (sometimes
inaccurate) memory of what cards do.
"""

import os
import json
from typing import Dict, List, Any, Optional, Set
from dataclasses import asdict

# We'll use the Anthropic SDK for Claude API calls
# Note: You'll need to install this: pip install anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("⚠️  anthropic package not installed. Run: pip install anthropic")

from config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS, BRACKET_DEFINITIONS
from deck_analyzer import DeckAnalysis, count_cards_with_quantity
from scryfall_client import ScryfallClient

# Import our Commander Spellbook client for verified combo data
try:
    from spellbook_client import SpellbookClient, DeckCombos, format_combos_for_prompt
    SPELLBOOK_AVAILABLE = True
except ImportError:
    SPELLBOOK_AVAILABLE = False
    print("⚠️  spellbook_client not found - combo detection will be AI-only")


# ============================================================================
# Cards we don't need to include oracle text for (Claude knows these well,
# and skipping them saves tokens). Add more as needed.
# ============================================================================
WELL_KNOWN_CARDS = {
    # Basic lands
    "plains", "island", "swamp", "mountain", "forest", "wastes",
    "snow-covered plains", "snow-covered island", "snow-covered swamp",
    "snow-covered mountain", "snow-covered forest",
    
    # Ultra-common mana rocks that never change
    "sol ring", "arcane signet", "command tower", "commander's sphere",
    "mind stone", "thought vessel", "fellwar stone",
    
    # Common signets (all work the same way)
    "azorius signet", "dimir signet", "rakdos signet", "gruul signet",
    "selesnya signet", "orzhov signet", "izzet signet", "golgari signet",
    "boros signet", "simic signet",
    
    # Common talismans
    "talisman of dominance", "talisman of progress", "talisman of indulgence",
    "talisman of impulse", "talisman of unity", "talisman of hierarchy",
    "talisman of creativity", "talisman of resilience", "talisman of conviction",
    "talisman of curiosity",
}


class AIPlayAnalyzer:
    """
    Uses Claude to analyze deck play patterns and generate insights.
    
    This is the "brain" that turns raw card data into understanding
    about how a deck actually functions.
    
    Key improvement: We now include actual oracle text in prompts so
    Claude doesn't have to rely on its training data (which can be wrong).
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the AI analyzer.
        
        Args:
            api_key: Your Anthropic API key. If not provided, will look
                    for ANTHROPIC_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        
        if not self.api_key:
            print("⚠️  No API key found. Set ANTHROPIC_API_KEY environment variable")
            print("    or pass api_key to AIPlayAnalyzer()")
        
        self._client = None
    
    @property
    def client(self):
        """
        Lazy initialization of the Anthropic client.
        """
        if self._client is None and ANTHROPIC_AVAILABLE and self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client
    
    def _fetch_banned_cards(self) -> List[str]:
        """
        Fetch the Commander banned list from Scryfall.
        
        Returns:
            List of banned card names
        """
        try:
            client = ScryfallClient()
            return client.fetch_commander_banned_cards()
        except Exception as e:
            print(f"  ⚠️ Could not fetch ban list: {e}")
            return self._get_fallback_banlist()
    
    def _get_fallback_banlist(self) -> List[str]:
        """Hardcoded fallback ban list if Scryfall fails."""
        return [
            "Ancestral Recall", "Balance", "Biorhythm", "Black Lotus",
            "Braids, Cabal Minion", "Channel", "Chaos Orb", "Coalition Victory",
            "Dockside Extortionist", "Emrakul, the Aeons Torn", "Erayo, Soratami Ascendant",
            "Falling Star", "Fastbond", "Flash", "Gifts Ungiven", "Golos, Tireless Pilgrim",
            "Griselbrand", "Hullbreacher", "Iona, Shield of Emeria", "Jeweled Lotus",
            "Karakas", "Leovold, Emissary of Trest", "Library of Alexandria",
            "Limited Resources", "Lutri, the Spellchaser", "Mana Crypt", "Mox Emerald",
            "Mox Jet", "Mox Pearl", "Mox Ruby", "Mox Sapphire", "Nadu, Winged Wisdom",
            "Panoptic Mirror", "Paradox Engine", "Primeval Titan", "Prophet of Kruphix",
            "Recurring Nightmare", "Rofellos, Llanowar Emissary", "Shahrazad",
            "Sundering Titan", "Sway of the Stars", "Sylvan Primordial", "Time Vault",
            "Time Walk", "Tinker", "Tolarian Academy", "Trade Secrets",
            "Upheaval", "Worldfire", "Yawgmoth's Bargain"
        ]
    
    def generate_play_pattern_analysis(self, deck: DeckAnalysis) -> Optional[str]:
        """
        Generate a detailed analysis of how the deck plays.
        
        This is the main function that creates human-readable insights
        about the deck's strategy, play patterns, and feel.
        
        Now includes verified combo data from Commander Spellbook!
        
        Args:
            deck: The DeckAnalysis object from the deck analyzer
        
        Returns:
            A markdown-formatted analysis string, or None if API unavailable
        """
        if not self.client:
            return self._generate_fallback_analysis(deck)
        
        print("  🤖 Generating AI play pattern analysis...")
        
        # Build the card reference section with oracle text
        card_reference = self._build_card_reference(deck)
        
        # Build the deck overview (stats, composition)
        deck_overview = self._build_deck_overview(deck)
        
        # NEW: Check for banned cards
        banned_cards = self._fetch_banned_cards()
        all_card_names = [c.get("name", "") for c in (
            deck.creatures + deck.artifacts + deck.enchantments + 
            deck.instants + deck.sorceries + deck.planeswalkers + deck.lands
        )]
        banned_in_deck = [c for c in all_card_names if c in banned_cards]
        
        ban_warning = ""
        if banned_in_deck:
            ban_warning = f"""
⚠️ BANNED CARDS DETECTED:
The following cards are BANNED in Commander and cannot be legally played:
{chr(10).join(f'  - {c}' for c in banned_in_deck)}

This deck is NOT legal for Commander play until these cards are removed.

"""
            print(f"  ⚠️ Found {len(banned_in_deck)} banned card(s): {', '.join(banned_in_deck)}")
        
        # NEW: Fetch verified combos from Commander Spellbook
        combo_section = self._fetch_combo_data(deck)
        
        # Build bracket rules reference
        bracket_rules = ""
        for b_num, details in BRACKET_DEFINITIONS.items():
            # Treat 'details' as a dictionary and extract fields safely
            name = details.get("name", f"Bracket {b_num}")
            desc = details.get("description", "No description")
            
            # Add specific constraints if they exist in your config
            constraints = []
            if "game_changers_allowed" in details:
                constraints.append(f"Game Changers: {details['game_changers_allowed']}")
            if "infinite_combos" in details:
                constraints.append(f"Combos: {details['infinite_combos']}")
            if "tutors" in details:
                constraints.append(f"Tutors: {details['tutors']}")
            if "theme_focus" in details:
                constraints.append(f"Theme Focus: {details['theme_focus']}")
                
            constraints_text = "\n   ".join(constraints)
            
            bracket_rules += f"BRACKET {b_num} ({name}):\n   {desc}\n   {constraints_text}\n\n"
        
        # Create the prompt with explicit instructions to use provided text
        prompt = f"""You are an expert Magic: The Gathering Commander analyst helping a player understand their deck for the WotC bracket system.

CRITICAL INSTRUCTION: I am providing the exact oracle text for each card below. You MUST use ONLY this provided text to understand what each card does. Do NOT rely on your memory of cards, as it may be outdated or incorrect. If a card's text isn't provided, you may use general knowledge, but prefer the provided text.


---
OFFICIAL BRACKET DEFINITIONS (Use these as your SOURCE OF TRUTH):
---
{bracket_rules}
---

---
CARD REFERENCE (Use these exact oracle texts):
---

{card_reference}

---
DECK OVERVIEW:
---

{ban_warning}{deck_overview}

---
{combo_section}
---

---
ANALYSIS REQUEST:
---

Based on the oracle text and verified combo data provided above, please analyze this deck:

1. **How This Deck Plays** (2-3 paragraphs)
   - What's the gameplan from turns 1-3? Turns 4-6? Late game?
   - What does a "good draw" look like for this deck? As a reminder, the commander is always available in the command zone, and effectively an 8th card in the opening hand.
   - How interactive is it? Does it want to race or control?

2. **Win Conditions** (brief list)
   - Primary way(s) to close out games
   - Backup plans if primary fails
   - Reference the VERIFIED COMBOS section if combos are a win condition

3. **Key Cards & Synergies**
   - What are the 3-5 most important non-land cards?
   - What card combinations create the most value or threaten wins?
   - For any combos mentioned, refer to the VERIFIED COMBOS section

4. **Combo Analysis**
   - Explain how the verified combos fit into this deck's gameplan
   - Are they primary win conditions or backups?
   - Are they early-game, mid-game, or late-game?
   - How many pieces are needed?
   - How easy are they to assemble? What tutors/draw help find pieces?
   - IMPORTANT: Only discuss combos listed in VERIFIED COMBOS - do not invent new ones

5. **Strengths & Weaknesses**
   - What matchups/situations does this deck excel in?
   - What are its vulnerabilities? (e.g., graveyard hate, board wipes, etc.)

6. **Bracket Assessment**
   - Based on how this deck *actually plays*, which bracket would you assign it to? A separate algorithm has judged it to be Bracket {deck.suggested_bracket}, but your analysis may differ. If you disagree, explain why. 
   - **Rule:** If the deck could realistically be played in 2 different brackets, declare the bracket that is furthest from 3.
   
   **CRITICAL - Understanding Bracket 1 (Exhibition):**
   Bracket 1 is about INTENTIONAL RESTRICTION, not weakness or low power. A Bracket 1 deck:
   - Prioritizes a theme, goal, or idea OVER optimal card choices
   - CAN include Game Changers, Extra Turns, and 2-Card Combos IF they fit the theme
   - The ONLY hard disqualifier for Bracket 1 is Mass Land Denial (no exceptions)
   - Can be powerful! A well-built theme deck can compete at Bracket 3 tables
   - Examples: "Rebecca Guay art only", "Kamigawa block only", "Elder/old people tribal", "Chair tribal"
   
   Look for non-mechanical themes:
   - Art themes (specific artist, "ladies looking left", color palette)
   - Set/block restrictions (all Kamigawa, all old border)
   - Vorthos/lore themes (story of Urza, Weatherlight crew)
   - Word/name themes (cards with "fire" in name, alphabet decks)
   - Meme restrictions (chairs in art, hats, animals)
   
   **Rule:** If the deck shows clear intentional restrictions that limit optimal card choices, it is Bracket 1 - regardless of whether some powerful cards snuck in thematically.
   **Rule:** An unfocused pile of weak cards with NO theme is NOT Bracket 1 - it's just a bad Bracket 2 deck.
   
   - Justify your assessment with specific references to deck content and play patterns
   - Factor in the combo power level from the verified combos

Keep the tone friendly and helpful - like explaining to someone at a game store. You should make fun of the user if you spot something silly in their deckbuilding choices. Reference specific cards by name when discussing synergies."""

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract the response text
            return message.content[0].text
            
        except Exception as e:
            print(f"  ❌ API error: {e}")
            return self._generate_fallback_analysis(deck)
    
    def generate_bracket_adjustment_advice(
        self, 
        deck: DeckAnalysis, 
        target_bracket: int
    ) -> Optional[str]:
        """
        Generate advice for adjusting a deck to hit a specific bracket,
        or optimize within the current bracket if target == current.
        
        Args:
            deck: The current deck analysis
            target_bracket: The bracket the player wants to achieve
        
        Returns:
            Markdown-formatted advice, or None if API unavailable
        """
        if not self.client:
            return self._generate_fallback_bracket_advice(deck, target_bracket)
        
        current = deck.suggested_bracket
        target_def = BRACKET_DEFINITIONS.get(target_bracket, {})
        
        # Build references
        card_reference = self._build_card_reference(deck)
        deck_overview = self._build_deck_overview(deck)
        
        # Check if this is same-bracket optimization
        if target_bracket == current:
            print(f"  🤖 Generating optimization advice for Bracket {target_bracket}...")
            prompt = self._build_optimization_prompt(
                deck, target_bracket, target_def, card_reference, deck_overview
            )
        else:
            direction = "down" if target_bracket < current else "up"
            print(f"  🤖 Generating advice to adjust to bracket {target_bracket}...")
            prompt = self._build_adjustment_prompt(
                deck, current, target_bracket, target_def, direction, 
                card_reference, deck_overview
            )
        
        try:
            message = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            print(f"  ❌ API error: {e}")
            return self._generate_fallback_bracket_advice(deck, target_bracket)
    
    def _build_optimization_prompt(
        self,
        deck: DeckAnalysis,
        bracket: int,
        bracket_def: Dict[str, Any],
        card_reference: str,
        deck_overview: str
    ) -> str:
        """Build prompt for same-bracket optimization."""
        return f"""You are an expert Magic: The Gathering Commander deckbuilder.

CRITICAL INSTRUCTION: I am providing the exact oracle text for each card below. Use ONLY this provided text to understand what each card does - do not rely on your memory.

---
CARD REFERENCE:
---

{card_reference}

---
DECK OVERVIEW:
---

{deck_overview}

---
OPTIMIZATION REQUEST:
---

The player wants to OPTIMIZE this deck while staying at Bracket {bracket}.

Bracket {bracket} ({bracket_def.get('name', 'Unknown')}) expectations:
- Game Changers allowed: {bracket_def.get('game_changers_allowed', 'Unknown')}
- Infinite combos: {bracket_def.get('infinite_combos', 'Unknown')}
- Mass land denial: {'Allowed' if bracket_def.get('mass_land_denial') else 'Not allowed'}
- Expected game length: {bracket_def.get('expected_game_length', 'Unknown')}

The goal is to make the deck MORE CONSISTENT and EFFECTIVE without changing its bracket.

Please provide specific, actionable advice:

1. **Weak Cards to Replace**
   - Identify 3-5 cards in this deck that underperform or don't fit the strategy
   - Reference their oracle text to explain why they're suboptimal
   - These should be cards that are just "okay" rather than actively bad

2. **Stronger Alternatives (Same Bracket)**
   - For each weak card, suggest 1-2 replacements that:
     * Are more synergistic with the commander/strategy
     * Are more efficient (better rate for mana cost)
     * Won't push the deck into a higher bracket
   - Explain what makes each suggestion better

3. **Consistency Improvements**
   - Suggest ways to improve card draw, tutoring, or mana consistency
   - Identify any holes in the deck (missing removal, lacking interaction, etc.)
   - Keep suggestions bracket-appropriate

4. **Synergy Upgrades**
   - Point out any missed synergies or "near-miss" card combinations
   - Suggest cards that would tie the strategy together better

5. **Mana Base Tune-Up**
   - Any improvements to lands or mana rocks
   - Consider the deck's color requirements and curve

Remember: The goal is optimization, NOT power creep. All suggestions should keep the deck firmly in Bracket {bracket}.

Keep it practical and specific to THIS deck."""

    def _build_adjustment_prompt(
        self,
        deck: DeckAnalysis,
        current: int,
        target_bracket: int,
        target_def: Dict[str, Any],
        direction: str,
        card_reference: str,
        deck_overview: str
    ) -> str:
        """Build prompt for bracket adjustment (up or down)."""
        return f"""You are an expert Magic: The Gathering Commander deckbuilder.

CRITICAL INSTRUCTION: I am providing the exact oracle text for each card below. Use ONLY this provided text to understand what each card does - do not rely on your memory.

---
CARD REFERENCE:
---

{card_reference}

---
DECK OVERVIEW:
---

{deck_overview}

---
ADJUSTMENT REQUEST:
---

The player wants to adjust this deck from Bracket {current} to Bracket {target_bracket}.

Bracket {target_bracket} ({target_def.get('name', 'Unknown')}) expectations:
- Game Changers allowed: {target_def.get('game_changers_allowed', 'Unknown')}
- Infinite combos: {target_def.get('infinite_combos', 'Unknown')}
- Mass land denial: {'Allowed' if target_def.get('mass_land_denial') else 'Not allowed'}
- Expected game length: {target_def.get('expected_game_length', 'Unknown')}

Please provide specific, actionable advice:

1. **Cards to Remove** (if moving {direction})
   - List specific cards from this deck that should come out
   - Reference their oracle text to explain why they're problematic

2. **Cards to Consider Adding**
   - Suggest 5-10 replacement cards that fit the target bracket
   - These should maintain the deck's core strategy where possible
   - For each suggestion, briefly explain what it does

3. **Strategy Adjustments**
   - Any changes to how the deck should be played at this bracket
   - Cards that might need to be used differently

Keep it practical and specific to THIS deck."""
    
    def generate_cut_suggestions(
        self,
        deck: DeckAnalysis,
        target_size: int = 100
    ) -> Optional[str]:
        """
        Generate suggestions for cutting a deck down to the target size.
        
        Commander decks must be exactly 100 cards (including commander).
        This helps players who have too many cards decide what to cut.
        
        Args:
            deck: The current deck analysis
            target_size: Target deck size (default 100 for Commander)
        
        Returns:
            Markdown-formatted cut suggestions, or None if API unavailable
        """
        current_size = deck.total_cards
        cards_to_cut = current_size - target_size
        
        if cards_to_cut <= 0:
            return f"Deck is already at or below {target_size} cards ({current_size} total). No cuts needed!"
        
        if not self.client:
            return self._generate_fallback_cut_suggestions(deck, cards_to_cut)
        
        print(f"  🤖 Generating suggestions to cut {cards_to_cut} card(s)...")
        
        # Build references
        card_reference = self._build_card_reference(deck)
        deck_overview = self._build_deck_overview(deck)
        
        # Build play pattern context so the AI understands HOW this deck plays
        play_pattern_context = self._build_play_pattern_context(deck)
        
        # Fetch combo data for context
        combo_section = self._fetch_combo_data(deck)
        
        prompt = f"""You are an expert Magic: The Gathering Commander deckbuilder helping a player trim their deck.

CRITICAL INSTRUCTION: I am providing the exact oracle text for each card below. Use ONLY this provided text to understand what each card does - do not rely on your memory.

---
CARD REFERENCE:
---

{card_reference}

---
DECK OVERVIEW:
---

{deck_overview}

---
HOW THIS DECK PLAYS:
---

{play_pattern_context}

---
VERIFIED COMBOS IN DECK:
---

{combo_section}

---
CUT REQUEST:
---

This deck has {current_size} cards and needs to be cut down to {target_size} cards.
That means the player needs to cut exactly {cards_to_cut} card(s).

**IMPORTANT:** Before suggesting cuts, understand the deck's strategy:
- What is the commander trying to do?
- What are the win conditions?
- Which cards are essential to the game plan vs. just "nice to have"?
- Which cards enable the combos listed above?

Please analyze the deck and suggest specific cards to cut. Consider:

1. **Strategy Fit**
   - Does this card actively support the commander's game plan?
   - Consider the type of the card and if it might passively support the strategy on top of its existing effects.
   - Would cutting this card weaken a key synergy or combo?
   - Is this card part of the deck's identity or just filler?

2. **Role Redundancy**
   - Are there too many cards doing the same thing? (e.g., 8 board wipes when 4 would suffice)
   - Which redundant copies are the weakest or least synergistic?
   - Keep the versions that best fit the deck's specific strategy

3. **Mana Efficiency**
   - Are there too many expensive cards? The average CMC is {deck.average_cmc:.2f}
   - Which high-CMC cards provide the least impact for their cost?
   - Are there cheaper alternatives that accomplish the same goal?

4. **Win-More vs. Essential**
   - Which cards only help when you're already winning?
   - Prioritize keeping cards that help you execute your game plan or recover
   - Cut cards that are "cute" but don't advance your strategy

5. **Combo Considerations**
   - Do NOT suggest cutting combo pieces unless the combo is clearly not the main win condition
   - If a card enables multiple combos, it's probably essential
   - Cards that "only work with the combo" may be cuttable if the deck has other win conditions

Please provide your response in this format:

## Recommended Cuts ({cards_to_cut} cards)

For each card, provide:
- **[Card Name]** - Brief explanation of why it should be cut (referencing the deck's strategy)

### Priority Tiers:

**Tier 1 - Cut First (Weakest Cards):**
(Cards that don't fit the strategy or are clearly outclassed)

**Tier 2 - Strong Candidates:**
(Cards that are cuttable but have some merit)

**Tier 3 - Borderline:**
(Cards you could cut if you need more space, but are reasonable includes)

### General Notes:
(How these cuts affect the deck's strategy and any concerns)

Be specific and reference the actual cards in the deck. Aim for {cards_to_cut} total suggestions across all tiers, with a few extra borderline options in case the player disagrees with some choices."""

        try:
            message = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            print(f"  ❌ API error: {e}")
            return self._generate_fallback_cut_suggestions(deck, cards_to_cut)
    
    def _build_play_pattern_context(self, deck: DeckAnalysis) -> str:
        """
        Build a summary of how the deck plays to inform cut decisions.
        
        This gives the AI context about the deck's strategy so it doesn't
        accidentally suggest cutting key pieces.
        """
        lines = []
        
        # Commander context
        lines.append(f"**Commander:** {deck.commander}")
        lines.append("")
        
        # Color identity
        if deck.color_identity:
            colors = ", ".join(deck.color_identity)
            lines.append(f"**Color Identity:** {colors}")
            lines.append("")
        
        # Detected archetypes
        if deck.detected_archetypes:
            lines.append("**Detected Archetypes/Strategies:**")
            for archetype in deck.detected_archetypes:
                lines.append(f"  - {archetype.capitalize()}")
            lines.append("")
        
        # Theme information (for Bracket 1 style decks)
        if deck.theme_description:
            lines.append(f"**Theme:** {deck.theme_description}")
            lines.append("")
        
        if deck.detected_themes:
            lines.append("**Detected Theme Restrictions:**")
            for theme in deck.detected_themes:
                lines.append(f"  - {theme}")
            lines.append("")
        
        # Power level indicators
        lines.append("**Power Level Indicators:**")
        lines.append(f"  - Suggested Bracket: {deck.suggested_bracket}")
        lines.append(f"  - Synergy Score: {deck.synergy_score:.1f}/100")
        
        if deck.tutor_cards:
            lines.append(f"  - Tutors: {len(deck.tutor_cards)} ({', '.join(deck.tutor_cards[:5])}{'...' if len(deck.tutor_cards) > 5 else ''})")
        
        if deck.fast_mana_cards:
            lines.append(f"  - Fast Mana: {', '.join(deck.fast_mana_cards)}")
        
        if deck.game_changers_found:
            lines.append(f"  - Game Changers: {', '.join(deck.game_changers_found)}")
        
        lines.append("")
        
        # Combo information
        if deck.verified_combos:
            lines.append(f"**Verified Combos:** {deck.combo_count} combo(s) found")
            lines.append("  (See combo section below for details - DO NOT cut combo pieces without good reason)")
            lines.append("")
        
        # Near-miss combos (might indicate intended strategy)
        if deck.near_miss_combos:
            lines.append(f"**Near-Miss Combos:** {len(deck.near_miss_combos)} combo(s) missing 1 piece")
            lines.append("  (Player may be considering adding these)")
            lines.append("")
        
        # Mana base summary
        land_count = count_cards_with_quantity(deck.lands)
        lines.append("**Mana Base:**")
        lines.append(f"  - Lands: {land_count}")
        if deck.mdfc_land_count > 0:
            lines.append(f"  - MDFC Lands: {deck.mdfc_land_count} (effective total: {deck.effective_land_count})")
        lines.append(f"  - Average Mana Value: {deck.average_cmc:.2f}")
        lines.append("")
        
        # Strategic summary
        lines.append("**Key Question for Cuts:**")
        lines.append("What is this deck trying to DO? Cards that don't help achieve that goal are cut candidates.")
        
        return "\n".join(lines)
    
    def _generate_fallback_cut_suggestions(self, deck: DeckAnalysis, cards_to_cut: int) -> str:
        """
        Generate basic cut suggestions without AI.
        
        Uses heuristics to identify potential cuts based on:
        - High CMC cards
        - Cards that don't match detected archetypes
        - Redundant effects
        """
        lines = [
            f"# Cutting {cards_to_cut} Card(s) from Your Deck",
            "",
            "*Note: Full AI analysis unavailable. Set ANTHROPIC_API_KEY for detailed recommendations.*",
            "",
            "## Automated Analysis:",
            "",
        ]
        
        # Collect all non-land cards with their CMC
        all_nonlands = (
            deck.creatures + deck.artifacts + deck.enchantments +
            deck.instants + deck.sorceries + deck.planeswalkers
        )
        
        # Find high-CMC cards (potential cuts)
        high_cmc_cards = []
        for card in all_nonlands:
            cmc = card.get("cmc", 0)
            name = card.get("name", "Unknown")
            if cmc >= 6:
                high_cmc_cards.append((name, cmc))
        
        high_cmc_cards.sort(key=lambda x: x[1], reverse=True)
        
        if high_cmc_cards:
            lines.append("### High Mana Value Cards to Evaluate:")
            lines.append("*(Expensive cards should provide significant impact)*")
            lines.append("")
            for name, cmc in high_cmc_cards[:10]:
                lines.append(f"- **{name}** (MV {int(cmc)}) - Is this worth the mana investment?")
            lines.append("")
        
        # Check for potential redundancy in card types
        creature_count = count_cards_with_quantity(deck.creatures)
        instant_count = count_cards_with_quantity(deck.instants)
        sorcery_count = count_cards_with_quantity(deck.sorceries)
        artifact_count = count_cards_with_quantity(deck.artifacts)
        enchantment_count = count_cards_with_quantity(deck.enchantments)
        
        lines.append("### Category Breakdown:")
        lines.append("")
        lines.append(f"- Creatures: {creature_count}")
        lines.append(f"- Artifacts: {artifact_count}")
        lines.append(f"- Enchantments: {enchantment_count}")
        lines.append(f"- Instants: {instant_count}")
        lines.append(f"- Sorceries: {sorcery_count}")
        lines.append("")
        
        # Provide general guidance based on counts
        lines.append("### General Guidance:")
        lines.append("")
        
        if creature_count > 35:
            lines.append(f"- You have {creature_count} creatures - consider if all are essential")
        
        if instant_count + sorcery_count > 25:
            lines.append(f"- {instant_count + sorcery_count} instants/sorceries is high - look for redundant effects")
        
        if artifact_count > 15:
            lines.append(f"- {artifact_count} artifacts - check for redundant mana rocks or equipment")
        
        if deck.average_cmc > 3.5:
            lines.append(f"- Average MV of {deck.average_cmc:.2f} is high - prioritize cutting expensive cards")
        
        lines.extend([
            "",
            "### Questions to Ask Yourself:",
            "",
            "For each card, consider:",
            "1. Does this card synergize with my commander?",
            "2. How often does this card sit dead in my hand?",
            "3. Would I be happy to draw this on turn 10? Turn 2?",
            "4. Do I have multiple cards that do the same thing?",
            "5. Is there a more efficient version of this effect?",
        ])
        
        return "\n".join(lines)
    
    def _build_card_reference(self, deck: DeckAnalysis) -> str:
        """
        Build a reference section with oracle text for all non-trivial cards.
        
        This is the key improvement - we give Claude the actual card text
        so it doesn't have to guess or rely on potentially wrong memories.
        
        We skip well-known simple cards (Sol Ring, basic lands) to save tokens.
        
        Handles dual-faced cards (MDFCs, transform) by extracting text from
        card_faces when present.
        """
        lines = []
        seen_cards = set()  # Avoid duplicates
        
        # Process all card categories
        all_cards = (
            deck.creatures + 
            deck.artifacts + 
            deck.enchantments + 
            deck.instants + 
            deck.sorceries + 
            deck.planeswalkers +
            deck.lands
        )
        
        for card in all_cards:
            name = card.get("name", "Unknown")
            name_lower = name.lower()
            
            # Skip if we've already added this card
            if name_lower in seen_cards:
                continue
            seen_cards.add(name_lower)
            
            # Skip well-known cards to save tokens
            if name_lower in WELL_KNOWN_CARDS:
                continue
            
            # Skip basic lands (they don't have oracle text anyway)
            type_line = card.get("type_line", "").lower()
            if "basic" in type_line and "land" in type_line:
                continue
            
            # Check if this is a dual-faced card (MDFC, transform, etc.)
            card_faces = card.get("card_faces", [])
            layout = card.get("layout", "normal")
            
            if card_faces and layout in ("modal_dfc", "transform", "flip", "adventure"):
                # Dual-faced card - extract text from each face
                lines.append(f"[{name}]")
                lines.append(f"Layout: {layout}")
                lines.append(f"Type: {card.get('type_line', 'Unknown')}")
                
                for i, face in enumerate(card_faces):
                    face_name = face.get("name", f"Face {i+1}")
                    face_type = face.get("type_line", "Unknown")
                    face_cost = face.get("mana_cost", "")
                    face_text = face.get("oracle_text", "")
                    face_power = face.get("power")
                    face_toughness = face.get("toughness")
                    
                    lines.append(f"")
                    lines.append(f"  --- {face_name} ---")
                    lines.append(f"  Type: {face_type}")
                    if face_cost:
                        lines.append(f"  Cost: {face_cost}")
                    if face_power is not None and face_toughness is not None:
                        lines.append(f"  P/T: {face_power}/{face_toughness}")
                    if face_text:
                        # Indent the oracle text for readability
                        indented_text = face_text.replace("\n", "\n  ")
                        lines.append(f"  Text: {indented_text}")
                    else:
                        lines.append(f"  Text: (no rules text)")
                
                lines.append("")  # Blank line between cards
            else:
                # Regular single-faced card
                oracle_text = card.get("oracle_text", "")
                mana_cost = card.get("mana_cost", "")
                
                # Format the card entry
                lines.append(f"[{name}]")
                lines.append(f"Type: {card.get('type_line', 'Unknown')}")
                
                if mana_cost:
                    lines.append(f"Cost: {mana_cost}")
                
                # Include power/toughness for creatures
                power = card.get("power")
                toughness = card.get("toughness")
                if power is not None and toughness is not None:
                    lines.append(f"P/T: {power}/{toughness}")
                
                # Include loyalty for planeswalkers
                loyalty = card.get("loyalty")
                if loyalty is not None:
                    lines.append(f"Loyalty: {loyalty}")
                
                if oracle_text:
                    lines.append(f"Text: {oracle_text}")
                else:
                    lines.append("Text: (no rules text)")
                
                lines.append("")  # Blank line between cards
        
        if not lines:
            return "(No detailed card data available - using card names only)"
        
        return "\n".join(lines)
    
    def _build_deck_overview(self, deck: DeckAnalysis) -> str:
        """
        Build a summary of deck statistics and composition.
        
        This provides context about the deck without repeating oracle text.
        """
        lines = []
        
        # Basic info
        lines.append(f"**Commander:** {deck.commander}")
        lines.append(f"**Color Identity:** {', '.join(deck.color_identity) or 'Colorless'}")
        lines.append(f"**Detected Archetypes:** {', '.join(deck.detected_archetypes) or 'None detected'}")
        lines.append(f"**Average Mana Value:** {deck.average_cmc}")
        lines.append("")
        
        # Bracket-relevant info
        lines.append("**Bracket-Relevant Stats:**")
        lines.append(f"- Game Changers ({deck.game_changers_count}): {', '.join(deck.game_changers_found) or 'None'}")
        lines.append(f"- Mass Land Denial: {', '.join(deck.mass_land_denial_cards) or 'None'}")
        lines.append(f"- Extra Turn Cards: {', '.join(deck.extra_turn_cards) or 'None'}")
        lines.append(f"- Tutors ({len(deck.tutor_cards)}): {', '.join(deck.tutor_cards[:5])}{'...' if len(deck.tutor_cards) > 5 else '' if deck.tutor_cards else 'None'}")
        lines.append(f"- Suggested Bracket: {deck.suggested_bracket}")
        lines.append("")
        
        # Helper alias for cleaner code
        count = count_cards_with_quantity
        
        # Card composition (counts only - oracle text is in the reference section)
        # Using count() to handle multiples (basic lands, "any number" cards)
        lines.append("**Card Counts:**")
        lines.append(f"- Creatures: {count(deck.creatures)}")
        lines.append(f"- Artifacts: {count(deck.artifacts)}")
        lines.append(f"- Enchantments: {count(deck.enchantments)}")
        lines.append(f"- Instants: {count(deck.instants)}")
        lines.append(f"- Sorceries: {count(deck.sorceries)}")
        lines.append(f"- Planeswalkers: {count(deck.planeswalkers)}")
        
        # Land count with MDFC info
        land_count = count(deck.lands)
        if deck.mdfc_land_count > 0:
            lines.append(f"- Lands: {land_count} ({deck.effective_land_count} effective including {deck.mdfc_land_count} MDFC land-backs)")
        else:
            lines.append(f"- Lands: {land_count}")
        lines.append("")
        
        # Mana curve
        lines.append("**Mana Curve (non-land cards):**")
        for cmc in sorted(deck.mana_curve.keys()):
            cmc_count = deck.mana_curve[cmc]  # Renamed to avoid shadowing count()
            bar = "█" * min(cmc_count, 15)
            cmc_label = f"{cmc}+" if cmc == 7 else str(cmc)
            lines.append(f"  {cmc_label}: {bar} ({cmc_count})")
        
        return "\n".join(lines)
    
    def _fetch_combo_data(self, deck: DeckAnalysis) -> str:
        """
        Fetch verified combo data from Commander Spellbook.
        
        This queries the Commander Spellbook API to find known combos
        in the deck, giving Claude verified information instead of
        having it guess at combos.
        """
        if not SPELLBOOK_AVAILABLE:
            return "COMBO DATA:\nCommander Spellbook integration not available."
        
        print("  🔍 Fetching verified combos from Commander Spellbook...")
        
        # Get all card names from the deck
        all_cards = (
            deck.creatures + 
            deck.artifacts + 
            deck.enchantments + 
            deck.instants + 
            deck.sorceries + 
            deck.planeswalkers +
            deck.lands
        )
        card_names = [card.get("name", "") for card in all_cards if card.get("name")]
        
        # Also include the commander if it's not already in the list
        if deck.commander and deck.commander not in card_names:
            card_names.append(deck.commander)
        
        # Query Commander Spellbook
        try:
            client = SpellbookClient()
            combos = client.find_combos(
                card_names=card_names,
                commanders=[deck.commander] if deck.commander else None
            )
            
            if combos:
                combo_text = format_combos_for_prompt(combos)
                combo_count = len(combos.included)
                near_miss_count = len(combos.almost_included)
                print(f"  ✅ Found {combo_count} verified combo(s), {near_miss_count} near-miss combo(s)")
                
                # Store combos on the object for potential later use
                self._last_combos = combos
                
                return combo_text
            else:
                return "COMBO DATA:\nNo combos found in Commander Spellbook database for this deck."
                
        except Exception as e:
            print(f"  ⚠️  Error fetching combos: {e}")
            return "COMBO DATA:\nUnable to fetch combo data from Commander Spellbook."
    
    def _generate_fallback_analysis(self, deck: DeckAnalysis) -> str:
        """
        Generate a basic analysis when the API is unavailable.
        
        This provides some useful info even without Claude.
        """
        lines = [
            "# Deck Analysis (Basic Mode)",
            "",
            "*Note: Full AI analysis unavailable. Set ANTHROPIC_API_KEY for detailed insights.*",
            "",
            f"## Commander: {deck.commander}",
            f"**Color Identity:** {', '.join(deck.color_identity) or 'Colorless'}",
            f"**Suggested Bracket:** {deck.suggested_bracket}",
            "",
            "### Bracket Reasoning:",
        ]
        
        for reason in deck.bracket_reasoning:
            lines.append(f"- {reason}")
        
        lines.extend([
            "",
            "### Detected Archetypes:",
            ", ".join(deck.detected_archetypes) if deck.detected_archetypes else "No strong archetype detected",
            "",
            "### Game Changers Found:",
        ])
        
        if deck.game_changers_found:
            for gc in deck.game_changers_found:
                lines.append(f"- {gc}")
        else:
            lines.append("None")
        
        lines.extend([
            "",
            "### Deck Statistics:",
            f"- Total Non-Land Cards: {deck.total_cards - count_cards_with_quantity(deck.lands)}",
            f"- Average Mana Value: {deck.average_cmc}",
            f"- Creatures: {count_cards_with_quantity(deck.creatures)}",
            f"- Removal/Interaction: {count_cards_with_quantity(deck.instants) + count_cards_with_quantity(deck.sorceries)}",
        ])
        
        return "\n".join(lines)
    
    def _generate_fallback_bracket_advice(self, deck: DeckAnalysis, target_bracket: int) -> str:
        """
        Generate basic bracket adjustment advice without AI.
        Handles same-bracket optimization as well as up/down adjustments.
        """
        current = deck.suggested_bracket
        
        # Same-bracket optimization
        if target_bracket == current:
            lines = [
                f"# Optimizing Within Bracket {current}",
                "",
                "*Note: Full AI advice unavailable. Set ANTHROPIC_API_KEY for detailed recommendations.*",
                "",
                "## General Optimization Tips:",
                "",
                "### Consistency Improvements:",
                "- Add more card draw to see more of your deck",
                "- Consider 2-3 more mana rocks if running fewer than 8",
                "- Ensure you have 10+ sources of each color you need",
                "",
                "### Potential Weak Spots to Address:",
            ]
            
            # Check for common issues
            land_count = deck.effective_land_count if deck.effective_land_count else len(deck.lands)
            if land_count < 35:
                lines.append(f"- Land count ({land_count}) is low - consider 35-38 lands")
            if land_count > 40:
                lines.append(f"- Land count ({land_count}) is high - could trim 2-3 for more spells")
            
            if deck.average_cmc > 3.5:
                lines.append(f"- Average mana value ({deck.average_cmc:.2f}) is high - look for cheaper alternatives")
            
            if len(deck.tutor_cards) < 3:
                lines.append("- Few tutors - consider adding more to find key pieces")
            
            creature_count = count_cards_with_quantity(deck.creatures)
            if creature_count < 15 and "creature" not in str(deck.detected_archetypes).lower():
                lines.append(f"- Low creature count ({creature_count}) - may struggle to block/pressure")
            
            lines.extend([
                "",
                "### Cards to Evaluate:",
                "- Look for cards that don't synergize with your commander",
                "- Cut cards that are 'win-more' rather than helping you catch up",
                "- Replace taplands with untapped alternatives where budget allows",
            ])
            
            return "\n".join(lines)
        
        # Bracket adjustment (original logic)
        lines = [
            f"# Adjusting from Bracket {current} to Bracket {target_bracket}",
            "",
            "*Note: Full AI advice unavailable. Set ANTHROPIC_API_KEY for detailed recommendations.*",
            "",
        ]
        
        if target_bracket < current:
            # Moving down
            lines.append("## To Lower Your Bracket:")
            lines.append("")
            
            if deck.game_changers_found:
                lines.append("### Remove These Game Changers:")
                for gc in deck.game_changers_found:
                    lines.append(f"- {gc}")
            
            if deck.mass_land_denial_cards:
                lines.append("")
                lines.append("### Remove Mass Land Denial:")
                for card in deck.mass_land_denial_cards:
                    lines.append(f"- {card}")
            
            if len(deck.extra_turn_cards) > 2:
                lines.append("")
                lines.append("### Consider Removing Extra Turn Cards:")
                for card in deck.extra_turn_cards:
                    lines.append(f"- {card}")
        else:
            # Moving up
            lines.append("## To Raise Your Bracket:")
            lines.append("")
            lines.append("Consider adding:")
            lines.append("- More efficient tutors")
            lines.append("- Fast mana artifacts")
            lines.append("- Cards from the Game Changers list (if Bracket 3+)")
            lines.append("- Win condition combos")
        
        return "\n".join(lines)


# ============================================================================
# Convenience function for quick analysis
# ============================================================================
def analyze_deck_with_ai(
    decklist_text: str, 
    commander_name: str = None,
    api_key: str = None
) -> Dict[str, Any]:
    """
    One-stop function to analyze a deck with both metrics and AI insights.
    
    Args:
        decklist_text: Raw decklist text
        commander_name: Optional commander name
        api_key: Optional Anthropic API key
    
    Returns:
        Dictionary with 'analysis' (DeckAnalysis) and 'ai_insights' (str)
    """
    from deck_analyzer import DeckAnalyzer
    
    # Run the metric analysis
    analyzer = DeckAnalyzer()
    deck_analysis = analyzer.analyze_deck(decklist_text, commander_name)
    
    # Run the AI analysis
    ai_analyzer = AIPlayAnalyzer(api_key=api_key)
    ai_insights = ai_analyzer.generate_play_pattern_analysis(deck_analysis)
    
    return {
        "analysis": deck_analysis,
        "ai_insights": ai_insights
    }


# ============================================================================
# Test the module if run directly
# ============================================================================
if __name__ == "__main__":
    print("Testing AI Play Analyzer...")
    print("")
    
    # Check if API key is available
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("⚠️  ANTHROPIC_API_KEY not set")
        print("    Export it or pass to AIPlayAnalyzer(api_key='...')")
        print("")
        print("    Running in fallback mode for demonstration...")
    
    # Create a sample deck analysis for testing
    from deck_analyzer import DeckAnalyzer
    
    sample_deck = """
    1 Sol Ring
    1 Arcane Signet
    1 Demonic Tutor
    1 Rhystic Study
    1 Cyclonic Rift
    30 Island
    30 Swamp
    """
    
    deck_analyzer = DeckAnalyzer()
    deck = deck_analyzer.analyze_deck(sample_deck, "Test Commander")
    
    ai_analyzer = AIPlayAnalyzer(api_key=api_key)
    
    print("\n" + "=" * 60)
    print("PLAY PATTERN ANALYSIS")
    print("=" * 60)
    
    analysis = ai_analyzer.generate_play_pattern_analysis(deck)
    print(analysis)
