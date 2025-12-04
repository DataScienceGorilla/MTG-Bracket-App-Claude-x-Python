# MTG Commander Bracket Analyzer 🎴

A Python tool for analyzing your Magic: The Gathering Commander decks according to the official WotC bracket system, with **AI-powered insights** into how your deck actually plays.

## What is the Bracket System?

In late 2024, Wizards of the Coast introduced a 5-tier bracket system for Commander to help players find balanced games:

| Bracket | Name | Description |
|---------|------|-------------|
| 1 | Exhibition | Ultra-casual, highly themed decks. No Game Changers. |
| 2 | Core | Preconstructed deck power level. No Game Changers. |
| 3 | Upgraded | Stronger decks. Up to 3 Game Changers allowed. |
| 4 | Optimized | High-power with strong synergies and combos. |
| 5 | cEDH | Competitive. Maximum optimization. |

**Game Changers** are a list of ~51 cards that dramatically warp games (think Rhystic Study, Demonic Tutor, Cyclonic Rift).

## Features

✅ **Bracket Calculation** - Automatically determines your deck's bracket based on:
- Game Changers count
- Mass land denial cards
- Extra turn effects
- Tutor density
- Infinite combo potential

✅ **AI Play Pattern Analysis** (optional) - Uses Claude to explain:
- How your deck actually plays out in a game
- What your win conditions are
- Your deck's strengths and weaknesses
- Whether the calculated bracket "feels" right

✅ **Bracket Adjustment Advice** - Get specific recommendations for:
- Cards to remove to lower your bracket
- Cards to add to raise your bracket
- Strategy changes for different power levels

## Installation

```bash
# Clone or download this folder, then:
cd mtg_bracket_analyzer

# Install dependencies
pip install -r requirements.txt

# (Optional) Set your Anthropic API key for AI analysis
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Usage

### Basic Usage

```bash
# Analyze a deck file
python main.py your_deck.txt

# Or run interactively (paste deck when prompted)
python main.py
```

### Decklist Format

The analyzer accepts common decklist formats:

```
1 Sol Ring
1x Arcane Signet
4 Lightning Bolt
Forest
```

Lines starting with `#` or `//` are treated as comments.

### Example Session

```
╔═══════════════════════════════════════════════════════════════╗
║        ⚔️  MTG Commander Bracket Analyzer  ⚔️                  ║
╚═══════════════════════════════════════════════════════════════╝

📂 Reading decklist from: sample_decks/yuriko_ninjas.txt
   ✅ Loaded 89 lines

🔮 Starting deck analysis...
  📝 Parsing decklist...
  📋 Fetching official Game Changers list from Scryfall...
  🌐 Fetching card data from Scryfall...
  ✅ Found data for 67/67 cards
  🎯 Analysis complete! Suggested bracket: 4

============================================================
  📊 DECK ANALYSIS RESULTS
============================================================

  Commander:        Yuriko, the Tiger's Shadow
  Color Identity:   U, B
  Total Cards:      67
  Average CMC:      2.84

  🎯 SUGGESTED BRACKET: Bracket 4 (Optimized)

  Reasoning:
    • Has 11 Game Changers (>3 requires Bracket 4+)
    • Has 4 tutors (moderate tutor presence)
```

## Project Structure

```
mtg_bracket_analyzer/
├── main.py              # CLI entry point
├── config.py            # Game Changers list, bracket definitions
├── scryfall_client.py   # Scryfall API wrapper
├── deck_analyzer.py     # Bracket calculation engine
├── ai_analyzer.py       # Claude-powered play pattern analysis
├── requirements.txt     # Python dependencies
└── sample_decks/        # Example decklists for testing
    ├── yuriko_ninjas.txt
    └── teysa_casual.txt
```

## How It Works

### 1. Deck Parsing
Your decklist is parsed into individual cards with quantities.

### 2. Card Data Fetching
We use the [Scryfall API](https://scryfall.com/docs/api) to fetch complete card data including:
- Oracle text
- Types
- Mana value
- Keywords
- Color identity

### 3. Bracket Analysis
The analyzer checks your deck against bracket criteria:

- **Game Changers**: Scryfall maintains an official `is:gamechanger` filter
- **Mass Land Denial**: Cards like Armageddon, Blood Moon
- **Extra Turns**: Time Warp, Temporal Mastery, etc.
- **Tutors**: Cards with "search your library" (excluding basic land tutors)

### 4. AI Analysis (Optional)
If you have an Anthropic API key, Claude analyzes the deck to explain:
- Early/mid/late game patterns
- Primary and backup win conditions
- Key card synergies
- Matchup strengths and weaknesses

## Sample Output

```
============================================================
  🃏 GAME CHANGERS FOUND
============================================================
    ⚡ Rhystic Study
    ⚡ Bolas's Citadel
    ⚡ Necropotence
    ⚡ Vampiric Tutor
    ⚡ Demonic Tutor
    ⚡ Mystical Tutor
    ⚡ Imperial Seal
    ⚡ Cyclonic Rift
    ⚡ Force of Will
    ⚡ Fierce Guardianship
    ⚡ Chrome Mox
    ⚡ Mox Diamond
    ⚡ Mana Vault
    ⚡ Ancient Tomb
    ⚡ Urza's Saga

  Total: 15 Game Changer(s)
  → This exceeds the 3-card limit, requiring Bracket 4+
```

## Getting an API Key

For AI-powered analysis, you'll need an Anthropic API key:

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key
5. Set it as an environment variable:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

The tool works without an API key, but you won't get the detailed play pattern analysis.

## Tips for Using the Bracket System

1. **Brackets are guidelines, not rules** - Use them to facilitate pregame discussion
2. **Context matters** - A deck with 3 Game Changers might play very differently depending on *which* Game Changers
3. **Rule 0 still applies** - If your playgroup is okay with something, go for it
4. **Theme can override power** - An Exhibition deck might include a Game Changer if it's super on-theme

## Contributing

Feel free to extend this tool! Some ideas:
- Web interface
- Combo detection
- Price tracking
- Deck comparison mode
- Integration with Moxfield/Archidekt

## Credits

- Card data from [Scryfall](https://scryfall.com)
- AI analysis powered by [Claude](https://anthropic.com)
- Bracket system by [Wizards of the Coast](https://magic.wizards.com/en/formats/commander)

## License

MIT License - do whatever you want with it!

---

Happy brewing! 🧙‍♂️
