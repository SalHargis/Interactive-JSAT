# config.py
# Core configuration and visual constants for the JSAT environment

# --- Graph Geometry & History ---
NODE_RADIUS = 20
HISTORY_LIMIT = 40

# --- Agent Defaults ---
DEFAULT_AGENTS = {"Unassigned": "white"}
DEFAULT_CURRENT_AGENT = "Unassigned"

# --- Viewport Modes ---
VIEW_MODE_FREE = "FREE"
VIEW_MODE_JSAT = "JSAT"

# --- JSAT Layer Definitions ---
# Y-coordinates define the horizontal "shelves" in JSAT view mode
JSAT_LAYERS = {
    "Synchrony": 100,
    "Coordination Grounding": 250,
    "Distributed Work": 400,
    "Base Environment": 550
}

# Vertical ordering (Top to Bottom)
LAYER_ORDER = [
    "Synchrony",                    
    "Coordination Grounding", 
    "Distributed Work", 
    "Base Environment"
]

# --- Edge Logic & Styling ---
EDGE_TYPE_HARD = "hard"
EDGE_TYPE_SOFT = "soft"

HARD_EDGE_COLOR = "black"
SOFT_EDGE_COLOR = "#999999"  # Grey for supportive links
HARD_EDGE_WIDTH = 2
SOFT_EDGE_WIDTH = 2
SOFT_EDGE_DASH = (4, 4)      # Visual distinction for soft constraints