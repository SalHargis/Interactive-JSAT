import networkx as nx
import random

def get_cycle_highlights(G):
    """
    Identifies all simple cycles and assigns a distinct neon color to each.
    Returns a list of dictionaries containing node/edge sets and colors.
    """
    try:
        cycles = list(nx.simple_cycles(G))
    except ImportError:
        return []

    highlights = []
    # A palette of high-contrast "neon" colors for the glow effect
    neon_colors = [
        "#FF1493", # DeepPink
        "#00FF00", # Lime
        "#00FFFF", # Cyan
        "#FFD700", # Gold
        "#FF4500", # OrangeRed
        "#9400D3", # DarkViolet
        "#32CD32", # LimeGreen
        "#1E90FF", # DodgerBlue
    ]

    for i, path in enumerate(cycles):
        color = neon_colors[i % len(neon_colors)]
        
        # Build the edge list for this specific cycle
        cycle_edges = []
        for j in range(len(path)):
            u = path[j]
            v = path[(j + 1) % len(path)] # Connect last node back to first
            cycle_edges.append((u, v))
            
        highlights.append({
            "nodes": path,
            "edges": cycle_edges,
            "color": color,
            "width": 8 # Offset width slightly so overlapping cycles are visible
        })
        
    return highlights

# metric_visualizations.py (formerly visual_analytics.py)
import networkx as nx

def get_single_cycle_highlight(G, cycle_index):
    """
    Highlights ONLY the cycle at the specified index, using a distinct color.
    """
    try:
        cycles = list(nx.simple_cycles(G))
        
        if cycle_index < 0 or cycle_index >= len(cycles):
            return [] 
            
        path = cycles[cycle_index]
        
        # Same palette as 'get_cycle_highlights' for consistency
        neon_colors = [
            "#FF1493", # DeepPink
            "#00C000", # Darker Lime (Readable on white)
            "#DE52D0", # 
            "#FFD700", # Gold
            "#FF4500", # OrangeRed
            "#9400D3", # DarkViolet
            "#32CD32", # LimeGreen
            "#060C12", # DodgerBlue
        ]
        
        # Pick color based on index so it matches the button
        color = neon_colors[cycle_index % len(neon_colors)]
        
        cycle_edges = []
        for j in range(len(path)):
            u = path[j]
            v = path[(j + 1) % len(path)]
            cycle_edges.append((u, v))
            
        return [{
            "nodes": path,
            "edges": cycle_edges,
            "color": color, 
            "width": 10
        }]
        
    except Exception as e:
        print(f"Error highlighting cycle {cycle_index}: {e}")
        return []

def get_interdependence_highlights(G):
    """
    Identifies edges that cross agent boundaries (the drivers of interdependence).
    """
    cross_edges = []
    involved_nodes = set()
    
    for u, v in G.edges():
        agent_u = G.nodes[u].get('agent', 'Unassigned')
        agent_v = G.nodes[v].get('agent', 'Unassigned')
        
        if agent_u != agent_v:
            cross_edges.append((u, v))
            involved_nodes.add(u)
            involved_nodes.add(v)
            
    if not cross_edges:
        return []

    return [{
        "nodes": list(involved_nodes),
        "edges": cross_edges,
        "color": "#FF0000", # Bright Red for critical dependencies
        "width": 8
    }]