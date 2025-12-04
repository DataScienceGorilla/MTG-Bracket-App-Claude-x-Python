"""
MTG Commander Bracket Analyzer - Scryfall API Client
====================================================

This module handles all communication with the Scryfall API to fetch card data.
Scryfall is a free Magic: The Gathering database that provides comprehensive
card information including oracle text, types, colors, and more.

Key points about the Scryfall API:
- It's free to use but has rate limits (10 requests/second)
- All requests must include a User-Agent header
- Card data includes everything we need: text, types, colors, legality, etc.
"""

import requests
import time
from typing import Optional, Dict, List, Any
from config import SCRYFALL_API_BASE, SCRYFALL_RATE_LIMIT_MS


class ScryfallClient:
    """
    A simple client for the Scryfall API with rate limiting.
    
    This class handles:
    - Making API requests with proper headers
    - Rate limiting to avoid getting blocked
    - Error handling for missing cards
    """
    
    def __init__(self):
        # Track when we last made a request (for rate limiting)
        self._last_request_time = 0
        
        # Session keeps connections alive for better performance
        self._session = requests.Session()
        
        # Scryfall requires a User-Agent header identifying your app
        self._session.headers.update({
            "User-Agent": "MTGBracketAnalyzer/1.0",
            "Accept": "application/json"
        })
    
    def _rate_limit(self):
        """
        Wait if necessary to respect Scryfall's rate limit.
        
        Scryfall allows ~10 requests per second. We track time between
        requests and sleep if we're going too fast.
        """
        # Calculate time since last request (in milliseconds)
        now = time.time() * 1000  # Convert to milliseconds
        elapsed = now - self._last_request_time
        
        # If we haven't waited long enough, sleep for the remainder
        if elapsed < SCRYFALL_RATE_LIMIT_MS:
            sleep_time = (SCRYFALL_RATE_LIMIT_MS - elapsed) / 1000  # Convert back to seconds
            time.sleep(sleep_time)
        
        # Update our last request time
        self._last_request_time = time.time() * 1000
    
    def get_card_by_name(self, name: str, fuzzy: bool = True) -> Optional[Dict[str, Any]]:
        """
        Fetch a single card by name from Scryfall.
        
        Args:
            name: The card name to search for (e.g., "Sol Ring")
            fuzzy: If True, allows approximate matching (recommended)
        
        Returns:
            A dictionary with card data, or None if not found
        
        Example response includes:
            - name: "Sol Ring"
            - oracle_text: "{T}: Add {C}{C}."
            - type_line: "Artifact"
            - mana_cost: "{1}"
            - colors: []
            - keywords: []
            - legalities: {"commander": "legal", ...}
        """
        # Respect rate limits before making the request
        self._rate_limit()
        
        # Build the API URL
        # Scryfall's "named" endpoint finds exact or fuzzy matches
        endpoint = f"{SCRYFALL_API_BASE}/cards/named"
        params = {
            "fuzzy" if fuzzy else "exact": name
        }
        
        try:
            response = self._session.get(endpoint, params=params)
            
            # Check if the card was found
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # Card not found - this is normal for typos or wrong names
                print(f"  ⚠️  Card not found: '{name}'")
                return None
            else:
                # Some other error occurred
                print(f"  ❌ Error fetching '{name}': HTTP {response.status_code}")
                return None
                
        except requests.RequestException as e:
            print(f"  ❌ Network error fetching '{name}': {e}")
            return None
    
    def get_cards_bulk(self, names: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Fetch multiple cards by name.
        
        This is more efficient than calling get_card_by_name repeatedly
        because it can use Scryfall's collection endpoint for batches.
        
        Args:
            names: List of card names to fetch
        
        Returns:
            A dictionary mapping card names to their data (or None if not found)
        """
        # We'll use the collection endpoint for efficiency
        # It accepts up to 75 cards per request
        results = {}
        
        # Scryfall's collection endpoint takes identifiers
        # We'll use the "name" identifier type
        batch_size = 75
        
        for i in range(0, len(names), batch_size):
            batch = names[i:i + batch_size]
            
            # Build the request body for the collection endpoint
            identifiers = [{"name": name} for name in batch]
            
            self._rate_limit()
            
            try:
                response = self._session.post(
                    f"{SCRYFALL_API_BASE}/cards/collection",
                    json={"identifiers": identifiers}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Process found cards
                    for card in data.get("data", []):
                        # Use the oracle name as the key (handles split cards, etc.)
                        card_name = card.get("name", "")
                        results[card_name.lower()] = card
                    
                    # Log any cards that weren't found
                    for not_found in data.get("not_found", []):
                        name = not_found.get("name", "Unknown")
                        print(f"  ⚠️  Card not found in batch: '{name}'")
                        results[name.lower()] = None
                else:
                    print(f"  ❌ Batch request failed: HTTP {response.status_code}")
                    
            except requests.RequestException as e:
                print(f"  ❌ Network error in batch request: {e}")
        
        return results
    
    def search_cards(self, query: str, unique: str = "cards") -> List[Dict[str, Any]]:
        """
        Search for cards using Scryfall's full search syntax.
        
        Args:
            query: Scryfall search query (e.g., "is:gamechanger", "c:blue type:creature")
            unique: How to handle duplicates ("cards", "art", "prints")
        
        Returns:
            List of matching cards
        
        Useful queries:
            - "is:gamechanger" - All Game Changers
            - "o:infinite" - Cards mentioning infinite in oracle text
            - "t:creature c:green" - Green creatures
        """
        self._rate_limit()
        
        all_cards = []
        next_page = f"{SCRYFALL_API_BASE}/cards/search"
        params = {"q": query, "unique": unique}
        
        # Scryfall paginates results, so we need to follow the pages
        while next_page:
            try:
                response = self._session.get(next_page, params=params)
                params = None  # Only use params on first request
                
                if response.status_code == 200:
                    data = response.json()
                    all_cards.extend(data.get("data", []))
                    
                    # Check if there are more pages
                    if data.get("has_more"):
                        next_page = data.get("next_page")
                        self._rate_limit()  # Rate limit between pages too
                    else:
                        next_page = None
                else:
                    print(f"  ❌ Search failed: HTTP {response.status_code}")
                    break
                    
            except requests.RequestException as e:
                print(f"  ❌ Network error in search: {e}")
                break
        
        return all_cards
    
    def get_game_changers_list(self) -> List[str]:
        """
        Fetch the current official Game Changers list from Scryfall.
        
        Scryfall maintains an 'is:gamechanger' filter that tracks
        the official WotC Game Changers list.
        
        Returns:
            List of card names on the Game Changers list
        """
        print("📋 Fetching official Game Changers list from Scryfall...")
        
        cards = self.search_cards("is:gamechanger")
        return [card.get("name", "") for card in cards]


def parse_decklist(decklist_text: str) -> List[Dict[str, Any]]:
    """
    Parse a decklist from common formats into a structured list.
    
    Supports formats like:
        1 Sol Ring
        1x Commander's Sphere
        4 Lightning Bolt
        Forest (quantity assumed 1 if missing)
    
    Args:
        decklist_text: Raw decklist text, one card per line
    
    Returns:
        List of dicts with 'quantity' and 'name' keys
    """
    cards = []
    
    for line in decklist_text.strip().split("\n"):
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        
        # Skip section headers like "// Commander" or "SIDEBOARD:"
        if line.upper().startswith("COMMANDER") or line.upper().startswith("SIDEBOARD"):
            continue
        if line.startswith("//"):
            continue
            
        # Try to parse "quantity name" format
        # Examples: "1 Sol Ring", "1x Sol Ring", "4 Lightning Bolt"
        parts = line.split(None, 1)  # Split on first whitespace
        
        if len(parts) == 2:
            quantity_str, name = parts
            
            # Handle "1x" format
            quantity_str = quantity_str.rstrip("x").rstrip("X")
            
            try:
                quantity = int(quantity_str)
                cards.append({"quantity": quantity, "name": name.strip()})
            except ValueError:
                # If first part isn't a number, treat whole line as card name
                cards.append({"quantity": 1, "name": line})
        else:
            # Single word on line - probably just a card name
            cards.append({"quantity": 1, "name": line})
    
    return cards


# ============================================================================
# Test the module if run directly
# ============================================================================
if __name__ == "__main__":
    print("Testing Scryfall API client...")
    
    client = ScryfallClient()
    
    # Test single card fetch
    print("\n🔍 Testing single card fetch:")
    sol_ring = client.get_card_by_name("Sol Ring")
    if sol_ring:
        print(f"  Found: {sol_ring['name']}")
        print(f"  Type: {sol_ring['type_line']}")
        print(f"  Text: {sol_ring['oracle_text']}")
    
    # Test Game Changers fetch
    print("\n📋 Testing Game Changers fetch:")
    game_changers = client.get_game_changers_list()
    print(f"  Found {len(game_changers)} Game Changers")
    print(f"  First 5: {game_changers[:5]}")
    
    # Test decklist parsing
    print("\n📝 Testing decklist parsing:")
    sample_deck = """
    1 Sol Ring
    1x Arcane Signet
    4 Lightning Bolt
    Forest
    """
    parsed = parse_decklist(sample_deck)
    for card in parsed:
        print(f"  {card['quantity']}x {card['name']}")
