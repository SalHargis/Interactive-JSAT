# utils.py
import networkx as nx
import config

def calculate_metric(G, metric_name):
    """
    Calculates metrics. Includes:
    Originals: Density, Clustering, Cycles, Interdependence, etc.
    New: Global Efficiency, Modularity.
    """
    try:
        n = G.number_of_nodes()
        
        # --- ORIGINAL METRICS ---
        if metric_name == "Nodes": return str(n)
        if metric_name == "Edges": return str(G.number_of_edges())
        if n == 0: return "0"
        
        if metric_name == "Density": 
            return f"{nx.density(G):.3f}"
        
        if metric_name == "Avg Degree": 
            avg_deg = sum([d for _, d in G.degree()]) / n
            return f"{avg_deg:.2f}"
        
        if metric_name == "Avg Clustering": 
            avg_clust = nx.average_clustering(G.to_undirected())
            return f"{avg_clust:.3f}"
        
        if metric_name == "Avg Cycle Length":
            try:
                cycles = list(nx.simple_cycles(G))
                if not cycles: return "0.0 (None)"
                lengths = [len(c) for c in cycles]
                avg = sum(lengths) / len(lengths)
                return f"{avg:.2f} {lengths}"
            except: return "Err"
        
        if metric_name == "Interdependence":
            try:
                m = G.number_of_edges()
                if m == 0: return "0.000"
                cross_boundary_edges = 0
                for u, v in G.edges():
                    agent_u = G.nodes[u].get('agent', 'Unassigned')
                    agent_v = G.nodes[v].get('agent', 'Unassigned')
                    if agent_u != agent_v: cross_boundary_edges += 1
                return f"{(cross_boundary_edges / m):.3f}"
            except: return "Err"
            
        if metric_name == "Cyclomatic Number":
            try:
                e = G.number_of_edges()
                p = nx.number_weakly_connected_components(G)
                return str(e - n + p)
            except: return "Err"

        if metric_name == "Critical Loop Nodes":
            try:
                fvs = nx.approximation.min_weighted_feedback_vertex_set(G)
                return str(len(fvs))
            except: return "0"

        if metric_name == "Total Cycles":
            try:
                count = 0
                for _ in nx.simple_cycles(G):
                    count += 1
                    if count > 100: return "100+"
                return str(count)
            except: return "Err"

        # --- NEW METRICS ONLY ---

        if metric_name == "Global Efficiency":
            # Measures how integrated the system is (0.0 to 1.0)
            try:
                # Treated as undirected to measure potential for information flow
                eff = nx.global_efficiency(G.to_undirected())
                return f"{eff:.3f}"
            except: return "Err"

        if metric_name == "Modularity":
            # Detects if system splits into distinct groups (Q-Score)
            try:
                communities = nx.community.greedy_modularity_communities(G.to_undirected())
                num_communities = len(communities)
                q_score = nx.community.modularity(G.to_undirected(), communities)
                return f"Q={q_score:.2f} ({num_communities} Grps)"
            except: return "Err"

        if metric_name == "Brittleness Ratio":
            # A. Brittleness: Ratio of Soft to Hard edges
            soft = sum(1 for u, v, d in G.edges(data=True) if d.get('type') == config.EDGE_TYPE_SOFT)
            hard = sum(1 for u, v, d in G.edges(data=True) if d.get('type') == config.EDGE_TYPE_HARD)
            
            if hard == 0: return "Infinite (No Hard Edges)"
            ratio = soft / hard
            return f"{ratio:.2f} (S:{soft}/H:{hard})"

        if metric_name == "Supportive Gain":
            # B. Supportive Gain: Efficiency(Total) - Efficiency(HardOnly)
            # Measures how much integration is lost if soft edges fail.
            
            # 1. Total Efficiency
            eff_total = nx.global_efficiency(G.to_undirected())
            
            # 2. Hard-Only Efficiency
            hard_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('type') == config.EDGE_TYPE_HARD]
            G_hard = nx.Graph()
            G_hard.add_nodes_from(G.nodes())
            G_hard.add_edges_from(hard_edges)
            eff_hard = nx.global_efficiency(G_hard)
            
            gain = eff_total - eff_hard
            return f"{gain:.3f} (Tot: {eff_total:.2f})"

        if metric_name == "Critical Vulnerability":
            # C. Critical Path Vulnerability: 
            # Does the graph shatter if soft edges are removed?
            # Measures Connected Components of the Hard-Only graph.
            
            hard_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('type') == config.EDGE_TYPE_HARD]
            G_hard = nx.DiGraph() # Use Directed to catch strict flow breaks
            G_hard.add_nodes_from(G.nodes())
            G_hard.add_edges_from(hard_edges)
            
            # Weakly connected components (islands of connectivity)
            num_components = nx.number_weakly_connected_components(G_hard)
            
            if num_components == 1:
                return "Robust (1 Comp)"
            else:
                return f"Fractured ({num_components} Comps)"
            
    except Exception as e:
        print(f"Error calculating {metric_name}: {e}")
        return "Err"
    
    return ""