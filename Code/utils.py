# utils.py
import networkx as nx
import config

def calculate_metric(G, metric_name):
    """
    Calculates metrics. Includes:
    Originals: Density, Clustering, Cycles, Interdependence, etc
    """
    try:
        n = G.number_of_nodes()
        
        if metric_name == "Nodes": return str(n)
        if metric_name == "Edges": return str(G.number_of_edges())
        if n == 0: return "0"
        
        if metric_name == "Density": 
            return f"{nx.density(G):.3f}"
        
        if metric_name == "Avg Degree": 
            avg_deg = sum([d for _, d in G.degree()]) / n
            return f"{avg_deg:.2f}"
        
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

        if metric_name == "Brittleness Ratio": # This isn't a great name, will rename the button
            # A. Ratio of Soft to Hard edges
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
            
            # 2. Hard-edges Only Efficiency
            hard_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('type') == config.EDGE_TYPE_HARD]
            G_hard = nx.Graph()
            G_hard.add_nodes_from(G.nodes())
            G_hard.add_edges_from(hard_edges)
            eff_hard = nx.global_efficiency(G_hard)
            
            gain = eff_total - eff_hard
            return f"{gain:.3f} (Tot: {eff_total:.2f})"

        if metric_name == "Critical Vulnerability":
            # C. Critical Path Vulnerability: 
            # Does the graph fragment if soft edges are removed?
            # Measures Connected Components of the Hard-Only graph.
            
            hard_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('type') == config.EDGE_TYPE_HARD]
            G_hard = nx.DiGraph() # di-graph to catch strict flow breaks
            G_hard.add_nodes_from(G.nodes())
            G_hard.add_edges_from(hard_edges)
            
            # Weakly connected components (islands of connectivity)
            num_components = nx.number_weakly_connected_components(G_hard)
            
            if num_components == 1:
                return "Robust (1 Comp)"
            else:
                return f"Fractured ({num_components} Comps)"
            
        ### Metric Ideas for analyzing SHared Authority

        if metric_name == "Functional Redundancy":
            # "Average number of agents" capable of performing a function.
            # Idea: 1.0 = Brittle (No backup), >1.2 = Resilient (more backups)
            total_agents = 0
            func_count = 0
            for n, d in G.nodes(data=True):
                if d.get('type') == 'Function':
                    # Get list of agents, handling single strings if necessary
                    ag = d.get('agent', [])
                    if not isinstance(ag, list): ag = [ag]
                    
                    # Count real agents (exclude "Unassigned")
                    real_agents = [x for x in ag if x != "Unassigned"]
                    total_agents += len(real_agents)
                    func_count += 1
            
            if func_count == 0: return "0.0"
            avg = total_agents / func_count
            return f"{avg:.2f} (Avg Agents)"

        if metric_name == "Agent Criticality":
            # try to find the agent with the most "authority" in the system
            # for the most functions? (If they disconnect, these functions fail)
            agent_sole_counts = {}
            
            for n, d in G.nodes(data=True):
                if d.get('type') == 'Function':
                    ag = d.get('agent', [])
                    if not isinstance(ag, list): ag = [ag]
                    real_agents = [x for x in ag if x != "Unassigned"]
                    
                    # If exactly one agent owns this, they are critical to it
                    if len(real_agents) == 1:
                        sole_agent = real_agents[0]
                        agent_sole_counts[sole_agent] = agent_sole_counts.get(sole_agent, 0) + 1
            
            if not agent_sole_counts: 
                return "None (Robust)"
            
            # Find the agent with the highest count
            worst_agent = max(agent_sole_counts, key=agent_sole_counts.get)
            count = agent_sole_counts[worst_agent]
            return f"{worst_agent} ({count} Sole Tasks)"
        
        if metric_name == "Collaboration Ratio":
            # Percent of functions that involve multiple agents
            shared_funcs = 0
            total_funcs = 0
            for n, d in G.nodes(data=True):
                if d.get('type') == 'Function':
                    ag = d.get('agent', [])
                    if not isinstance(ag, list): ag = [ag]
                    
                    # Filter out 'Unassigned' (only count other agents)
                    real_agents = [x for x in ag if x != "Unassigned"]
                    
                    if len(real_agents) > 0:
                        total_funcs += 1
                        # if more than 1 agent is assigned then it's a collaborative task
                        if len(real_agents) > 1:
                            shared_funcs += 1
            
            if total_funcs == 0: return "0.0%"
            ratio = (shared_funcs / total_funcs) * 100
            return f"{ratio:.1f}%"
            
    except Exception as e:
        print(f"Error calculating {metric_name}: {e}")
        return "Err"
    
    return ""