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
from typing import Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

try:
    load_dotenv(override=True)  # Override any existing env vars with .env values
except ImportError:
    pass  # python-dotenv not installed, rely on system env vars


# Import our modules
from deck_analyzer import DeckAnalyzer, DeckAnalysis, count_cards_with_quantity
from ai_analyzer import AIPlayAnalyzer
from config import BRACKET_DEFINITIONS


# =============================================================================
# Display Functions
# =============================================================================

def print_banner():
    """Print the app banner."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║        ⚔️  MTG Commander Bracket Analyzer  ⚔️                   ║
║                                                               ║
║    Analyze your deck for the WotC bracket system              ║
║    with AI-powered play pattern insights                      ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
""")


def print_section_header(title: str):
    """Print a formatted section header."""
    print("\n" + "═" * 64)
    print(f"  {title}".center(64))
    print("═" * 64)


def print_menu(deck: Optional[DeckAnalysis] = None):
    """Print the main menu."""
    print("\n" + "─" * 50)
    print("  📋 MAIN MENU")
    print("─" * 50)
    
    if deck:
        print(f"  Current deck: {deck.commander} (Bracket {deck.suggested_bracket})")
        print(f"  Cards: {deck.total_cards}")
        print("─" * 50)
        print("  1. 📊 View deck analysis summary")
        print("  2. 🤖 AI play pattern analysis")
        print("  3. ✂️  Get cut suggestions" + (f" ({deck.total_cards - 100} over)" if deck.total_cards > 100 else " (at/under 100)"))
        print("  4. 🎯 Bracket adjustment/optimization advice")
        print("  5. 📂 Load a different deck")
        print("  6. 🚪 Exit")
    else:
        print("  No deck loaded")
        print("─" * 50)
        print("  1. 📂 Load a deck")
        print("  2. 🚪 Exit")
    
    print("─" * 50)


def print_analysis_results(deck: DeckAnalysis):
    """
    Print the analysis results in a formatted way.
    """
    # Header with commander
    print_section_header(f"📋 ANALYSIS: {deck.commander}")
    
    # Bracket result (big and prominent)
    bracket_def = BRACKET_DEFINITIONS.get(deck.suggested_bracket, {})
    bracket_name = bracket_def.get("name", "Unknown")
    
    print(f"""
       SUGGESTED BRACKET: {deck.suggested_bracket}              
       "{bracket_name}" 
    """)
    
    # Reasoning
    if deck.bracket_reasoning:
        print("  Reasoning:")
        for reason in deck.bracket_reasoning:
            print(f"    • {reason}")
    
    # Legality warnings (if any)
    if deck.legality_warnings:
        print_section_header("⚠️  LEGALITY WARNINGS")
        for warning in deck.legality_warnings:
            print(f"    {warning}")
    
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
    
    # MDFCs with land backs
    if deck.mdfc_lands:
        print_section_header("🃏 MODAL DOUBLE-FACED CARDS (Land Backs)")
        for mdfc in deck.mdfc_lands:
            name = mdfc.get("name", "Unknown")
            # Show front face name and type
            front_name = name.split(" // ")[0] if " // " in name else name
            type_line = mdfc.get("type_line", "")
            front_type = type_line.split(" // ")[0] if " // " in type_line else type_line
            print(f"    🔄 {front_name} ({front_type})")
        print(f"\n  These {deck.mdfc_land_count} card(s) can also be played as lands")
        print(f"  → Effective land count: {deck.effective_land_count} (actual lands + MDFCs)")

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
        bar_length = int((count / max_count) * 20)
        bar = "█" * bar_length
        cmc_label = f"{cmc}+" if cmc == 7 else f"{cmc} "
        print(f"    {cmc_label} │ {bar} ({count})")
    
    # Card composition summary
    print_section_header("📦 CARD COMPOSITION")
    
    # Use count helper for accurate counts (handles duplicates like basic lands)
    count = count_cards_with_quantity
    
    # Build land display string with MDFC info
    land_count = count(deck.lands)
    if deck.mdfc_land_count > 0:
        land_str = f"{land_count:3d}  ({deck.effective_land_count} effective incl. {deck.mdfc_land_count} MDFCs)"
    else:
        land_str = f"{land_count:3d}"
    
    print(f"""
    Creatures:     {count(deck.creatures):3d}
    Artifacts:     {count(deck.artifacts):3d}
    Enchantments:  {count(deck.enchantments):3d}
    Instants:      {count(deck.instants):3d}
    Sorceries:     {count(deck.sorceries):3d}
    Planeswalkers: {count(deck.planeswalkers):3d}
    Lands:         {land_str}
""")


# =============================================================================
# Input Functions
# =============================================================================

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


def get_menu_choice(max_choice: int) -> int:
    """Get a valid menu choice from the user."""
    while True:
        try:
            choice = input("\n  Enter choice: ").strip()
            if not choice:
                continue
            num = int(choice)
            if 1 <= num <= max_choice:
                return num
            print(f"  Please enter a number between 1 and {max_choice}")
        except ValueError:
            print("  Please enter a valid number")


def get_target_bracket(current_bracket: int) -> Optional[int]:
    """Get target bracket for adjustment/optimization."""
    print(f"\n  Current bracket: {current_bracket}")
    print("  Enter target bracket (1-5), same number for optimization,")
    print("  or press Enter to cancel:")
    
    response = input("  > ").strip()
    
    if not response:
        return None
    
    try:
        target = int(response)
        if 1 <= target <= 5:
            return target
        else:
            print("  Invalid bracket number.")
            return None
    except ValueError:
        print("  Invalid input.")
        return None


def get_target_deck_size() -> int:
    """Get target deck size for cut suggestions."""
    print("\n  Enter target deck size (default 100):")
    response = input("  > ").strip()
    
    if not response:
        return 100
    
    try:
        size = int(response)
        if 1 <= size <= 200:
            return size
        else:
            print("  Invalid size, using 100.")
            return 100
    except ValueError:
        print("  Invalid input, using 100.")
        return 100


# =============================================================================
# Deck Loading
# =============================================================================

def load_deck_from_file(filename: str) -> Tuple[Optional[DeckAnalysis], Optional[str]]:
    """
    Load and analyze a deck from a file.
    
    Returns:
        Tuple of (DeckAnalysis, error_message)
        If successful, error_message is None
        If failed, DeckAnalysis is None
    """
    try:
        with open(filename, "r") as f:
            decklist_text = f.read()
        print(f"   ✅ Loaded {len(decklist_text.splitlines())} lines")
    except FileNotFoundError:
        return None, f"File not found: {filename}"
    except Exception as e:
        return None, f"Error reading file: {e}"
    
    commander_name = get_commander_name()
    
    # Run analysis
    print("\n" + "─" * 60)
    analyzer = DeckAnalyzer()
    deck = analyzer.analyze_deck(decklist_text, commander_name)
    
    return deck, None


def load_deck_interactive() -> Optional[DeckAnalysis]:
    """
    Load and analyze a deck from user input.
    
    Returns:
        DeckAnalysis if successful, None if cancelled/empty
    """
    decklist_text = get_decklist_from_user()
    
    if not decklist_text.strip():
        print("\n  ❌ No decklist provided.")
        return None
    
    commander_name = get_commander_name()
    
    # Run analysis
    print("\n" + "─" * 60)
    analyzer = DeckAnalyzer()
    deck = analyzer.analyze_deck(decklist_text, commander_name)
    
    return deck


# =============================================================================
# Menu Actions
# =============================================================================

def action_view_summary(deck: DeckAnalysis):
    """Display the deck analysis summary."""
    print_analysis_results(deck)


def action_ai_analysis(deck: DeckAnalysis):
    """Run AI play pattern analysis."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("\n  💡 AI analysis requires an API key.")
        print("     Set ANTHROPIC_API_KEY environment variable to enable it.")
        return
    
    print_section_header("🤖 AI PLAY PATTERN ANALYSIS")
    ai_analyzer = AIPlayAnalyzer()
    ai_insights = ai_analyzer.generate_play_pattern_analysis(deck)
    print(ai_insights)


def action_cut_suggestions(deck: DeckAnalysis):
    """Generate cut suggestions."""
    target_size = get_target_deck_size()
    cards_to_cut = deck.total_cards - target_size
    
    if cards_to_cut <= 0:
        print(f"\n  ✅ Deck is already at or below {target_size} cards ({deck.total_cards} total).")
        print("     No cuts needed!")
        return
    
    print_section_header(f"✂️  CUT SUGGESTIONS ({cards_to_cut} cards to cut)")
    ai_analyzer = AIPlayAnalyzer()
    cuts = ai_analyzer.generate_cut_suggestions(deck, target_size=target_size)
    print(cuts)


def action_bracket_advice(deck: DeckAnalysis):
    """Generate bracket adjustment or optimization advice."""
    target = get_target_bracket(deck.suggested_bracket)
    
    if target is None:
        return
    
    if target == deck.suggested_bracket:
        print_section_header(f"📋 OPTIMIZATION ADVICE FOR BRACKET {target}")
    else:
        print_section_header(f"📋 ADVICE: MOVING TO BRACKET {target}")
    
    ai_analyzer = AIPlayAnalyzer()
    advice = ai_analyzer.generate_bracket_adjustment_advice(deck, target)
    print(advice)


# =============================================================================
# Main Menu Loop
# =============================================================================

def run_menu_loop(initial_deck: Optional[DeckAnalysis] = None):
    """
    Run the main menu loop.
    
    Args:
        initial_deck: Pre-loaded deck analysis (optional)
    """
    deck = initial_deck
    
    # Show initial analysis if deck was provided
    if deck:
        print_analysis_results(deck)
    
    while True:
        print_menu(deck)
        
        if deck:
            # Full menu with deck loaded
            choice = get_menu_choice(6)
            
            if choice == 1:
                action_view_summary(deck)
            elif choice == 2:
                action_ai_analysis(deck)
            elif choice == 3:
                action_cut_suggestions(deck)
            elif choice == 4:
                action_bracket_advice(deck)
            elif choice == 5:
                # Load new deck
                new_deck = load_deck_interactive()
                if new_deck:
                    deck = new_deck
                    print_analysis_results(deck)
            elif choice == 6:
                print("\n  👋 Thanks for using the Bracket Analyzer!")
                print("     Remember: Brackets are guidelines for pregame discussion,")
                print("     not hard rules. Talk to your playgroup! 🎲\n")
                break
        else:
            # Limited menu without deck
            choice = get_menu_choice(2)
            
            if choice == 1:
                new_deck = load_deck_interactive()
                if new_deck:
                    deck = new_deck
                    print_analysis_results(deck)
            elif choice == 2:
                print("\n  👋 Goodbye!\n")
                break


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """
    Main entry point for the bracket analyzer.
    """
    print_banner()
    
    initial_deck = None
    
    # Check for command line argument (file path)
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        print(f"📂 Reading decklist from: {filename}")
        
        deck, error = load_deck_from_file(filename)
        
        if error:
            print(f"   ❌ {error}")
            print("   Continuing to interactive mode...\n")
        else:
            initial_deck = deck
    
    # Run the menu loop
    run_menu_loop(initial_deck)


if __name__ == "__main__":
    main()