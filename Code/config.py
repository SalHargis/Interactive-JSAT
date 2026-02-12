# config.py
# Stores all your "Magic Numbers" and settings.

# --- Graph Settings ---
NODE_RADIUS = 20
HISTORY_LIMIT = 40

# --- Default Agents ---
DEFAULT_AGENTS = {"Unassigned": "white"}
DEFAULT_CURRENT_AGENT = "Unassigned"

# --- View Modes ---
VIEW_MODE_FREE = "FREE"
VIEW_MODE_JSAT = "JSAT"

# --- JSAT Layer Definitions ---
# Defines the Y-coordinate for each layer
JSAT_LAYERS = {
    "Synchrony": 100,               # Matches JSON "SynchronyFunction"
    "Coordination Grounding": 250,
    "Distributed Work": 400,
    "Base Environment": 550
}

# Defines the order in which they appear (Top to Bottom)
LAYER_ORDER = [
    "Synchrony",                    # Matches JSON "SynchronyFunction"
    "Coordination Grounding", 
    "Distributed Work", 
    "Base Environment"
]

# --- Edge Types ---
EDGE_TYPE_HARD = "hard"
EDGE_TYPE_SOFT = "soft"

# --- Visual Styles ---
HARD_EDGE_COLOR = "black"
SOFT_EDGE_COLOR = "#999999" # grey
HARD_EDGE_WIDTH = 2
SOFT_EDGE_WIDTH = 2
SOFT_EDGE_DASH = (4, 4) # Dashed line pattern