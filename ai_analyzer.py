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

This goes beyond simple calculation - it tries to understand
the deck the way an experienced player would.
"""

import os
import json
from typing import Dict, List, Any, Optional
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


class AIPlayAnalyzer:
    """
    Uses Claude to analyze deck play patterns and generate insights.
    
    This is the "brain" that turns raw card data into understanding
    about how a deck actually functions.
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
        
        Args:
            deck: The DeckAnalysis object from the deck analyzer
        
        Returns:
            A markdown-formatted analysis string, or None if API unavailable
        """
        if not self.client:
            return self._generate_fallback_analysis(deck)
        
        print("  🤖 Generating AI play pattern analysis...")
        
        # Build a summary of the deck for Claude
        deck_summary = self._build_deck_summary(deck)
        
        # Create the prompt
        prompt = f"""You are an expert Magic: The Gathering Commander analyst. 
You're helping a player understand their deck better for the new WotC bracket system.

Here's the deck information:

{deck_summary}

Please provide a comprehensive but conversational analysis covering:

1. **How This Deck Plays** (2-3 paragraphs)
   - What's the gameplan from turns 1-3? Turns 4-6? Late game?
   - What does a "good draw" look like for this deck?
   - How interactive is it? Does it want to race or control?

2. **Win Conditions** (brief list)
   - Primary way(s) to close out games
   - Backup plans if primary fails

3. **Key Cards & Synergies**
   - What are the 3-5 most important cards?
   - What combinations create the most value?

4. **Strengths & Weaknesses**
   - What matchups/situations does this deck excel in?
   - What are its vulnerabilities?

5. **Bracket Assessment**
   - Based on how this deck *actually plays*, does the suggested bracket of {deck.suggested_bracket} seem right?
   - Any nuance? (e.g., "This is technically bracket 3 due to Game Changers, but plays like a bracket 2 deck in practice")

Keep the tone friendly and helpful - like explaining to someone at a game store.
Use specific card names when discussing synergies."""

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
        
        deck_summary = self._build_deck_summary(deck)
        current = deck.suggested_bracket
        target_def = BRACKET_DEFINITIONS.get(target_bracket, {})
        
        direction = "down" if target_bracket < current else "up"
        
        prompt = f"""You are an expert Magic: The Gathering Commander deckbuilder.

A player wants to adjust their deck from Bracket {current} to Bracket {target_bracket}.

Bracket {target_bracket} ({target_def.get('name', 'Unknown')}) expectations:
- Game Changers allowed: {target_def.get('game_changers_allowed', 'Unknown')}
- Infinite combos: {target_def.get('infinite_combos', 'Unknown')}
- Mass land denial: {'Allowed' if target_def.get('mass_land_denial') else 'Not allowed'}
- Expected game length: {target_def.get('expected_game_length', 'Unknown')}

Current deck:
{deck_summary}

Please provide specific, actionable advice:

1. **Cards to Remove** (if moving {direction})
   - List specific cards from this deck that should come out
   - Explain why each is problematic for the target bracket

2. **Cards to Consider Adding**
   - Suggest 5-10 replacement cards that fit the target bracket
   - These should maintain the deck's core strategy where possible

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
    
    def _build_deck_summary(self, deck: DeckAnalysis) -> str:
        """
        Build a text summary of the deck for the AI prompt.
        
        This formats the deck data in a way that's easy for
        Claude to understand and analyze.
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
        lines.append(f"- Tutors ({len(deck.tutor_cards)}): {', '.join(deck.tutor_cards[:5])}{'...' if len(deck.tutor_cards) > 5 else ''}")
        lines.append(f"- Suggested Bracket: {deck.suggested_bracket}")
        lines.append("")
        
        # Card composition
        lines.append("**Deck Composition:**")
        lines.append(f"- Creatures ({len(deck.creatures)}): {self._summarize_cards(deck.creatures)}")
        lines.append(f"- Artifacts ({len(deck.artifacts)}): {self._summarize_cards(deck.artifacts)}")
        lines.append(f"- Enchantments ({len(deck.enchantments)}): {self._summarize_cards(deck.enchantments)}")
        lines.append(f"- Instants ({len(deck.instants)}): {self._summarize_cards(deck.instants)}")
        lines.append(f"- Sorceries ({len(deck.sorceries)}): {self._summarize_cards(deck.sorceries)}")
        lines.append(f"- Planeswalkers ({len(deck.planeswalkers)}): {self._summarize_cards(deck.planeswalkers)}")
        lines.append(f"- Lands ({len(deck.lands)})")
        lines.append("")
        
        # Mana curve
        lines.append("**Mana Curve:**")
        for cmc in sorted(deck.mana_curve.keys()):
            count = deck.mana_curve[cmc]
            bar = "█" * min(count, 20)
            cmc_label = f"{cmc}+" if cmc == 7 else str(cmc)
            lines.append(f"  {cmc_label}: {bar} ({count})")
        
        return "\n".join(lines)
    
    def _summarize_cards(self, cards: List[Dict[str, Any]], max_display: int = 8) -> str:
        """
        Create a comma-separated summary of card names.
        """
        if not cards:
            return "None"
        
        names = [card.get("name", "Unknown") for card in cards[:max_display]]
        result = ", ".join(names)
        
        if len(cards) > max_display:
            result += f" (+{len(cards) - max_display} more)"
        
        return result
    
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
