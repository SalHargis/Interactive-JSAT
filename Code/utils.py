# utils.py
import networkx as nx
import config

def calculate_metric(G, metric_name):
    """
    Core analytical engine for JSAT. Calculates structural and functional metrics
    based on Network Science and Cognitive Systems Engineering principles.
    """
    try:
        n = G.number_of_nodes()
        
        # --- Basic Graph Stats ---
        if metric_name == "Nodes": return str(n)
        if metric_name == "Edges": return str(G.number_of_edges())
        if n == 0: return "0"
        
        if metric_name == "Density": 
            return f"{nx.density(G):.3f}"
        
        if metric_name == "Avg Degree": 
            avg_deg = sum(d for _, d in G.degree()) / n
            return f"{avg_deg:.2f}"
        
        # --- Structural Complexity ---
        if metric_name == "Avg Cycle Length":
            try:
                cycles = list(nx.simple_cycles(G))
                if not cycles: return "0.0 (None)"
                lengths = [len(c) for c in cycles]
                return f"{(sum(lengths) / len(lengths)):.2f}"
            except: return "Err"
            
        if metric_name == "Cyclomatic Number":
            # Fundamental complexity: E - N + P
            e = G.number_of_edges()
            p = nx.number_weakly_connected_components(G)
            return str(e - n + p)

        if metric_name == "Total Cycles":
            # Count capped at 100 for performance on dense graphs
            count = 0
            for _ in nx.simple_cycles(G):
                count += 1
                if count > 100: return "100+"
            return str(count)

        # --- Resilience & Connectivity ---
        if metric_name == "Global Efficiency":
            # System integration (potential for information flow)
            eff = nx.global_efficiency(G.to_undirected())
            return f"{eff:.3f}"

        if metric_name == "Modularity":
            # Structural coupling (Q-Score)
            communities = nx.community.greedy_modularity_communities(G.to_undirected())
            q_score = nx.community.modularity(G.to_undirected(), communities)
            return f"Q={q_score:.2f} ({len(communities)} Grps)"

        if metric_name == "Brittleness Ratio":
            # Balance of Soft (Supportive) vs. Hard (Essential) interdependencies
            soft = sum(1 for u, v, d in G.edges(data=True) if d.get('type') == config.EDGE_TYPE_SOFT)
            hard = sum(1 for u, v, d in G.edges(data=True) if d.get('type') == config.EDGE_TYPE_HARD)
            if hard == 0: return "Inf (No Hard Edges)"
            return f"{(soft / hard):.2f} (S:{soft}/H:{hard})"

        if metric_name == "Supportive Gain":
            # Measures efficiency loss if soft/assistive links are removed
            eff_total = nx.global_efficiency(G.to_undirected())
            hard_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('type') == config.EDGE_TYPE_HARD]
            G_hard = nx.Graph()
            G_hard.add_nodes_from(G.nodes())
            G_hard.add_edges_from(hard_edges)
            eff_hard = nx.global_efficiency(G_hard)
            return f"{(eff_total - eff_hard):.3f} (Tot: {eff_total:.2f})"

        if metric_name == "Critical Vulnerability":
            # Checks if the essential 'Hard' skeleton remains connected
            hard_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('type') == config.EDGE_TYPE_HARD]
            G_hard = nx.DiGraph()
            G_hard.add_nodes_from(G.nodes())
            G_hard.add_edges_from(hard_edges)
            num_comps = nx.number_weakly_connected_components(G_hard)
            return "Robust (1 Comp)" if num_comps == 1 else f"Fractured ({num_comps} Comps)"

        # --- Shared Authority & Coordination ---
        if metric_name == "Interdependence":
            # Ratio of edges crossing agent boundaries
            m = G.number_of_edges()
            if m == 0: return "0.000"
            cross = 0
            for u, v in G.edges():
                if G.nodes[u].get('agent') != G.nodes[v].get('agent'):
                    cross += 1
            return f"{(cross / m):.3f}"

        if metric_name == "Functional Redundancy":
            # Average number of agents assigned per Function (backup capacity)
            total_agents, func_count = 0, 0
            for n, d in G.nodes(data=True):
                if d.get('type') == 'Function':
                    ag = d.get('agent', [])
                    real_agents = [x for x in (ag if isinstance(ag, list) else [ag]) if x != "Unassigned"]
                    total_agents += len(real_agents)
                    func_count += 1
            if func_count == 0: return "0.0"
            return f"{(total_agents / func_count):.2f}"

        if metric_name == "Agent Criticality":
            # Identifies the agent with the most 'Sole Authority' functions
            sole_counts = {}
            for n, d in G.nodes(data=True):
                if d.get('type') == 'Function':
                    ag = d.get('agent', [])
                    real = [x for x in (ag if isinstance(ag, list) else [ag]) if x != "Unassigned"]
                    if len(real) == 1:
                        sole_counts[real[0]] = sole_counts.get(real[0], 0) + 1
            if not sole_counts: return "None (Robust)"
            worst = max(sole_counts, key=sole_counts.get)
            return f"{worst} ({sole_counts[worst]} Sole)"
        
        if metric_name == "Collaboration Ratio":
            # Percent of functions involving joint activity (multiple agents)
            shared, total = 0, 0
            for n, d in G.nodes(data=True):
                if d.get('type') == 'Function':
                    ag = d.get('agent', [])
                    real = [x for x in (ag if isinstance(ag, list) else [ag]) if x != "Unassigned"]
                    if real:
                        total += 1
                        if len(real) > 1: shared += 1
            if total == 0: return "0.0%"
            return f"{((shared / total) * 100):.1f}%"
            
    except Exception as e:
        print(f"Error calculating {metric_name}: {e}")
        return "Err"
    
    return ""