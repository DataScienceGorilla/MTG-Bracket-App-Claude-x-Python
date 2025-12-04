"""
MTG Commander Bracket Analyzer - Commander Spellbook Integration
================================================================

This module queries the Commander Spellbook API to find known combos
in a decklist. This is WAY more reliable than having an LLM try to
"discover" combos, since Commander Spellbook has a curated database
of 10,000+ verified combos with step-by-step instructions.

API Documentation: https://backend.commanderspellbook.com/schema/swagger/

Key endpoints:
- find-my-combos: POST a decklist, get back all combos in your deck
- variants: Search for specific combos by card names
"""

import requests
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


# ============================================================================
# Configuration
# ============================================================================

SPELLBOOK_API_BASE = "https://backend.commanderspellbook.com"
FIND_MY_COMBOS_ENDPOINT = f"{SPELLBOOK_API_BASE}/find-my-combos/"

# Rate limiting - be nice to the API
REQUEST_DELAY = 0.1  # 100ms between requests

# Bracket tag to WotC bracket mapping (from Commander Spellbook's source code)
# See: https://github.com/SpaceCowMedia/commander-spellbook-backend
BRACKET_TAG_MAP = {
    "R": 4,   # Ruthless -> Bracket 4
    "S": 3,   # Spicy -> Bracket 3  
    "PW": 3,  # Powerful -> Bracket 3
    "O": 2,   # Oddball -> Bracket 2
    "PA": 2,  # Precon Appropriate -> Bracket 2
    "C": 1,   # Casual -> Bracket 1
}


# ============================================================================
# Data Classes - Clean structures for combo data
# ============================================================================

@dataclass
class ComboCard:
    """A card that's part of a combo."""
    name: str
    type_line: str = ""
    must_be_commander: bool = False
    zone: str = "battlefield"  # Where the card needs to be (B=battlefield, H=hand, etc.)


@dataclass 
class ComboResult:
    """
    A single combo from Commander Spellbook.
    
    This contains everything you need to understand and explain the combo:
    - What cards are involved
    - What it produces (infinite mana, damage, etc.)
    - Step-by-step instructions
    - How "powerful" it is (bracket tag)
    """
    id: str                              # Spellbook's unique ID (e.g., "4131-4684")
    cards: List[ComboCard]               # Cards involved in the combo
    produces: List[str]                  # What the combo creates ("Infinite mana", etc.)
    description: str                     # Step-by-step instructions
    bracket_tag: str                     # Raw tag from Spellbook (C, PA, O, S, PW, R)
    suggested_bracket: int               # Mapped to WotC bracket (1-4)
    popularity: int = 0                  # How many EDHREC decks use this
    prerequisites: str = ""              # What you need before starting
    mana_needed: str = ""                # Mana required to execute
    is_legal_commander: bool = True      # Legal in Commander format?
    
    @property
    def permalink(self) -> str:
        """URL to view this combo on Commander Spellbook."""
        return f"https://commanderspellbook.com/combo/{self.id}"
    
    @property
    def card_names(self) -> List[str]:
        """Just the card names, for easy reference."""
        return [card.name for card in self.cards]


@dataclass
class DeckCombos:
    """
    All combos found in a deck.
    
    Separates combos into:
    - included: Combos where you have ALL the pieces
    - almost_included: Combos where you're missing 1-2 cards (suggestions!)
    - missing_cards: For almost_included combos, what cards would complete them
    """
    included: List[ComboResult] = field(default_factory=list)
    almost_included: List[ComboResult] = field(default_factory=list)
    missing_cards: Dict[str, List[str]] = field(default_factory=dict)  # combo_id -> missing card names
    color_identity: str = ""
    
    @property
    def total_combos(self) -> int:
        return len(self.included)
    
    @property
    def has_infinite(self) -> bool:
        """Check if any combo produces something infinite."""
        for combo in self.included:
            if any("infinite" in p.lower() for p in combo.produces):
                return True
        return False


# ============================================================================
# API Client
# ============================================================================

class SpellbookClient:
    """
    Client for the Commander Spellbook API.
    
    Main method is find_combos() which takes a list of card names
    and returns all known combos in that card pool.
    """
    
    def __init__(self):
        self._last_request_time = 0
    
    def _rate_limit(self):
        """Ensure we don't hammer the API."""
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()
    
    def find_combos(
        self, 
        card_names: List[str],
        commanders: List[str] = None
    ) -> Optional[DeckCombos]:
        """
        Find all known combos in a list of cards.
        
        This is the main entry point. Give it your decklist's card names,
        and it returns structured combo data.
        
        Args:
            card_names: List of card names in the deck
            commanders: Optional list of commander names (for commander-specific combos)
        
        Returns:
            DeckCombos object with included and almost-included combos,
            or None if the API request fails
        
        Example:
            client = SpellbookClient()
            combos = client.find_combos(["Basalt Monolith", "Mesmeric Orb", "Sol Ring"])
            
            for combo in combos.included:
                print(f"Combo: {combo.card_names}")
                print(f"Produces: {combo.produces}")
                print(f"How: {combo.description}")
        """
        self._rate_limit()
        
        # Build the request payload
        # The API expects: {"main": [{"card": "Name"}, ...], "commanders": [{"card": "Name"}, ...]}
        payload = {
            "main": [{"card": name} for name in card_names]
        }
        
        if commanders:
            payload["commanders"] = [{"card": name} for name in commanders]
        
        try:
            response = requests.post(
                FIND_MY_COMBOS_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30  # Generous timeout for large decklists
            )
            response.raise_for_status()
            data = response.json()
            
            return self._parse_response(data)
            
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Commander Spellbook API error: {e}")
            return None
        except (KeyError, ValueError) as e:
            print(f"  ⚠️  Error parsing Spellbook response: {e}")
            return None
    
    def _parse_response(self, data: Dict[str, Any]) -> DeckCombos:
        """
        Parse the raw API response into our clean data structures.
        
        The API returns a nested structure with 'included' and 'almostIncluded'
        arrays, each containing combo objects with card data, descriptions, etc.
        """
        result = DeckCombos()
        results = data.get("results", {})
        
        # Get color identity if provided
        result.color_identity = results.get("identity", "")
        
        # Parse included combos (all cards present)
        for raw_combo in results.get("included", []):
            combo = self._parse_combo(raw_combo)
            if combo:
                result.included.append(combo)
        
        # Parse almost-included combos (missing 1-2 cards)
        for raw_combo in results.get("almostIncluded", []):
            combo = self._parse_combo(raw_combo)
            if combo:
                result.almost_included.append(combo)
                
                # Track which cards are missing for this combo
                # We need to compare the combo's cards vs what's in the deck
                # The API doesn't directly tell us, but we can figure it out
                # by looking at which cards in 'uses' aren't in our deck
                # (This is approximate - the API doesn't give us a clean "missing" list)
        
        # Sort by popularity (most popular combos first)
        result.included.sort(key=lambda c: c.popularity, reverse=True)
        result.almost_included.sort(key=lambda c: c.popularity, reverse=True)
        
        return result
    
    def _parse_combo(self, raw: Dict[str, Any]) -> Optional[ComboResult]:
        """Parse a single combo object from the API response."""
        try:
            # Extract cards
            cards = []
            for use in raw.get("uses", []):
                card_data = use.get("card", {})
                
                # Map zone codes to readable names
                zone_codes = use.get("zoneLocations", ["B"])
                zone_map = {
                    "B": "battlefield",
                    "H": "hand", 
                    "G": "graveyard",
                    "L": "library",
                    "C": "command zone",
                    "E": "exile"
                }
                zone = zone_map.get(zone_codes[0] if zone_codes else "B", "battlefield")
                
                cards.append(ComboCard(
                    name=card_data.get("name", "Unknown"),
                    type_line=card_data.get("typeLine", ""),
                    must_be_commander=use.get("mustBeCommander", False),
                    zone=zone
                ))
            
            # Extract what the combo produces
            produces = []
            for prod in raw.get("produces", []):
                feature = prod.get("feature", {})
                produces.append(feature.get("name", "Unknown effect"))
            
            # Get bracket info
            bracket_tag = raw.get("bracketTag", "C")
            suggested_bracket = BRACKET_TAG_MAP.get(bracket_tag, 2)
            
            # Check legality
            legalities = raw.get("legalities", {})
            is_legal = legalities.get("commander", True)
            
            return ComboResult(
                id=raw.get("id", "unknown"),
                cards=cards,
                produces=produces,
                description=raw.get("description", "No description available"),
                bracket_tag=bracket_tag,
                suggested_bracket=suggested_bracket,
                popularity=raw.get("popularity") or 0 ,
                prerequisites=raw.get("notablePrerequisites", ""),
                mana_needed=raw.get("manaNeeded", ""),
                is_legal_commander=is_legal
            )
            
        except Exception as e:
            print(f"  ⚠️  Error parsing combo: {e}")
            return None


# ============================================================================
# Helper Functions
# ============================================================================

def format_combos_for_display(deck_combos: DeckCombos, max_display: int = 5) -> str:
    """
    Format combo data for human-readable display.
    
    This is useful for CLI output or debugging.
    """
    lines = []
    
    if not deck_combos or not deck_combos.included:
        lines.append("No known combos found in this deck.")
        return "\n".join(lines)
    
    lines.append(f"Found {len(deck_combos.included)} known combo(s):")
    lines.append("")
    
    for i, combo in enumerate(deck_combos.included[:max_display], 1):
        lines.append(f"**Combo {i}: {' + '.join(combo.card_names)}**")
        lines.append(f"  Produces: {', '.join(combo.produces)}")
        lines.append(f"  Bracket: {combo.suggested_bracket} ({combo.bracket_tag})")
        lines.append(f"  Popularity: {combo.popularity:,} decks")
        lines.append(f"  Steps:")
        
        # Format the description with nice indentation
        for step in combo.description.split("\n"):
            if step.strip():
                lines.append(f"    • {step.strip()}")
        
        lines.append(f"  Link: {combo.permalink}")
        lines.append("")
    
    if len(deck_combos.included) > max_display:
        lines.append(f"  ... and {len(deck_combos.included) - max_display} more combo(s)")
    
    # Show suggestions (almost-included combos)
    if deck_combos.almost_included:
        lines.append("")
        lines.append(f"💡 Potential combos (missing 1-2 cards): {len(deck_combos.almost_included)}")
        for combo in deck_combos.almost_included[:3]:
            lines.append(f"  • {' + '.join(combo.card_names)} → {', '.join(combo.produces)}")
    
    return "\n".join(lines)


def format_combos_for_prompt(deck_combos: DeckCombos, max_combos: int = 10) -> str:
    """
    Format combo data for inclusion in an LLM prompt.
    
    This gives the AI verified combo information so it doesn't have to
    guess or hallucinate combos. The AI can then explain how these combos
    fit into the deck's overall gameplan.
    """
    if not deck_combos or not deck_combos.included:
        return "No known combos found in Commander Spellbook database."
    
    lines = [
        "VERIFIED COMBOS (from Commander Spellbook database):",
        "These are confirmed, tested combos. Use this information to understand",
        "the deck's combo potential - do NOT invent combos not listed here.",
        ""
    ]
    
    for combo in deck_combos.included[:max_combos]:
        lines.append(f"[COMBO: {' + '.join(combo.card_names)}]")
        lines.append(f"Produces: {', '.join(combo.produces)}")
        lines.append(f"Bracket Impact: {combo.suggested_bracket}")
        lines.append(f"How it works:")
        lines.append(combo.description)
        if combo.prerequisites:
            lines.append(f"Prerequisites: {combo.prerequisites}")
        if combo.mana_needed:
            lines.append(f"Mana needed: {combo.mana_needed}")
        lines.append("")
    
    if len(deck_combos.included) > max_combos:
        lines.append(f"({len(deck_combos.included) - max_combos} additional combos not shown)")
    
    # Add suggestions section
    if deck_combos.almost_included:
        lines.append("")
        lines.append("NEAR-MISS COMBOS (deck is missing 1-2 cards):")
        for combo in deck_combos.almost_included[:5]:
            lines.append(f"• {' + '.join(combo.card_names)} → {', '.join(combo.produces)}")
    
    return "\n".join(lines)


# ============================================================================
# Test the module
# ============================================================================

if __name__ == "__main__":
    print("Testing Commander Spellbook Client...")
    print("")
    
    # Test with some cards that form a known combo
    test_cards = [
        "Basalt Monolith",
        "Mesmeric Orb",
        "Sol Ring",
        "Thassa's Oracle",
        "Demonic Consultation",
        "Island",
        "Swamp"
    ]
    
    print(f"Testing with cards: {test_cards[:5]}...")
    print("")
    
    client = SpellbookClient()
    combos = client.find_combos(test_cards)
    
    if combos:
        print(format_combos_for_display(combos))
    else:
        print("❌ Failed to fetch combos")