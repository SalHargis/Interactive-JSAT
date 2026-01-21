# utils.py
# Handles the "Heavy Lifting" math. This is where your metric calculations live. 
# If you want to add a new metric, you add it here.

import networkx as nx

def calculate_metric(G, metric_name):
    """
    Calculates a specific network metric for a given graph G.
    Returns a string representation of the result or 'Err'.
    """
    try:
        n = G.number_of_nodes()
        
        if metric_name == "Nodes": 
            return n
        
        if metric_name == "Edges": 
            return G.number_of_edges()
        
        if n == 0: 
            return "0"
        
        if metric_name == "Density": 
            return f"{nx.density(G):.3f}"
        
        if metric_name == "Avg Degree": 
            avg_deg = sum([d for _, d in G.degree()]) / n
            return f"{avg_deg:.2f}"
        
        if metric_name == "Avg Clustering": 
            avg_clust = nx.average_clustering(G.to_undirected())
            return f"{avg_clust:.3f}"
        
        if metric_name == "Reciprocity":
            # Measures how many edges immediately point to each other
            # 0.0 = Pure Hierarchy, 1.0 = All feedback
            return f"{nx.reciprocity(G):.3f}"
        
        if metric_name == "Interdependence":
            # Measures the % of edges that cross agent boundaries.
            # 0.0 = Silos (Independent), 1.0 = High Coupling (Interdependent)
            try:
                m = G.number_of_edges()
                if m == 0: return "0.000"
                
                cross_boundary_edges = 0
                for u, v in G.edges():
                    # Safely get agents, defaulting to 'Unassigned' if missing
                    agent_u = G.nodes[u].get('agent', 'Unassigned')
                    agent_v = G.nodes[v].get('agent', 'Unassigned')
                    
                    # If they are different, that's a dependency
                    if agent_u != agent_v:
                        cross_boundary_edges += 1
                        
                return f"{(cross_boundary_edges / m):.3f}"
                
            except Exception as e:
                print(f"Interdependence Error: {e}")
                return "Err"
            
        if metric_name == "Cyclomatic Number":
            # Formula: E - N + P (where P is connected components)
            # This measures the number of independent loops.
            # Low = more linear flows, High = more interdependent/tangled 
            try:
                e = G.number_of_edges()
                n = G.number_of_nodes()
                p = nx.number_weakly_connected_components(G)
                return str(e - n + p)
            except:
                return "Err"

        if metric_name == "Critical Loop Nodes":
            # Returns the size of the Feedback Vertex Set.
            # These are the nodes that, if removed, kill all cycles.
            # Low = tighter cycles, High = larger cycles
            try:
                # We use the approximation algorithm
                fvs = nx.approximation.min_weighted_feedback_vertex_set(G)
                return str(len(fvs))
            except:
                return "0"

        if metric_name == "Total Cycles":
            # Raw count of all elementary cycles.
            # This can be huge (exponential) for dense graphs.
            # Capped at 100 just to limit computations
            try:
                count = 0
                for _ in nx.simple_cycles(G):
                    count += 1
                    if count > 100:
                        return "100+"
                return str(count)
            except:
                return "Err"
            
    except Exception as e:
        print(f"Error calculating {metric_name}: {e}")
        return "Err"
    
    return ""