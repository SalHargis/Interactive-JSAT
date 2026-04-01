# metric_visualizations.py
import networkx as nx
import random

def get_cycle_highlights(G):
    """
    Identifies all simple cycles and assigns a distinct neon color to each.
    Useful for visualizing feedback loops and potential resonance in the system.
    """
    try:
        cycles = list(nx.simple_cycles(G))
    except (ImportError, AttributeError):
        return []

    highlights = []
    # High-contrast palette for visual clarity against white canvas
    neon_colors = [
        "#FF1493", "#00FF00", "#00FFFF", "#FFD700", 
        "#FF4500", "#9400D3", "#32CD32", "#1E90FF"
    ]

    for i, path in enumerate(cycles):
        color = neon_colors[i % len(neon_colors)]
        
        cycle_edges = []
        for j in range(len(path)):
            u = path[j]
            v = path[(j + 1) % len(path)]
            cycle_edges.append((u, v))
            
        highlights.append({
            "nodes": path,
            "edges": cycle_edges,
            "color": color,
            "width": 8 
        })
        
    return highlights

def get_single_cycle_highlight(G, cycle_index):
    """Highlights a specific cycle by index from the simple_cycles list."""
    try:
        cycles = list(nx.simple_cycles(G))
        if cycle_index < 0 or cycle_index >= len(cycles):
            return [] 
            
        path = cycles[cycle_index]
        neon_colors = [
            "#FF1493", "#00C000", "#DE52D0", "#FFD700", 
            "#FF4500", "#9400D3", "#32CD32", "#060C12"
        ]
        
        color = neon_colors[cycle_index % len(neon_colors)]
        cycle_edges = [(path[j], path[(j + 1) % len(path)]) for j in range(len(path))]
            
        return [{
            "nodes": path,
            "edges": cycle_edges,
            "color": color, 
            "width": 10
        }]
    except Exception as e:
        print(f"Cycle Viz Error: {e}")
        return []

def get_interdependence_highlights(G):
    """
    Identifies 'Cross-Agent' edges that drive system interdependence.
    Highlights connections where Source and Target agents differ.
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
        "color": "#FF0000", 
        "width": 8
    }]

def get_modularity_highlights(G):
    """
    Detects communities using greedy modularity and assigns unique colors.
    Visualizes tightly coupled functional groups within the broader network.
    """
    try:
        communities = nx.community.greedy_modularity_communities(G.to_undirected())
        highlights = []
        community_colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", 
            "#98D8C8", "#F7DC6F", "#BB8FCE", "#B2BABB"
        ]

        for i, community_set in enumerate(communities):
            color = community_colors[i % len(community_colors)]
            nodes_list = list(community_set)
            
            intra_edges = [
                (u, v) for u in nodes_list for v in nodes_list if G.has_edge(u, v)
            ]
            
            highlights.append({
                "nodes": nodes_list,
                "edges": intra_edges,
                "color": color,
                "width": 10 
            })
        return highlights
    except Exception as e:
        print(f"Modularity Viz Error: {e}")
        return []
    
def get_single_modularity_highlight(G, group_index):
    """Highlights a specific community detected via modularity analysis."""
    try:
        communities = list(nx.community.greedy_modularity_communities(G.to_undirected()))
        communities.sort(key=len, reverse=True)
        
        if group_index < 0 or group_index >= len(communities):
            return []
            
        target_group = list(communities[group_index])
        community_colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", 
            "#98D8C8", "#F7DC6F", "#BB8FCE", "#B2BABB"
        ]
        color = community_colors[group_index % len(community_colors)]
        
        intra_edges = [
            (u, v) for u in target_group for v in target_group if G.has_edge(u, v)
        ]
                    
        return [{
            "nodes": target_group,
            "edges": intra_edges,
            "color": color,
            "width": 10
        }]
    except Exception as e:
        print(f"Modularity Single Error: {e}")
        return []