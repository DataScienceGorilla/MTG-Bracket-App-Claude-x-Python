#!/usr/bin/env python3
"""
MTG Commander Bracket Analyzer
==============================

A tool to analyze your Commander deck for the WotC bracket system,
with AI-powered insights into how your deck actually plays.

Usage:
    python main.py [decklist_file]
    
    If no file is provided, the program will prompt you to paste
    your decklist directly.

Requirements:
    pip install requests anthropic

Environment Variables:
    ANTHROPIC_API_KEY - Your Claude API key (optional but recommended)

Examples:
    # Analyze a deck file
    python main.py my_deck.txt
    
    # Paste a deck interactively
    python main.py
"""

import sys
import os
from typing import Optional

# Import our modules
from deck_analyzer import DeckAnalyzer, DeckAnalysis, count_cards_with_quantity
from ai_analyzer import AIPlayAnalyzer
from dotenv import load_dotenv
from config import BRACKET_DEFINITIONS


def print_banner():
    """Print the app banner."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║        ⚔️  MTG Commander Bracket Analyzer  ⚔️                   ║
║                                                               ║
║    Analyze your deck for the WotC bracket system              ║
║                                                               ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
""")


def print_section_header(title: str):
    """Print a formatted section header."""
    print("")
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def format_bracket_display(bracket: int) -> str:
    """
    Create a nice display string for a bracket number.
    
    Returns something like: "Bracket 3 (Upgraded)"
    """
    bracket_info = BRACKET_DEFINITIONS.get(bracket, {})
    name = bracket_info.get("name", "Unknown")
    return f"Bracket {bracket} ({name})"


def print_analysis_results(deck: DeckAnalysis):
    """
    Print the deck analysis results in a nice format.
    """
    print_section_header("📊 DECK ANALYSIS RESULTS")
    
    # Basic info
    print(f"""
  Commander:        {deck.commander}
  Color Identity:   {', '.join(deck.color_identity) or 'Colorless'}
  Total Cards:      {deck.total_cards}
  Average CMC:      {deck.average_cmc}
""")
    
    # Bracket result (the main thing!)
    bracket_display = format_bracket_display(deck.suggested_bracket)
    print(f"  🎯 SUGGESTED BRACKET: {bracket_display}")
    print("")
    
    # Reasoning
    print("  Reasoning:")
    for reason in deck.bracket_reasoning:
        print(f"    • {reason}")
    
    # Game Changers
    print_section_header("🃏 GAME CHANGERS FOUND")
    if deck.game_changers_found:
        for gc in deck.game_changers_found:
            print(f"    ⚡ {gc}")
        print(f"\n  Total: {deck.game_changers_count} Game Changer(s)")
        
        # Explain the limit
        if deck.game_changers_count <= 3:
            print("  → This is within the 3-card limit for Bracket 3")
        else:
            print("  → This exceeds the 3-card limit, requiring Bracket 4+")
    else:
        print("    None found! ✓")
        print("    → Eligible for Bracket 1 or 2")
    
    # Problematic cards
    if deck.mass_land_denial_cards or deck.extra_turn_cards:
        print_section_header("⚠️  BRACKET-AFFECTING CARDS")
        
        if deck.mass_land_denial_cards:
            print("\n  Mass Land Denial:")
            for card in deck.mass_land_denial_cards:
                print(f"    🚫 {card}")
        
        if deck.extra_turn_cards:
            print("\n  Extra Turn Effects:")
            for card in deck.extra_turn_cards:
                print(f"    ⏱️  {card}")
    
    # Tutors
    if deck.tutor_cards:
        print_section_header("🔍 TUTORS")
        for tutor in deck.tutor_cards[:10]:  # Show first 10
            print(f"    📚 {tutor}")
        if len(deck.tutor_cards) > 10:
            print(f"    ... and {len(deck.tutor_cards) - 10} more")
        print(f"\n  Total: {len(deck.tutor_cards)} tutor(s)")
    
    # Detected archetypes
    if deck.detected_archetypes:
        print_section_header("🎭 DETECTED ARCHETYPES")
        for archetype in deck.detected_archetypes:
            print(f"    • {archetype.capitalize()}")
    
    # Mana curve
    print_section_header("📈 MANA CURVE")
    max_count = max(deck.mana_curve.values()) if deck.mana_curve else 1
    
    for cmc in sorted(deck.mana_curve.keys()):
        count = deck.mana_curve[cmc]
        bar_length = int((count / max_count) * 30)
        bar = "█" * bar_length
        cmc_label = f"{cmc}+" if cmc == 7 else f" {cmc}"
        print(f"    {cmc_label} │ {bar} ({count})")
    
    # Card composition summary
    land_count = count_cards_with_quantity(deck.lands)
    if deck.mdfc_land_count > 0:
        land_str = f"{land_count:3d}  ({deck.effective_land_count} effective incl. {deck.mdfc_land_count} MDFCs)"
    else:
        land_str = f"{land_count:3d}"
    print_section_header("📦 CARD COMPOSITION")
    print(f"""
    Creatures:     {count_cards_with_quantity(deck.creatures):3d}
    Artifacts:     {count_cards_with_quantity(deck.artifacts):3d}
    Enchantments:  {count_cards_with_quantity(deck.enchantments):3d}
    Instants:      {count_cards_with_quantity(deck.instants):3d}
    Sorceries:     {count_cards_with_quantity(deck.sorceries):3d}
    Planeswalkers: {count_cards_with_quantity(deck.planeswalkers):3d}
    Lands:         {land_str}
""")


def get_decklist_from_user() -> str:
    """
    Prompt the user to paste their decklist.
    
    Returns the decklist text.
    """
    print("\n📝 Paste your decklist below.")
    print("   (One card per line, e.g., '1 Sol Ring' or '1x Sol Ring')")
    print("   Press Enter twice when done.\n")
    
    lines = []
    empty_count = 0
    
    while True:
        try:
            line = input()
            if line.strip() == "":
                empty_count += 1
                if empty_count >= 2:
                    break
            else:
                empty_count = 0
                lines.append(line)
        except EOFError:
            break
    
    return "\n".join(lines)


def get_commander_name() -> Optional[str]:
    """
    Optionally get the commander name from the user.
    """
    print("\n👑 Enter your commander's name (or press Enter to auto-detect):")
    name = input("   > ").strip()
    return name if name else None


def ask_for_ai_analysis() -> bool:
    """
    Ask if the user wants AI play pattern analysis.
    """
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("\n💡 AI play pattern analysis is available!")
        print("   Set ANTHROPIC_API_KEY environment variable to enable it.")
        return False
    
    print("\n🤖 Would you like AI-powered play pattern analysis? (y/n)")
    response = input("   > ").strip().lower()
    return response in ["y", "yes", ""]


def ask_for_bracket_adjustment(current_bracket: int) -> Optional[int]:
    """
    Ask if the user wants advice on adjusting to a different bracket.
    """
    print(f"\n🎯 Your deck is currently Bracket {current_bracket}.")
    print("   Would you like advice on adjusting to a different bracket?")
    print("   Enter a bracket number (1-5) or press Enter to skip:")
    
    response = input("   > ").strip()
    
    if not response:
        return None
    
    try:
        target = int(response)
        if 1 <= target <= 5:
            return target
        else:
            print("   Invalid bracket number. Skipping.")
            return None
    except ValueError:
        return None


def main():
    """
    Main entry point for the bracket analyzer.
    """
    print_banner()
    
    # Get the decklist
    decklist_text = ""
    commander_name = None
    
    if len(sys.argv) > 1:
        # Read from file
        filename = sys.argv[1]
        print(f"📂 Reading decklist from: {filename}")
        
        try:
            with open(filename, "r") as f:
                decklist_text = f.read()
            print(f"   ✅ Loaded {len(decklist_text.splitlines())} lines")
        except FileNotFoundError:
            print(f"   ❌ File not found: {filename}")
            sys.exit(1)
        except Exception as e:
            print(f"   ❌ Error reading file: {e}")
            sys.exit(1)
        
        commander_name = get_commander_name()
    else:
        # Get from user input
        decklist_text = get_decklist_from_user()
        commander_name = get_commander_name()
    
    if not decklist_text.strip():
        print("\n❌ No decklist provided. Exiting.")
        sys.exit(1)
    
    # Run the analysis
    print("\n" + "─" * 60)
    analyzer = DeckAnalyzer()
    deck = analyzer.analyze_deck(decklist_text, commander_name)
    
    # Display results
    print_analysis_results(deck)
    
    # Ask about AI analysis
    if ask_for_ai_analysis():
        print_section_header("🤖 AI PLAY PATTERN ANALYSIS")
        ai_analyzer = AIPlayAnalyzer()
        ai_insights = ai_analyzer.generate_play_pattern_analysis(deck)
        print(ai_insights)
    
    # Ask about bracket adjustment advice
    target_bracket = ask_for_bracket_adjustment(deck.suggested_bracket)
    
    if target_bracket and target_bracket != deck.suggested_bracket:
        print_section_header(f"📋 ADVICE: MOVING TO BRACKET {target_bracket}")
        ai_analyzer = AIPlayAnalyzer()
        advice = ai_analyzer.generate_bracket_adjustment_advice(deck, target_bracket)
        print(advice)
    
    # Closing
    print("\n" + "─" * 60)
    print("✨ Analysis complete!")
    print("")
    print("Remember: Brackets are guidelines for pregame discussion,")
    print("not hard rules. Talk to your playgroup! 🎲")
    print("")


if __name__ == "__main__":
    main()
