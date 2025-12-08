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
        "infinite_combos": "Thematic or non-existent",
        "mass_land_denial": False,
        "extra_turns": "Thematic or non-existent",
        "tutors": "Occasional theme-based tutors or ways to tutor for a 'true commander' card",
        "expected_game_length": "10+ turns",
        "theme_focus": "Very high - deck may prioritize art, lore, or jokes over mechanics",
    },
    2: {
        "name": "Core",
        "description": "Preconstructed deck power level. Solid gameplay.",
        "game_changers_allowed": 0,
        "infinite_combos": "none",
        "mass_land_denial": False,
        "extra_turns": "sparse, not chained",
        "tutors": "allowed, but typically not optimized",
        "expected_game_length": "8-10 turns",
        "theme_focus": "Moderate - deck balances theme and mechanics",
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
        "theme_focus": "Low - deck greatly prioritizes mechanics over theme, but may still have some thematic elements",
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
        "theme_focus": "Minimal - deck is built for power and efficiency, with little regard for theme",
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
        "theme_focus": "None - deck is built solely for competitive performance",
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


# ============================================================================
# cEDH COMMANDER LISTS
# These commanders are primarily played competitively. Having one is a strong
# signal that the deck might be cEDH.
# ============================================================================
CEDH_COMMANDERS_TIER1 = [
    # Top tier - almost exclusively cEDH
    "Kinnan, Bonder Prodigy",
    "Najeela, the Blade-Blossom",
    "Tymna the Weaver",  # Partner, usually with competitive partners
    "Thrasios, Triton Hero",  # Partner
    "Kraum, Ludevic's Opus",  # Partner
    "Kodama of the East Tree",  # Partner
    "Rograkh, Son of Rohgahh",  # Partner
    "Sisay, Weatherlight Captain",
    "Kenrith, the Returned King",
    "Talion, the Kindly Lord",
    "The Gitrog Monster",
    "Selvala, Heart of the Wilds",
    "Godo, Bandit Warlord",
    "Malcolm, Keen-Eyed Navigator",  # Partner with Tana/Kediss
    "Tivit, Seller of Secrets",
    "Inalla, Archmage Ritualist",
    "Rog-Silas",  # Shorthand often used
    "Blue Farm",  # Archetype name, matches Thrasios/Tymna builds
]

CEDH_COMMANDERS_TIER2 = [
    # Strong competitive options but also played casually
    "Yuriko, the Tiger's Shadow",
    "Urza, Lord High Artificer",
    "Winota, Joiner of Forces",
    "Korvold, Fae-Cursed King",
    "Magda, Brazen Outlaw",
    "Heliod, Sun-Crowned",
    "K'rrik, Son of Yawgmoth",
    "Prossh, Skyraider of Kher",
    "Derevi, Empyrial Tactician",
    "Zur the Enchanter",
    "Selvala, Explorer Returned",
    "Teshar, Ancestor's Apostle",
    "Birgi, God of Storytelling",
    "Jhoira, Weatherlight Captain",
    "Emry, Lurker of the Loch",
    "Oswald Fiddlebender",
    "Grist, the Hunger Tide",
    "Raffine, Scheming Seer",
    "Kinnan, Bonder Prodigy",
    "Light-Paws, Emperor's Voice",
    "Krark, the Thumbless",  # Partner with Sakashima
    "Minsc & Boo, Timeless Heroes",
    "Shorikai, Genesis Engine",
]


# ============================================================================
# FAST MANA
# 0-1 mana accelerants that provide explosive starts. High density = cEDH signal.
# ============================================================================
FAST_MANA = [
    # 0-cost mana sources
    "Mana Crypt",
    "Mox Diamond",
    "Chrome Mox",
    "Mox Opal",
    "Mox Amber",
    "Jeweled Lotus",
    "Lotus Petal",
    "Lion's Eye Diamond",
    "Mana Vault",
    "Grim Monolith",
    
    # Land-based fast mana
    "Ancient Tomb",
    "City of Traitors",
    "Crystal Vein",
    "Gemstone Caverns",
    
    # 1-mana accelerants (above rate)
    "Sol Ring",  # Everyone runs this, but still counts
    "Springleaf Drum",  # In creature-heavy cEDH
]


# ============================================================================
# FREE INTERACTION
# Spells that cost 0 mana to cast. High density = cEDH signal.
# ============================================================================
FREE_INTERACTION = [
    # Free counterspells
    "Force of Will",
    "Force of Negation",
    "Fierce Guardianship",
    "Pact of Negation",
    "Mental Misstep",
    "Misdirection",
    "Commandeer",
    
    # Free removal/protection
    "Deflecting Swat",
    "Deadly Rollick",
    "Fierce Guardianship",
    "Submerge",
    "Snapback",
    "Bounty of the Hunt",
    
    # Free protection
    "Teferi's Protection",
    "Flawless Maneuver",
    "Slip Out the Back",
]


# ============================================================================
# CEDH-SPECIFIC COMBOS
# Card combinations that are hallmarks of competitive play. These are typically
# chosen for being mana-efficient, compact, and fast.
# ============================================================================
CEDH_COMBO_PIECES = {
    # Thoracle combos - the gold standard of cEDH wins
    "thoracle": ["Thassa's Oracle", "Demonic Consultation", "Tainted Pact"],
    
    # Breach lines
    "breach": ["Underworld Breach", "Brain Freeze", "Lion's Eye Diamond"],
    
    # Ad Naus
    "adnaus": ["Ad Nauseam", "Angel's Grace", "Sickening Dreams"],
    
    # Dramatic Scepter
    "dramatic": ["Isochron Scepter", "Dramatic Reversal"],
    
    # Dockside loops
    "dockside": ["Dockside Extortionist", "Temur Sabertooth", "Cloudstone Curio"],
    
    # Food Chain
    "foodchain": ["Food Chain", "Squee, the Immortal", "Eternal Scourge"],
    
    # Heliod combo
    "heliod": ["Heliod, Sun-Crowned", "Walking Ballista", "Triskelion"],
    
    # Razaketh lines
    "razaketh": ["Razaketh, the Foulblooded", "Life // Death", "Reanimate"],
    
    # Twin combo
    "twin": ["Kiki-Jiki, Mirror Breaker", "Splinter Twin", "Zealous Conscripts", "Felidar Guardian"],
    
    # Worldgorger
    "worldgorger": ["Worldgorger Dragon", "Animate Dead", "Dance of the Dead"],
}


# ============================================================================
# COMPETITIVE STAX/HATE PIECES
# Cards that primarily make sense in fast, competitive metas.
# ============================================================================
COMPETITIVE_STAX = [
    "Drannith Magistrate",
    "Opposition Agent",
    "Collector Ouphe",
    "Null Rod",
    "Cursed Totem",
    "Grafdigger's Cage",
    "Rule of Law",
    "Deafening Silence",
    "Archon of Emeria",
    "Aven Mindcensor",
    "Stranglehold",
    "Notion Thief",
    "Narset, Parter of Veils",
    "Lavinia, Azorius Renegade",
    "Linvala, Keeper of Silence",
    "Torpor Orb",
    "Hushwing Gryff",
    "Spirit of the Labyrinth",
    "Leonin Arbiter",
    "Thalia, Guardian of Thraben",
    "Grand Abolisher",
    "Silence",
    "Orim's Chant",
]


# ============================================================================
# TIERED TUTOR LISTS
# Instead of counting all tutors equally, we weight them by efficiency.
# Premium tutors in cEDH decks are much more impactful than slow tutors.
# ============================================================================
TUTORS_PREMIUM = [
    # 1-2 mana, finds any card or any card of a type, instant speed preferred
    "Demonic Tutor",
    "Vampiric Tutor",
    "Imperial Seal",
    "Mystical Tutor",
    "Enlightened Tutor",
    "Worldly Tutor",
    "Personal Tutor",
    "Gamble",
    "Summoner's Pact",
    "Merchant Scroll",
    "Muddle the Mixture",  # Transmute for 2 CMC
    "Shred Memory",  # Transmute for 2 CMC
    "Dimir Machinations",  # Transmute for 3 CMC
    "Dizzy Spell",  # Transmute for 1 CMC
]

TUTORS_EFFICIENT = [
    # Cheap but more limited, or slightly more expensive but powerful
    "Eladamri's Call",
    "Finale of Devastation",
    "Green Sun's Zenith",
    "Chord of Calling",
    "Eldritch Evolution",
    "Neoform",
    "Natural Order",
    "Birthing Pod",
    "Survival of the Fittest",
    "Fauna Shaman",
    "Crop Rotation",
    "Sylvan Tutor",
    "Wish",  # Various wish cards
    "Wishclaw Talisman",
    "Scheming Symmetry",
    "Diabolic Intent",
    "Grim Tutor",
    "Recruiter of the Guard",
    "Imperial Recruiter",
    "Ranger-Captain of Eos",
    "Ranger of Eos",
    "Spellseeker",
    "Tribute Mage",
    "Trophy Mage",
    "Trinket Mage",
    "Urza's Saga",
    "Inventors' Fair",
    "Tolaria West",  # Transmute for 0 CMC
    "Fabricate",
    "Whir of Invention",
    "Tezzeret the Seeker",
    "Steelshaper's Gift",
    "Open the Armory",
    "Idyllic Tutor",
    "Sterling Grove",
    "Academy Rector",
    "Arena Rector",
]

TUTORS_STANDARD = [
    # 3-4 mana, functional but not optimized
    "Diabolic Tutor",
    "Mastermind's Acquisition",
    "Praetor's Grasp",
    "Dark Petition",
    "Sidisi, Undead Vizier",
    "Rune-Scarred Demon",
    "Razaketh, the Foulblooded",
    "Solve the Equation",
    "Long-Term Plans",
    "Supply // Demand",
    "Drift of Phantasms",  # Transmute for 3 CMC
    "Dimir Infiltrator",  # Transmute for 2 CMC
    "Clutch of the Undercity",  # Transmute for 4 CMC
    "Plea for Guidance",
    "Beseech the Queen",
    "Final Parting",
    "Jarad's Orders",
    "Entomb",  # Graveyard tutor
    "Buried Alive",  # Graveyard tutor
    "Unmarked Grave",  # Graveyard tutor
]

TUTORS_SLOW = [
    # 5+ mana or very restricted
    "Diabolic Revelation",
    "Increasing Ambition",
    "Behold the Beyond",
    "Liliana Vess",
    "Tamiyo's Journal",
    "Planar Portal",
    "Planar Bridge",
    "Ring of Three Wishes",
    "Citanul Flute",
]


# ============================================================================
# HIGH-POWER STAPLES
# Cards that are very powerful but not necessarily cEDH-exclusive.
# Having many of these indicates a well-optimized deck.
# ============================================================================
HIGH_POWER_STAPLES = [
    # Card advantage engines
    "Rhystic Study",
    "Mystic Remora",
    "Necropotence",
    "Sylvan Library",
    "Esper Sentinel",
    "Dark Confidant",
    "Consecrated Sphinx",
    "The One Ring",
    "Orcish Bowmasters",
    
    # Efficient interaction
    "Cyclonic Rift",
    "Deadly Rollick",
    "Deflecting Swat",
    "Fierce Guardianship",
    "Force of Will",
    "Force of Negation",
    "Swan Song",
    "Delay",
    "Counterspell",
    "Mana Drain",
    "Dovin's Veto",
    "Swords to Plowshares",
    "Path to Exile",
    "Assassin's Trophy",
    "Abrupt Decay",
    "Nature's Claim",
    
    # Value creatures
    "Dockside Extortionist",
    "Smothering Tithe",
    "Dauthi Voidwalker",
    "Ragavan, Nimble Pilferer",
    "Thassa's Oracle",
    "Drannith Magistrate",
    "Opposition Agent",
    
    # Fast mana (also in FAST_MANA but worth double-tracking)
    "Mana Crypt",
    "Mox Diamond",
    "Chrome Mox",
    "Jeweled Lotus",
    
    # Powerful lands
    "Gaea's Cradle",
    "Serra's Sanctum",
    "Ancient Tomb",
    "Mishra's Workshop",
    "The Tabernacle at Pendrell Vale",
    "Bazaar of Baghdad",
    "Boseiju, Who Endures",
]

# Cards that allow multiple copies in Commander (singleton exception)
UNLIMITED_COPIES_CARDS = {
    # These cards have "A deck can have any number of cards named ~"
    "relentless rats",
    "rat colony", 
    "shadowborn apostle",
    "persistent petitioners",
    "dragon's approach",
    "slime against humanity",
    "hare apparent",
}

# Cards with specific copy limits (not singleton, but not unlimited)
LIMITED_COPIES_CARDS = {
    "seven dwarves": 7,
    "nazgûl": 9,
}

# Basic land names (unlimited copies allowed)
BASIC_LAND_NAMES = {
    "plains", "island", "swamp", "mountain", "forest", "wastes",
    "snow-covered plains", "snow-covered island", "snow-covered swamp",
    "snow-covered mountain", "snow-covered forest",
}

# ============================================================================
# SCORING WEIGHTS FOR BRACKET CALCULATION
# These control how much each factor contributes to bracket determination.
# ============================================================================
BRACKET_SCORING = {
    # Tutor weights (points per tutor)
    "tutor_premium_weight": 3.0,
    "tutor_efficient_weight": 2.0,
    "tutor_standard_weight": 1.0,
    "tutor_slow_weight": 0.5,
    
    # Tutor thresholds
    "tutor_bracket3_threshold": 6,   # 6+ tutor points = Bracket 3
    "tutor_bracket4_threshold": 12,  # 12+ tutor points = Bracket 4
    
    # Fast mana thresholds
    "fast_mana_bracket4_threshold": 4,  # 4+ fast mana = Bracket 4
    "fast_mana_cedh_threshold": 6,      # 6+ fast mana = cEDH signal
    
    # Free interaction thresholds
    "free_interaction_cedh_threshold": 3,  # 3+ free spells = cEDH signal
    
    # High power staple thresholds  
    "staples_bracket3_threshold": 5,   # 5+ staples = Bracket 3 signal
    "staples_bracket4_threshold": 10,  # 10+ staples = Bracket 4 signal
    
    # Combo thresholds (from Commander Spellbook)
    "combo_bracket3_tags": ["S", "PW", "O"],  # Spicy, Powerful, Oddball
    "combo_bracket4_tags": ["R"],              # Ruthless
    
    # cEDH signal threshold
    "cedh_signal_threshold": 12,  # 12+ cEDH signals = Bracket 5
    
    # Average CMC thresholds
    "avg_cmc_cedh": 2.0,       # Avg CMC < 2.0 is cEDH signal
    "avg_cmc_optimized": 2.5,  # Avg CMC < 2.5 is optimization signal
    
    # Land count thresholds
    "lands_cedh_max": 31,      # 31 or fewer lands = cEDH signal
    
    "jank_synergy_threshold": 40,  # Synergy score below this indicates jank deck
}