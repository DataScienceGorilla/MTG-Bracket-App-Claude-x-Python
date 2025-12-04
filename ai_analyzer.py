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
from deck_analyzer import DeckAnalysis

# Import our Commander Spellbook client for verified combo data
try:
    from combos import SpellbookClient, DeckCombos, format_combos_for_prompt
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
        
        # NEW: Fetch verified combos from Commander Spellbook
        combo_section = self._fetch_combo_data(deck)
        
        # Create the prompt with explicit instructions to use provided text
        prompt = f"""You are an expert Magic: The Gathering Commander analyst helping a player understand their deck for the WotC bracket system.

CRITICAL INSTRUCTION: I am providing the exact oracle text for each card below. You MUST use ONLY this provided text to understand what each card does. Do NOT rely on your memory of cards, as it may be outdated or incorrect. If a card's text isn't provided, you may use general knowledge, but prefer the provided text.

---
CARD REFERENCE (Use these exact oracle texts):
---

{card_reference}

---
DECK OVERVIEW:
---

{deck_overview}

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
   - Based on how this deck *actually plays*, does Bracket {deck.suggested_bracket} seem right?
   - Factor in the combo power level from the verified combos
   - Any nuance? (e.g., "Technically bracket 3 due to Game Changers, but plays like bracket 2")

Keep the tone friendly and helpful - like explaining to someone at a game store. Reference specific cards by name when discussing synergies."""

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
        Generate advice for adjusting a deck to hit a specific bracket.
        
        Args:
            deck: The current deck analysis
            target_bracket: The bracket the player wants to achieve
        
        Returns:
            Markdown-formatted advice, or None if API unavailable
        """
        if not self.client:
            return self._generate_fallback_bracket_advice(deck, target_bracket)
        
        print(f"  🤖 Generating advice to adjust to bracket {target_bracket}...")
        
        # Build references
        card_reference = self._build_card_reference(deck)
        deck_overview = self._build_deck_overview(deck)
        
        current = deck.suggested_bracket
        target_def = BRACKET_DEFINITIONS.get(target_bracket, {})
        direction = "down" if target_bracket < current else "up"
        
        prompt = f"""You are an expert Magic: The Gathering Commander deckbuilder.

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
    
    def _build_card_reference(self, deck: DeckAnalysis) -> str:
        """
        Build a reference section with oracle text for all non-trivial cards.
        
        This is the key improvement - we give Claude the actual card text
        so it doesn't have to guess or rely on potentially wrong memories.
        
        We skip well-known simple cards (Sol Ring, basic lands) to save tokens.
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
            
            # Get card details
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
        
        # Card composition (counts only - oracle text is in the reference section)
        lines.append("**Card Counts:**")
        lines.append(f"- Creatures: {len(deck.creatures)}")
        lines.append(f"- Artifacts: {len(deck.artifacts)}")
        lines.append(f"- Enchantments: {len(deck.enchantments)}")
        lines.append(f"- Instants: {len(deck.instants)}")
        lines.append(f"- Sorceries: {len(deck.sorceries)}")
        lines.append(f"- Planeswalkers: {len(deck.planeswalkers)}")
        lines.append(f"- Lands: {len(deck.lands)}")
        lines.append("")
        
        # Mana curve
        lines.append("**Mana Curve (non-land cards):**")
        for cmc in sorted(deck.mana_curve.keys()):
            count = deck.mana_curve[cmc]
            bar = "█" * min(count, 15)
            cmc_label = f"{cmc}+" if cmc == 7 else str(cmc)
            lines.append(f"  {cmc_label}: {bar} ({count})")
        
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
            f"- Total Non-Land Cards: {deck.total_cards - len(deck.lands)}",
            f"- Average Mana Value: {deck.average_cmc}",
            f"- Creatures: {len(deck.creatures)}",
            f"- Removal/Interaction: {len(deck.instants) + len(deck.sorceries)}",
        ])
        
        return "\n".join(lines)
    
    def _generate_fallback_bracket_advice(self, deck: DeckAnalysis, target_bracket: int) -> str:
        """
        Generate basic bracket adjustment advice without AI.
        """
        current = deck.suggested_bracket
        
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
