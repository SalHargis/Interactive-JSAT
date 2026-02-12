# metric_visualizations.py
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
# metric_visualizations.py

def get_modularity_highlights(G):
    """
    Detects communities and assigns a unique color to each group.
    Colors nodes and 'intra-community' edges (edges within the same group).
    """
    try:
        # 1. Detect Communities
        # Returns a list of sets: [{n1, n2}, {n3, n4}...]
        communities = nx.community.greedy_modularity_communities(G.to_undirected())
        
        highlights = []
        
        # 2. Define Palette
        community_colors = [
            "#FF6B6B", # Red
            "#4ECDC4", # Teal
            "#45B7D1", # Blue
            "#FFA07A", # Light Salmon
            "#98D8C8", # Pale Green
            "#F7DC6F", # Yellow
            "#BB8FCE", # Purple
            "#B2BABB", # Gray
        ]

        for i, community_set in enumerate(communities):
            color = community_colors[i % len(community_colors)]
            nodes_list = list(community_set)
            
            # Find edges that stay COMPLETELY within this community
            intra_edges = []
            for u in nodes_list:
                for v in nodes_list:
                    if G.has_edge(u, v):
                        intra_edges.append((u, v))
            
            # Create Highlight Group
            highlights.append({
                "nodes": nodes_list,
                "edges": intra_edges,
                "color": color,
                "width": 10 # Thick highlight for groups
            })
            
        return highlights

    except Exception as e:
        print(f"Modularity Vis Error: {e}")
        return []
    
def get_single_modularity_highlight(G, group_index):
    """
    Highlights ONLY the specific community group at the given index.
    """
    try:
        # 1. Detect Communities (Must use same method as the main visualizer)
        communities = list(nx.community.greedy_modularity_communities(G.to_undirected()))
        
        # Sort by size (largest first) to keep UI consistent
        communities.sort(key=len, reverse=True)
        
        if group_index < 0 or group_index >= len(communities):
            return []
            
        target_group = list(communities[group_index])
        
        # 2. Match Colors (Use same palette as full view for consistency)
        community_colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", 
            "#98D8C8", "#F7DC6F", "#BB8FCE", "#B2BABB"
        ]
        color = community_colors[group_index % len(community_colors)]
        
        # 3. Find edges within this group
        intra_edges = []
        for u in target_group:
            for v in target_group:
                if G.has_edge(u, v):
                    intra_edges.append((u, v))
                    
        return [{
            "nodes": target_group,
            "edges": intra_edges,
            "color": color,
            "width": 10
        }]

    except Exception as e:
        print(f"Modularity Single Error: {e}")
        return []