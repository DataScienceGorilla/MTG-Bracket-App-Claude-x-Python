"""
MTG Commander Bracket Analyzer - Configuration
==============================================

This file contains all the configuration constants for analyzing Commander decks
according to WotC's bracket system. The bracket system helps players find balanced
games by categorizing decks into 5 power levels.

BRACKET SUMMARY:
- Bracket 1 (Exhibition): Ultra-casual, themed decks. No Game Changers.
- Bracket 2 (Core): Precon-level power. No Game Changers.
- Bracket 3 (Upgraded): Stronger decks. Up to 3 Game Changers allowed.
- Bracket 4 (Optimized): High-power. Unlimited Game Changers.
- Bracket 5 (cEDH): Competitive. Full optimization.
"""

# ============================================================================
# GAME CHANGERS LIST (as of October 2025)
# These are cards that "dramatically warp Commander games" - having any of these
# affects which bracket your deck falls into.
# ============================================================================
GAME_CHANGERS = [
    # WHITE
    "Drannith Magistrate",
    "Enlightened Tutor",
    "Humility",
    "Smothering Tithe",
    "Teferi's Protection",
    
    # BLUE
    "Consecrated Sphinx",
    "Cyclonic Rift",
    "Fierce Guardianship",
    "Force of Will",
    "Gifts Ungiven",
    "Intuition",
    "Mystical Tutor",
    "Narset, Parter of Veils",
    "Rhystic Study",
    "Thassa's Oracle",
    
    # BLACK
    "Ad Nauseam",
    "Bolas's Citadel",
    "Braids, Cabal Minion",
    "Demonic Tutor",
    "Imperial Seal",
    "Necropotence",
    "Opposition Agent",
    "Orcish Bowmasters",
    "Tergrid, God of Fright // Tergrid's Lantern",  # Full DFC name
    "Vampiric Tutor",
    
    # RED
    "Gamble",
    "Jeska's Will",
    "Underworld Breach",
    "Panoptic Mirror",  # Added Oct 2025
    
    # GREEN
    "Crop Rotation",
    "Natural Order",
    "Seedborn Muse",
    "Survival of the Fittest",
    "Worldly Tutor",
    
    # MULTICOLOR
    "Grand Arbiter Augustin IV",
    "Notion Thief",
    "Aura Shards",
    "Coalition Victory",
    
    # COLORLESS/ARTIFACTS
    "Chrome Mox",
    "Grim Monolith",
    "Lion's Eye Diamond",
    "Mana Vault",
    "Mox Diamond",
    "The One Ring",  # Added Oct 2025
    
    # LANDS
    "Ancient Tomb",
    "Field of the Dead",  # Added Oct 2025
    "Gaea's Cradle",
    "Glacial Chasm",  # Added Oct 2025
    "Mishra's Workshop",  # Added Oct 2025
    "Serra's Sanctum",
    "The Tabernacle at Pendrell Vale",
    # Note: Strip Mine and Urza's Saga were REMOVED in Oct 2025 update
]

# ============================================================================
# BRACKET DEFINITIONS
# Each bracket has specific rules about what cards/strategies are allowed
# ============================================================================
BRACKET_DEFINITIONS = {
    1: {
        "name": "Exhibition",
        "description": "Ultra-casual, highly themed decks. Games go long.",
        "game_changers_allowed": 0,
        "infinite_combos": "none",
        "mass_land_denial": False,
        "extra_turns": "none",
        "tutors": "none",
        "expected_game_length": "10+ turns",
    },
    2: {
        "name": "Core",
        "description": "Preconstructed deck power level. Solid gameplay.",
        "game_changers_allowed": 0,
        "infinite_combos": "none",
        "mass_land_denial": False,
        "extra_turns": "sparse, not chained",
        "tutors": "sparse",
        "expected_game_length": "8-10 turns",
    },
    3: {
        "name": "Upgraded",
        "description": "Stronger than precons, carefully built decks.",
        "game_changers_allowed": 3,
        "infinite_combos": "none early-game (first 6 turns)",
        "mass_land_denial": False,
        "extra_turns": "low quantity, not looped",
        "tutors": "allowed",
        "expected_game_length": "6-8 turns",
    },
    4: {
        "name": "Optimized",
        "description": "High-power decks with strong synergies and combos.",
        "game_changers_allowed": "unlimited",
        "infinite_combos": "allowed",
        "mass_land_denial": True,
        "extra_turns": "allowed",
        "tutors": "heavily used",
        "expected_game_length": "4-6 turns",
    },
    5: {
        "name": "cEDH",
        "description": "Competitive EDH. Maximum optimization for the metagame.",
        "game_changers_allowed": "unlimited",
        "infinite_combos": "expected",
        "mass_land_denial": True,
        "extra_turns": "allowed",
        "tutors": "maximized",
        "expected_game_length": "3-5 turns",
    },
}

# ============================================================================
# KEYWORDS FOR DETECTING DECK STRATEGIES
# We use these to help the LLM understand what kind of deck it's analyzing
# ============================================================================
ARCHETYPE_KEYWORDS = {
    "combo": [
        "infinite", "loop", "untap", "goes infinite", "win the game",
        "combo", "chain", "trigger", "stack"
    ],
    "control": [
        "counter", "destroy", "exile", "bounce", "stax", "tax",
        "prison", "lock", "deny", "prevent"
    ],
    "aggro": [
        "haste", "attack", "combat", "damage", "power", "toughness",
        "creature", "buff", "pump"
    ],
    "midrange": [
        "value", "synergy", "advantage", "efficient", "flexible"
    ],
    "ramp": [
        "land", "mana", "ramp", "accelerate", "dork", "rock"
    ],
    "aristocrats": [
        "sacrifice", "die", "death", "blood artist", "grave pact"
    ],
    "tokens": [
        "token", "create", "copy", "populate", "swarm"
    ],
    "graveyard": [
        "graveyard", "reanimate", "dredge", "mill", "recursion"
    ],
    "voltron": [
        "equipment", "aura", "commander damage", "protection", "indestructible"
    ],
    "spellslinger": [
        "instant", "sorcery", "magecraft", "prowess", "storm"
    ],
}

# ============================================================================
# MASS LAND DENIAL CARDS
# These cards are restricted in brackets 1-3
# ============================================================================
MASS_LAND_DENIAL = [
    "Armageddon",
    "Catastrophe",
    "Decree of Annihilation",
    "Devastation",
    "Epicenter",
    "Fall of the Thran",
    "Global Ruin",
    "Impending Disaster",
    "Jokulhaups",
    "Keldon Firebombers",
    "Obliterate",
    "Ravages of War",
    "Ruination",
    "Sunder",
    "Thoughts of Ruin",
    "Worldslayer",
    "Boom // Bust",
    "Blood Moon",  # Considered mass land denial in spirit
    "Back to Basics",
    "Winter Orb",
    "Static Orb",
]

# ============================================================================
# EXTRA TURN CARDS
# Too many of these can bump your bracket up
# ============================================================================
EXTRA_TURN_CARDS = [
    "Time Walk",  # Vintage only, but included for completeness
    "Time Warp",
    "Temporal Manipulation",
    "Temporal Mastery",
    "Expropriate",
    "Time Stretch",
    "Beacon of Tomorrows",
    "Capture of Jingzhou",
    "Extra Turn",  # Generic placeholder for new cards
    "Karn's Temporal Sundering",
    "Nexus of Fate",
    "Part the Waterveil",
    "Savor the Moment",
    "Temporal Trespass",
    "Walk the Aeons",
    "Alrund's Epiphany",
    "Medomai the Ageless",
    "Notorious Throng",
    "Ral Zarek",
    "Seedtime",
    "Wanderwine Prophets",
]

# ============================================================================
# SCRYFALL API CONFIGURATION
# ============================================================================
SCRYFALL_API_BASE = "https://api.scryfall.com"
SCRYFALL_RATE_LIMIT_MS = 100  # Minimum ms between requests (10 requests/sec max)

# ============================================================================
# CLAUDE API CONFIGURATION
# You'll need to set your API key as an environment variable
# ============================================================================
CLAUDE_MODEL = "claude-sonnet-4-20250514"  # Good balance of cost and capability
CLAUDE_MAX_TOKENS = 2000
