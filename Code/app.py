import tkinter as tk
from tkinter import simpledialog, messagebox, Toplevel, filedialog, ttk
import networkx as nx
import math
import json
import random
from PIL import ImageGrab

# external modules / files from project
import config
from utils import calculate_metric
from components import InteractiveComparisonPanel, CreateToolTip
import metric_visualizations

# descriptions of metrics (hover-over-able)
METRIC_DESCRIPTIONS = {
    "Density": "The ratio of actual connections to potential connections.\nHigh density = highly connected.",
    "Cyclomatic Number": "The number of fundamental independent loops.\nMeasures the structural complexity of feedback.",
    "Global Efficiency": "A measure (0.0 - 1.0) of how easily information flows across the network.\nHigher is better for connectivity.",
    "Supportive Gain": "The amount of efficiency provided specifically by 'Soft' edges.\nHigh gain = Critical reliance on soft interdependencies.",
    "Brittleness Ratio": "The balance of Supportive (Soft) vs. Essential (Hard) edges.\nLow soft count may indicate a brittle, rigid system.",
    "Critical Vulnerability": "Checks if the 'Hard' skeleton of the graph is connected.\n'Fractured' means the system breaks if soft links fail.",
    "Interdependence": "The percentage of edges that cross between different agents.\nHigh interdependence = High requirement for collaboration.",
    "Total Cycles": "The total count of all feedback loops in the system.\nIndicates potential for recirculation or resonance.",
    "Avg Cycle Length": "The average number of steps in a feedback loop.\nLong loops = delayed feedback.",
    "Modularity": "How well the system divides into distinct, isolated groups (modules).\nHigh modularity = Low coupling between groups.",
    "Functional Redundancy": "The average number of agents assigned to each function.\n>1.0 implies backup capacity exists.",
    "Agent Criticality": "The agent with the most sole-authority tasks.\nLoss of this agent may cause most disruption.",
    "Collaboration Ratio": "The percentage of functions that have shared authority.\nCould be a measure of system flexibility."
}

class GraphBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Interactive JSAT")
        self.root.geometry("1400x900")
        
        # Backend Data 
        self.G = nx.DiGraph()
        self.saved_archs = {} 
        self.undo_stack = []
        self.redo_stack = []
        
        # State 
        self.selected_node = None     
        self.inspected_node = None    
        self.drag_node = None       
        self.drag_start_pos = None 
        self.is_dragging = False   
        self.pre_drag_graph_state = None
        self.sidebar_drag_data = None
        self.current_highlights = [] 
        self.active_vis_mode = None
        self.is_sidebar_dragging = False

        # View Settings
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_start = None 
        
        # Mode Settings
        self.mode = "SELECT"
        self.mode_buttons = {}
        self.view_mode = config.VIEW_MODE_FREE
        self.edge_view_mode = "ALL"
        
        self.agents = config.DEFAULT_AGENTS.copy()
        
        self.setup_ui()
        
    def setup_ui(self):
        # Toolbar
        toolbar_frame = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        self.build_toolbar(toolbar_frame)

        # Main Layout
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        # 1. Dashboard (Right Side)
        self.dashboard_frame = tk.Frame(main_container, width=350, bg="#f0f0f0", bd=1, relief=tk.SUNKEN)
        self.dashboard_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.dashboard_frame.pack_propagate(False)

        # 2. Canvas (Left Side)
        self.canvas = tk.Canvas(main_container, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Canvas Bindings
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        # Right Click Binding (Mac uses Button-2, Windows/Linux Button-3)
        self.canvas.bind("<Button-3>", self.on_right_click) 
        self.canvas.bind("<Button-2>", self.on_right_click) # For some MacOS configs
        
        # Zooming
        self.canvas.bind("<MouseWheel>", self.on_zoom)      
        self.canvas.bind("<Button-4>", lambda e: self.on_zoom(e, 1))  
        self.canvas.bind("<Button-5>", lambda e: self.on_zoom(e, -1)) 

        # 3. Dashboard Content
        self._setup_dashboard_structure()

        # Footer Status
        self.status_label = tk.Label(self.root, text="Mode: Select & Inspect", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.redraw()

    def _setup_dashboard_structure(self):
        """Initializes static dashboard containers."""
        tk.Label(self.dashboard_frame, text="Network Dashboard", font=("Arial", 14, "bold"), 
                 bg="#4a4a4a", fg="white", pady=8).pack(fill=tk.X)
        
        self.inspector_frame = tk.Frame(self.dashboard_frame, bg="#fff8e1", bd=2, relief=tk.GROOVE)
        self.inspector_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Scrollable Area
        self.scroll_canvas = tk.Canvas(self.dashboard_frame, bg="#f0f0f0")
        self.scrollbar = tk.Scrollbar(self.dashboard_frame, orient="vertical", command=self.scroll_canvas.yview)
        self.scrollable_content = tk.Frame(self.scroll_canvas, bg="#f0f0f0")

        self.scroll_canvas.create_window((0, 0), window=self.scrollable_content, anchor="nw", width=330)
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrollable_content.bind("<Configure>", lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))

    # Coordinate Transforms

    def to_screen(self, wx, wy):
        return (wx * self.zoom) + self.offset_x, (wy * self.zoom) + self.offset_y

    def to_world(self, sx, sy):
        return (sx - self.offset_x) / self.zoom, (sy - self.offset_y) / self.zoom

    def get_draw_pos(self, node_id):
        """Calculates WORLD coordinates based on current view mode."""
        data = self.G.nodes[node_id]
        raw_x, raw_y = data.get('pos', (100, 100))
        
        # If dragging in JSAT mode, show raw position until dropped
        if self.view_mode == config.VIEW_MODE_JSAT and self.drag_node == node_id and self.is_dragging:
            return raw_x, raw_y
        
        if self.view_mode == config.VIEW_MODE_FREE:
            return raw_x, raw_y
            
        # JSAT Mode: Snap Y to layer
        layer = self.get_node_layer(data)
        return raw_x, config.JSAT_LAYERS[layer]

    def get_node_layer(self, data):
        if 'layer' in data and data['layer'] in config.JSAT_LAYERS:
            return data['layer']
        return "Base Environment" if data.get('type') == "Resource" else "Distributed Work"

    # Interaction Logic

    def on_zoom(self, event, direction=None):
        factor = 1.1 if (direction or event.delta) > 0 else 0.9
        self.zoom *= factor
        self.redraw()

    def on_mouse_down(self, event):
        # 1. Check for Node Click
        clicked_node = self._get_node_at(event.x, event.y)
        
        if clicked_node is not None:
            self._handle_node_press(clicked_node, event)
        else:
            self._handle_background_press(event)

    def _handle_node_press(self, node_id, event):
        self.pre_drag_graph_state = self.G.copy()
        self.drag_node = node_id
        self.drag_start_pos = (event.x, event.y)
        self.is_dragging = False

    def _handle_background_press(self, event):
        if self.mode == "DELETE":
            clicked_edge = self.find_edge_at(event.x, event.y)
            if clicked_edge:
                self.save_state()
                self.G.remove_edge(*clicked_edge)
                self.redraw()
                return

        # Prepare for Pan or Add
        self.inspected_node = None
        self.pan_start = (event.x, event.y)
        self.is_dragging = False
        self.redraw()

    def on_mouse_drag(self, event):
        if self.drag_node is not None:
            if not self.is_dragging and math.hypot(event.x - self.drag_start_pos[0], event.y - self.drag_start_pos[1]) > 5:
                self.is_dragging = True
            
            if self.is_dragging:
                wx, wy = self.to_world(event.x, event.y)
                self.G.nodes[self.drag_node]['pos'] = (wx, wy)
                self.redraw()

        elif self.pan_start is not None:
            if not self.is_dragging and math.hypot(event.x - self.pan_start[0], event.y - self.pan_start[1]) > 5:
                self.is_dragging = True
            
            if self.is_dragging:
                dx, dy = event.x - self.pan_start[0], event.y - self.pan_start[1]
                self.offset_x += dx
                self.offset_y += dy
                self.pan_start = (event.x, event.y)
                self.redraw()

    def on_mouse_up(self, event):
        if self.drag_node is not None:
            if self.is_dragging: 
                self._finalize_drag(event)
            else: 
                self.handle_click(self.drag_node)
            self.drag_node = None
            self.is_dragging = False

        elif self.pan_start is not None:
            if not self.is_dragging and self.mode in ["ADD_FUNC", "ADD_RES"]:
                self.save_state()
                wx, wy = self.to_world(event.x, event.y)
                self.add_node(wx, wy)
            self.pan_start = None
            self.is_dragging = False

    def _finalize_drag(self, event):
        self.save_state(state=self.pre_drag_graph_state) # save previous state before modification
        
        # JSAT Snapping Logic
        if self.view_mode == config.VIEW_MODE_JSAT:
            _, world_y = self.to_world(event.x, event.y)
            new_layer = self.get_layer_from_y(world_y)
            if new_layer:
                self.G.nodes[self.drag_node]['layer'] = new_layer
                # Visual snap logic handled in get_draw_pos via data update
                
        self.redraw()

    def handle_click(self, node_id):
        self.inspected_node = node_id
        
        if self.mode == "SELECT": 
            self.redraw()
            
        elif self.mode == "DELETE": 
            self.save_state()
            self.G.remove_node(node_id)
            self.inspected_node = None
            self.redraw()
            
        elif self.mode == "ADD_EDGE":
            self._handle_add_edge(node_id)

    def _handle_add_edge(self, node_id):
        if not self.selected_node: 
            self.selected_node = node_id
            self.redraw()
            return

        if self.selected_node == node_id:
            return

        # Enforce Alternating connection types (Func <-> Res, no fun-->fun or res-->res)
        type_start = self.G.nodes[self.selected_node].get('type')
        type_end = self.G.nodes[node_id].get('type')
        
        if type_start == type_end:
            messagebox.showerror("Connection Error", f"Cannot connect {type_start} to {type_end}.\nConnections must alternate (Func <-> Res).")
        else:
            is_hard = messagebox.askyesno("Interdependency Type", "Is this a HARD constraint?\n\nYes = Essential (Hard)\nNo = Supportive (Soft)")
            edge_type = config.EDGE_TYPE_HARD if is_hard else config.EDGE_TYPE_SOFT
            
            self.save_state()
            self.G.add_edge(self.selected_node, node_id, type=edge_type)
        
        self.selected_node = None
        self.redraw()

    # Drawing Logic

    def redraw(self, rebuild_dash=True):
        self.canvas.delete("all")
        
        # 1. Background Layers
        if self.view_mode == config.VIEW_MODE_JSAT:
            self._draw_layer_lines()
            
        # 2. Highlights
        self._draw_highlights()
        
        # 3. Graph Content
        self._draw_edges()
        self._draw_nodes()
        
        # 4. Refresh Dashboard
        # Only rebuild if explicitly requested AND not currently dragging sidebar
        if rebuild_dash and not self.is_dragging:
            self.rebuild_dashboard()

    def _draw_layer_lines(self):
        for layer_name in config.LAYER_ORDER:
            world_y = config.JSAT_LAYERS[layer_name]
            _, screen_y = self.to_screen(0, world_y)
            self.canvas.create_line(0, screen_y, 20000, screen_y, fill="#ddd", dash=(4, 4))
            self.canvas.create_text(10, screen_y - 10, text=layer_name, anchor="w", fill="#888", font=("Arial", 8, "italic"))

    def _draw_highlights(self):
        if not self.current_highlights: return
        
        edge_counts = {}
        for h in self.current_highlights:
            color = h.get('color', 'yellow')
            width = h.get('width', 8) * self.zoom
            
            # Draw Nodes
            for n in h.get('nodes', []):
                wx, wy = self.get_draw_pos(n)
                sx, sy = self.to_screen(wx, wy)
                rad = (config.NODE_RADIUS * self.zoom) + (width/2)
                self.canvas.create_oval(sx-rad, sy-rad, sx+rad, sy+rad, fill=color, outline=color)
            
            # Draw Edges (with offset for overlaps)
            for u, v in h.get('edges', []):
                edge_key = tuple(sorted((u, v)))
                count = edge_counts.get(edge_key, 0)
                edge_counts[edge_key] = count + 1
                
                wx1, wy1 = self.get_draw_pos(u)
                wx2, wy2 = self.get_draw_pos(v)
                sx1, sy1 = self.to_screen(wx1, wy1)
                sx2, sy2 = self.to_screen(wx2, wy2)
                
                # Offset logic
                offset_step = width / 2
                current_offset = (count * width) - offset_step
                dx, dy = sx2 - sx1, sy2 - sy1
                length = math.hypot(dx, dy)
                if length == 0: continue
                
                nx_vec, ny_vec = -dy / length, dx / length
                os_x, os_y = nx_vec * current_offset, ny_vec * current_offset
                
                self.canvas.create_line(sx1+os_x, sy1+os_y, sx2+os_x, sy2+os_y, 
                                        fill=color, width=width, capstyle=tk.ROUND)

    def _draw_edges(self):
        r = config.NODE_RADIUS * self.zoom
        
        for u, v, d in self.G.edges(data=True):
            e_type = d.get('type', config.EDGE_TYPE_HARD)
            
            # Filter
            if self.edge_view_mode != "ALL" and e_type != self.edge_view_mode:
                continue

            # Style
            is_soft = (e_type == config.EDGE_TYPE_SOFT)
            color = config.SOFT_EDGE_COLOR if is_soft else config.HARD_EDGE_COLOR
            dash = config.SOFT_EDGE_DASH if is_soft else None
            width = (1.5 if is_soft else 2.0) * self.zoom

            # Coordinates
            wx1, wy1 = self.get_draw_pos(u)
            wx2, wy2 = self.get_draw_pos(v)
            sx1, sy1 = self.to_screen(wx1, wy1)
            sx2, sy2 = self.to_screen(wx2, wy2)
            
            dx, dy = sx2 - sx1, sy2 - sy1
            dist = math.hypot(dx, dy)
            if dist == 0: continue
            
            # Stop line at node edge
            gap = r + 2
            tx = sx2 - (dx/dist)*gap
            ty = sy2 - (dy/dist)*gap
            
            self.canvas.create_line(sx1, sy1, tx, ty, arrow=tk.LAST, width=width, fill=color, dash=dash)

    def _draw_nodes(self):
        r = config.NODE_RADIUS * self.zoom
        font_size = max(15, int(10 * self.zoom))
        
        for n, d in self.G.nodes(data=True):
            wx, wy = self.get_draw_pos(n)
            sx, sy = self.to_screen(wx, wy)
            
            ag_list = d.get('agent', ["Unassigned"])
            if not isinstance(ag_list, list): ag_list = [ag_list]
            
            # Outline Style
            outline, width = "black", 1
            if n == self.selected_node:
                outline, width = "blue", 3
            elif n == self.inspected_node:
                outline, width = "orange", 3
            
            # Shape Render
            if d.get('type') == "Function":
                self._draw_rect_node(sx, sy, r, ag_list, outline, width)
            else:
                self._draw_circle_node(sx, sy, r, ag_list, outline, width)
                
            # Label
            label_offset = r + (5 * self.zoom)
            self.canvas.create_text(sx, sy-label_offset, text=d.get('label',''), font=("Arial", font_size, "bold"), anchor="s")

    def _draw_rect_node(self, sx, sy, r, agents, outline, width):
        total_w = (r * 2)
        strip_w = total_w / len(agents)
        start_x = sx - r
        
        for i, ag in enumerate(agents):
            fill = self.agents.get(ag, "white")
            x1 = start_x + (i * strip_w)
            x2 = start_x + ((i + 1) * strip_w)
            self.canvas.create_rectangle(x1, sy-r, x2, sy+r, fill=fill, outline="")
            
        self.canvas.create_rectangle(sx-r, sy-r, sx+r, sy+r, fill="", outline=outline, width=width)

    def _draw_circle_node(self, sx, sy, r, agents, outline, width):
        if len(agents) == 1:
            fill = self.agents.get(agents[0], "white")
            self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill=fill, outline=outline, width=width)
        else:
            extent = 360 / len(agents)
            start_angle = 90
            for ag in agents:
                fill = self.agents.get(ag, "white")
                self.canvas.create_arc(sx-r, sy-r, sx+r, sy+r, start=start_angle, extent=extent, fill=fill, outline="")
                start_angle += extent
            self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill="", outline=outline, width=width)

    # Dashboard Builders 

    def rebuild_dashboard(self):
        # dictionary for the drag-and-drop geometry check
        self.agent_ui_frames = {}

        # preserve scroll position
        try: scroll_pos = self.scroll_canvas.yview()[0]
        except: scroll_pos = 0.0

        # clear existing widgets
        for w in self.inspector_frame.winfo_children(): w.destroy()
        for w in self.scrollable_content.winfo_children(): w.destroy()

        # Build Sections
        self._build_stats_section()
        self._build_agent_section() # This populates self.agent_ui_frames
        self._build_inspector_section()
        
        # restore scroll
        self.scrollable_content.update_idletasks()
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
        self.scroll_canvas.yview_moveto(scroll_pos)

    def _build_stats_section(self):
        tk.Label(self.scrollable_content, text="Network Statistics", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(fill=tk.X, pady=(10, 5))
        stats_frame = tk.Frame(self.scrollable_content, bg="white", bd=1, relief=tk.SOLID)
        stats_frame.pack(fill=tk.X, padx=5)

        def add_row(text, color="black", callback=None, metric_key=None):
            lbl = tk.Label(stats_frame, text=text, bg="white", fg=color)
            if callback:
                lbl.config(cursor="hand2")
                lbl.bind("<Button-1>", lambda e: callback())
            lbl.pack(anchor="w", padx=5)
            if metric_key and metric_key in METRIC_DESCRIPTIONS:
                CreateToolTip(lbl, METRIC_DESCRIPTIONS[metric_key])

        # Standard Metrics
        standard_metrics = [
            ("Density", "Density"), 
            ("Cyclomatic Number", "Cyclomatic Number"),
            ("Global Efficiency", "Global Efficiency"), 
            ("Supportive Gain", "Supportive Gain"),
            ("Soft/Hard Ratio", "Brittleness Ratio"), 
            ("Critical Vulnerability", "Critical Vulnerability"),
            ("Func. Redundancy", "Functional Redundancy"),
            ("Agent Criticality", "Agent Criticality"),
            ("Collab. Ratio", "Collaboration Ratio")
        ]
        
        for label, key in standard_metrics:
            val = calculate_metric(self.G, key)
            add_row(f"{label}: {val}", metric_key=key)

        # Interactive Metrics
        add_row(f"Interdependence: {calculate_metric(self.G, 'Interdependence')}", "blue", 
                lambda: self.trigger_visual_analytics("interdependence"), "Interdependence")
        
        add_row(f"Total Cycles: {calculate_metric(self.G, 'Total Cycles')}", "blue", 
                lambda: self.trigger_visual_analytics("cycles"), "Total Cycles")
        
        # Metric: Cycles List
        cycles = list(nx.simple_cycles(self.G))
        avg_len = sum(len(c) for c in cycles) / len(cycles) if cycles else 0.0
        add_row(f"Avg Cycle Length: {avg_len:.2f}", metric_key="Avg Cycle Length")
        
        if cycles:
            items = [{'label': len(c), 'tooltip': f"Cycle {i+1}:\n" + " -> ".join([str(self.G.nodes[n].get('label', n)) for n in c])} for i, c in enumerate(cycles)]
            self._create_scrollable_list_ui(stats_frame, "", items, ["blue"], lambda idx: self.trigger_single_cycle_vis(idx)).pack(fill=tk.X, padx=5, pady=2)

        # Metric: Modularity
        try:
            mod_val = calculate_metric(self.G, 'Modularity')
            add_row(f"Modularity: {mod_val}", "blue", lambda: self.trigger_visual_analytics("modularity"), "Modularity")
            
            comms = sorted(nx.community.greedy_modularity_communities(self.G.to_undirected()), key=len, reverse=True)
            if comms:
                mod_items = [{'label': len(c), 'tooltip': f"Group {i+1}:\n" + ", ".join([str(self.G.nodes[n].get('label', n)) for n in c])} for i, c in enumerate(comms)]
                self._create_scrollable_list_ui(stats_frame, "", mod_items, ["blue"], lambda idx: self.trigger_single_modularity_vis(idx)).pack(fill=tk.X, padx=5, pady=2)
        except:
            add_row("Modularity: Err")

    def _build_agent_section(self):
        tk.Label(self.scrollable_content, text="Agent Overview", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(fill=tk.X, pady=(15, 2))
        
        # Top Controls
        ctrl = tk.Frame(self.scrollable_content, bg="#e0e0e0", bd=1, relief=tk.RAISED)
        ctrl.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(ctrl, text="New Agent", command=self.create_agent, bg="white").pack(pady=5)

        # 1. Group Nodes
        agent_map = {name: [] for name in self.agents}
        for n, d in self.G.nodes(data=True):
            ag_list = d.get('agent', ["Unassigned"])
            if not isinstance(ag_list, list): ag_list = [ag_list]
            for ag in ag_list:
                target = ag if ag in agent_map else "Unassigned"
                if target not in agent_map: agent_map[target] = []
                agent_map[target].append(n)

        # 2. Build UI
        for name, color in self.agents.items():
            af = tk.Frame(self.scrollable_content, bg="#e0e0e0", bd=1, relief=tk.RAISED)
            af.pack(fill=tk.X, pady=2, padx=5)
            
            # Save frame for drag-and-drop geometry check
            self.agent_ui_frames[name] = af
            
            # Agent Header
            hf = tk.Frame(af, bg="#e0e0e0"); hf.pack(fill=tk.X)
            tk.Label(hf, bg=color, width=3).pack(side=tk.LEFT, padx=5, fill=tk.X)
            lbl = tk.Label(hf, text=name, bg="#e0e0e0", font=("Arial", 10, "bold"))
            lbl.pack(side=tk.LEFT, fill=tk.X)
            lbl.bind("<Button-1>", lambda e, a=name: self.edit_agent(a))

            # Nodes List
            nodes = agent_map.get(name, [])
            if nodes:
                for nid in nodes:
                    lbl_text = self.G.nodes[nid].get('label', str(nid))
                    
                    # --- THE FIX: Use Label instead of Button ---
                    # We style it with relief and border to LOOK like a button
                    btn = tk.Label(af, text=f" {lbl_text}", anchor="w", 
                                   bg="white", 
                                   font=("Arial", 11),       # Larger Font
                                   bd=2, relief=tk.RAISED,   # 3D Button Look
                                   padx=10, pady=5,          # Larger Click Area
                                   cursor="hand2")           # Hand Cursor
                    
                    btn.pack(fill=tk.X, padx=5, pady=2)
                    
                    # Bindings
                    btn.bind("<Button-1>", lambda e, n=nid: self.on_sidebar_node_press(e, n))
                    btn.bind("<Button-3>", lambda e, n=nid: self.open_sharing_dialog(n))
                    btn.bind("<Button-2>", lambda e, n=nid: self.open_sharing_dialog(n))
                    
                    # Hover Effect (Optional polish)
                    btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#f0f8ff"))
                    btn.bind("<Leave>", lambda e, b=btn: b.config(bg="white"))

            else:
                tk.Label(af, text="(Empty)", bg="#e0e0e0", fg="#666", font=("Arial", 8, "italic")).pack(anchor="w", padx=10)

    def _build_inspector_section(self):
        if self.inspected_node is None or not self.G.has_node(self.inspected_node):
            tk.Label(self.inspector_frame, text="(Select a node to inspect)", bg="#fff8e1", fg="#888").pack(pady=5)
            return

        d = self.G.nodes[self.inspected_node]
        tk.Label(self.inspector_frame, text="SELECTED NODE INSPECTOR", bg="#fff8e1", font=("Arial", 10, "bold")).pack(pady=2)

        # Details
        tk.Label(self.inspector_frame, text=f"ID: {self.inspected_node} | Lbl: {d.get('label')}", bg="#fff8e1", font=("Arial", 9, "bold")).pack(anchor="w", padx=5)

        # Layer Control
        r2 = tk.Frame(self.inspector_frame, bg="#fff8e1"); r2.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(r2, text="Layer:", bg="#fff8e1").pack(side=tk.LEFT)
        
        current_layer = self.get_node_layer(d)
        layer_var = tk.StringVar(value=current_layer)
        layer_box = ttk.Combobox(r2, textvariable=layer_var, values=config.LAYER_ORDER, state="readonly", width=18)
        layer_box.pack(side=tk.LEFT, padx=5)
        
        def on_layer_change(event):
            self.save_state()
            self.G.nodes[self.inspected_node]['layer'] = layer_var.get()
            self.redraw()
        layer_box.bind("<<ComboboxSelected>>", on_layer_change)

        # Metrics
        def safe_metric(func, **kwargs):
            try: return f"{func(self.G, **kwargs)[self.inspected_node]:.3f}"
            except: return "0.000"

        stats = (f"In-Degree:     {self.G.in_degree(self.inspected_node)}\n"
                 f"Out-Degree:    {self.G.out_degree(self.inspected_node)}\n"
                 f"Degree Cent.:  {safe_metric(nx.degree_centrality)}\n"
                 f"Eigenvector:   {safe_metric(nx.eigenvector_centrality, max_iter=100, tol=1e-04)}\n"
                 f"Betweenness:   {safe_metric(nx.betweenness_centrality)}")
        
        tk.Label(self.inspector_frame, text=stats, bg="#fff8e1", justify=tk.LEFT, font=("Consolas", 13)).pack(anchor="w", padx=5, pady=5)

    def _create_scrollable_list_ui(self, parent, label_text, items, colors, click_callback, label_click_callback=None):
        container = tk.Frame(parent, bg=parent.cget('bg'))
        
        if not items:
             tk.Label(container, text=f"{label_text} (None)", bg=parent.cget('bg')).pack(anchor="w")
             return container

        lbl = tk.Label(container, text=f"{label_text} [", bg=parent.cget('bg'))
        lbl.pack(side=tk.LEFT, anchor="n", pady=2)
        
        if label_click_callback:
            lbl.config(fg="blue", cursor="hand2")
            lbl.bind("<Button-1>", lambda e: label_click_callback())
        
        scroll_wrapper = tk.Frame(container, bg="white")
        scroll_wrapper.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="n")

        h_scroll = tk.Scrollbar(scroll_wrapper, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        h_canvas = tk.Canvas(scroll_wrapper, height=25, bg="white", highlightthickness=0, xscrollcommand=h_scroll.set)
        h_canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
        h_scroll.config(command=h_canvas.xview)
        
        inner_frame = tk.Frame(h_canvas, bg="white")
        h_canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        
        for i, item in enumerate(items):
            txt_color = colors[i % len(colors)]
            btn = tk.Label(inner_frame, text=str(item['label']), font=("Arial", 14, "bold"), 
                           fg=txt_color, cursor="hand2", bg="white")
            btn.pack(side=tk.LEFT)
            btn.bind("<Button-1>", lambda e, idx=i: click_callback(idx))
            
            if item.get('tooltip'): CreateToolTip(btn, text=item['tooltip'])
            if i < len(items) - 1: tk.Label(inner_frame, text=", ", bg="white").pack(side=tk.LEFT)
        
        tk.Label(inner_frame, text=" ]", bg="white").pack(side=tk.LEFT)
        
        inner_frame.update_idletasks()
        h_canvas.config(scrollregion=h_canvas.bbox("all"))
        
        h_canvas.bind("<MouseWheel>", lambda e: h_canvas.xview_scroll(int(-1*(e.delta/120)), "units"))
        return container

    # Mode & Toolbar Logic 

    def build_toolbar(self, parent):
        r1 = tk.Frame(parent); r1.pack(fill=tk.X, pady=2)
        
        # History
        tk.Button(r1, text="↶", command=self.undo, width=2).pack(side=tk.LEFT, padx=1)
        tk.Button(r1, text="↷", command=self.redo, width=2).pack(side=tk.LEFT, padx=1)
        
        # View Filters
        tk.Label(r1, text=" | Edges: ", fg="#555", font=("Arial", 15)).pack(side=tk.LEFT)
        for name, mode in [("All", "ALL"), ("Required", config.EDGE_TYPE_HARD), ("Assistive", config.EDGE_TYPE_SOFT)]:
             tk.Button(r1, text=name, command=lambda m=mode: self.set_edge_view(m), font=("Arial", 12)).pack(side=tk.LEFT, padx=1)
        
        self.view_btn = tk.Button(r1, text="👁 View: Free", command=self.toggle_view, bg="#e1bee7", font=("Arial", 12, "bold"))
        self.view_btn.pack(side=tk.LEFT, padx=10)
        
        # Modes
        for k, txt in [("SELECT", "➤ Select"), ("ADD_FUNC", "Add Func"), ("ADD_RES", "Add Res"), ("ADD_EDGE", "Connect"), ("DELETE", "Delete")]:
            self.create_mode_button(r1, k, txt)
        
        # Row 2: File Ops
        r2 = tk.Frame(parent); r2.pack(fill=tk.X, pady=2)
        tk.Label(r2, text="| RAM:", fg="#888").pack(side=tk.LEFT, padx=5)
        tk.Button(r2, text="Store Architecture", command=self.save_architecture_internal).pack(side=tk.LEFT, padx=2)
        tk.Button(r2, text="Compare", command=self.open_comparison_dialog, bg="#ffd700").pack(side=tk.LEFT, padx=5)
        
        tk.Label(r2, text="| Disk:", fg="#888").pack(side=tk.LEFT, padx=5)
        tk.Button(r2, text="Save JSON", command=self.initiate_save_json).pack(side=tk.LEFT, padx=2)
        tk.Button(r2, text="Open JSON", command=self.load_from_json).pack(side=tk.LEFT, padx=2)
        tk.Button(r2, text="📷 PNG", command=self.export_as_image, bg="#e0e0e0").pack(side=tk.LEFT, padx=2)
        
        self.update_mode_indicator()

    def set_edge_view(self, mode):
        self.edge_view_mode = mode
        self.redraw()

    def toggle_view(self):
        is_free = (self.view_mode == config.VIEW_MODE_FREE)
        self.view_mode = config.VIEW_MODE_JSAT if is_free else config.VIEW_MODE_FREE
        self.view_btn.config(text="👁 View: JSAT Layers" if is_free else "👁 View: Free")
        self.redraw()

    def create_mode_button(self, parent, mode_key, text):
        btn = tk.Button(parent, text=text, command=lambda: self.set_mode(mode_key))
        btn.pack(side=tk.LEFT, padx=2)
        self.mode_buttons[mode_key] = btn

    def set_mode(self, m): 
        self.mode = m
        self.selected_node = None
        self.status_label.config(text=f"Mode: {m}")
        self.update_mode_indicator()
        self.redraw()
    
    def update_mode_indicator(self):
        for mode_key, btn in self.mode_buttons.items():
            is_active = (mode_key == self.mode)
            btn.config(bg="#87CEFA" if is_active else ("#ffcccc" if mode_key == "DELETE" else "#f0f0f0"), 
                       relief=tk.SUNKEN if is_active else tk.RAISED)

    # Node/Agent Helpers

    def assign_agent_logic(self, node_id, agent_name):
        current_data = self.G.nodes[node_id].get('agent', ["Unassigned"])
        if not isinstance(current_data, list): current_data = [current_data]
        
        if "Unassigned" in current_data and agent_name != "Unassigned":
            current_data.remove("Unassigned")
            
        if agent_name in current_data:
            current_data.remove(agent_name)
            if not current_data: current_data = ["Unassigned"]
        else:
            current_data.append(agent_name)
            
        self.G.nodes[node_id]['agent'] = current_data

    def on_double_click(self, event):
        # Check Node
        node = self._get_node_at(event.x, event.y)
        if node is not None:
            self.open_node_editor(node)
            return

        # Check Edge
        edge = self.find_edge_at(event.x, event.y)
        if edge:
            u, v = edge
            curr = self.G.edges[u, v].get('type', config.EDGE_TYPE_HARD)
            new_type = config.EDGE_TYPE_SOFT if curr == config.EDGE_TYPE_HARD else config.EDGE_TYPE_HARD
            self.save_state()
            self.G.edges[u, v]['type'] = new_type
            self.redraw()

    def _get_node_at(self, x, y):
        r_screen = config.NODE_RADIUS * self.zoom
        for n in self.G.nodes:
            wx, wy = self.get_draw_pos(n)
            sx, sy = self.to_screen(wx, wy)
            if math.hypot(x - sx, y - sy) <= r_screen:
                return n
        return None

    def open_node_editor(self, nid):
        win = Toplevel(self.root)
        win.title("Edit Node")
        
        tk.Label(win, text="Label:").pack()
        e_lbl = tk.Entry(win)
        e_lbl.insert(0, self.G.nodes[nid].get('label', ''))
        e_lbl.pack()
        
        def save():
            self.save_state()
            self.G.nodes[nid]['label'] = e_lbl.get()
            win.destroy()
            self.redraw()
            
        tk.Button(win, text="Save", command=save).pack(pady=10)

    def add_node(self, x, y):
        nid = (max(self.G.nodes)+1) if self.G.nodes else 0
        typ = "Function" if self.mode == "ADD_FUNC" else "Resource"
        self.G.add_node(nid, pos=(x, y), type=typ, agent="Unassigned", 
                        label=typ[0], layer=("Base Environment" if typ == "Resource" else "Distributed Work"))
        self.redraw()

    def create_agent(self):
        n = simpledialog.askstring("Input", "Name:")
        if n and n not in self.agents:
            c = simpledialog.askstring("Input", "Color:") or "grey"
            self.agents[n] = c
            self.rebuild_dashboard()
    
    def edit_agent(self, agent_name):
        win = Toplevel(self.root); win.title("Edit Agent"); win.geometry("250x220")
        
        tk.Label(win, text="Name:").pack(pady=(10, 0))
        ne = tk.Entry(win); ne.insert(0, agent_name); ne.pack()
        tk.Label(win, text="Color:").pack(pady=(10, 0))
        ce = tk.Entry(win); ce.insert(0, self.agents[agent_name]); ce.pack()
        
        def save():
            new_name, new_color = ne.get(), ce.get()
            if new_name and new_color:
                self.save_state()
                del self.agents[agent_name]
                self.agents[new_name] = new_color
                
                # Update nodes
                for n, d in self.G.nodes(data=True): 
                    ag = d.get('agent')
                    if ag == agent_name: self.G.nodes[n]['agent'] = new_name # handle simple string
                    elif isinstance(ag, list) and agent_name in ag: # handle list
                        idx = ag.index(agent_name)
                        ag[idx] = new_name
                
                self.redraw()
                win.destroy()

        def delete():
            if agent_name == "Unassigned": return
            if messagebox.askyesno("Delete", f"Delete '{agent_name}'?"):
                self.save_state()
                for n, d in self.G.nodes(data=True):
                    ag = d.get('agent')
                    if isinstance(ag, list):
                        if agent_name in ag: ag.remove(agent_name)
                        if not ag: self.G.nodes[n]['agent'] = ["Unassigned"]
                del self.agents[agent_name]
                self.redraw()
                win.destroy()

        tk.Button(win, text="Save", command=save, bg="#e1bee7").pack(pady=15, fill=tk.X, padx=20)
        tk.Button(win, text="Delete", command=delete, bg="#ffcccc").pack(pady=5, fill=tk.X, padx=20)

    # History & IO 

    def save_state(self, state=None):
        snapshot = state if state else self.G.copy()
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > config.HISTORY_LIMIT: self.undo_stack.pop(0)
        self.redo_stack.clear()
    
    def undo(self):
        if self.undo_stack: 
            self.redo_stack.append(self.G.copy())
            self.G = self.undo_stack.pop()
            self.redraw()
            
    def redo(self):
        if self.redo_stack: 
            self.undo_stack.append(self.G.copy())
            self.G = self.redo_stack.pop()
            self.redraw()

    def export_as_image(self):
        fp = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not fp: return
        try:
            x, y = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
            w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
            ImageGrab.grab(bbox=(x, y, x+w, y+h)).save(fp)
            messagebox.showinfo("Success", f"Saved to {fp}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def initiate_save_json(self):
        fp = filedialog.asksaveasfilename(defaultextension=".json")
        if not fp: return

        # Prepare Data Structure
        nodes_dict = {}
        agent_authorities = {name: [] for name in self.agents}
        
        for nid, d in self.G.nodes(data=True):
            lbl = d.get('label', f"Node_{nid}")
            layer = d.get('layer', "Base Environment").replace(" ", "")
            typ = d.get('type', "Function")
            nodes_dict[lbl] = {"Type": f"{layer}{typ}", "UserData": lbl}
            
            ag_list = d.get('agent', ["Unassigned"])
            if not isinstance(ag_list, list): ag_list = [ag_list]
            for ag in ag_list:
                if ag in agent_authorities: agent_authorities[ag].append(lbl)

        edges_list = []
        for u, v, d in self.G.edges(data=True): 
            edges_list.append({
                "Source": self.G.nodes[u].get('label', f"Node_{u}"),
                "Target": self.G.nodes[v].get('label', f"Node_{v}"),
                "UserData": {"type": d.get('type', config.EDGE_TYPE_HARD)}
            })

        final = {"GraphData": {
            "Nodes": nodes_dict, 
            "Edges": edges_list, 
            "Agents": {name: {"Authority": auth} for name, auth in agent_authorities.items()}
        }}

        with open(fp, 'w') as f: json.dump(final, f, indent=4)

    def load_from_json(self):
        fp = filedialog.askopenfilename()
        if not fp: return
        try:
            with open(fp, 'r', encoding='utf-8-sig') as f: data = json.load(f)["GraphData"]
            
            self.save_state()
            self.G.clear()
            self.agents = config.DEFAULT_AGENTS.copy()
            
            # 1. Load Agents
            label_to_agents = {}
            for ag_name, ag_data in data.get("Agents", {}).items():
                if ag_name not in self.agents: 
                    self.agents[ag_name] = "#" + ''.join([random.choice('ABCDEF89') for _ in range(6)])
                for node_lbl in ag_data.get("Authority", []):
                    label_to_agents.setdefault(node_lbl, []).append(ag_name)
            
            # 2. Load Nodes
            label_to_id = {}
            layer_counters = {l: 100 for l in config.LAYER_ORDER}
            
            for i, (lbl, props) in enumerate(data.get("Nodes", {}).items()):
                n_type, n_layer = self._parse_node_attributes(props.get("Type", ""))
                
                # Position logic
                pos_y = config.JSAT_LAYERS.get(n_layer, 550)
                pos_x = layer_counters.get(n_layer, 100)
                layer_counters[n_layer] = pos_x + 120
                
                assigned = label_to_agents.get(lbl, ["Unassigned"])
                self.G.add_node(i, pos=(pos_x, pos_y), layer=n_layer, type=n_type, 
                                label=props.get("UserData", lbl), agent=assigned)
                label_to_id[lbl] = i

            # 3. Load Edges
            for e in data.get("Edges", []):
                u, v = label_to_id.get(e["Source"]), label_to_id.get(e["Target"])
                if u is not None and v is not None:
                    self.G.add_edge(u, v, type=e.get("UserData", {}).get("type", config.EDGE_TYPE_HARD))
            
            self.redraw()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")

    def _parse_node_attributes(self, combined_string):
        """Extracts (Type, Layer) from the specific JSON string format."""
        n_type = "Resource"
        layer = "Base Environment"
        
        if combined_string.endswith("Function"):
            n_type = "Function"
            prefix = combined_string.replace("Function", "")
        elif combined_string.endswith("Resource"):
            prefix = combined_string.replace("Resource", "")
        else:
            prefix = combined_string
            
        norm_prefix = prefix.lower().replace(" ", "")
        for known in config.LAYER_ORDER:
            if known.lower().replace(" ", "") == norm_prefix:
                layer = known
                break
        return n_type, layer

    # Comparative Analytics 

    def save_architecture_internal(self):
        n = simpledialog.askstring("Name", "Name:")
        if n: self.saved_archs[n] = self.G.copy()

    def open_comparison_dialog(self):
        if not self.saved_archs: 
            messagebox.showinfo("Info", "No saved architectures.")
            return

        w = Toplevel(self.root)
        tk.Label(w, text="Select (Ctrl+Click)").pack()
        lb = tk.Listbox(w, selectmode=tk.MULTIPLE)
        lb.pack()
        opts = ["Current"] + list(self.saved_archs.keys())
        for o in opts: lb.insert(tk.END, o)
        lb.selection_set(0)

        def go():
            selected = [lb.get(i) for i in lb.curselection()]
            graphs = [(n, self.G.copy() if n == "Current" else self.saved_archs[n].copy()) for n in selected]
            w.destroy()
            self.launch_compare_window(graphs)
        tk.Button(w, text="Go", command=go).pack()

    def launch_compare_window(self, graph_list):
        w = Toplevel(self.root)
        w.title("Comparative Analytics")
        w.geometry("1400x900")
        
        # UI Structure
        top_frame = tk.Frame(w, bd=2, relief=tk.RAISED)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Header
        h_row = tk.Frame(top_frame)
        h_row.pack(fill=tk.X, pady=5)
        tk.Label(h_row, text="Comparative Analytics", font=("Arial", 16, "bold")).pack(side=tk.LEFT, padx=10)
        
        paned = tk.PanedWindow(w, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        graph_container = tk.Frame(paned)
        paned.add(graph_container, minsize=400)
        
        inspector_frame = tk.Frame(paned, bd=2, relief=tk.SUNKEN, bg="#f0f0f0")
        paned.add(inspector_frame, minsize=200)

        panels = []

        # Helper: Highlight Trigger
        def set_highlights(metric_name):
            for _, panel in panels:
                if metric_name == "Total Cycles":
                    panel.set_highlights(metric_visualizations.get_cycle_highlights(panel.G))
                elif metric_name == "Interdependence":
                    panel.set_highlights(metric_visualizations.get_interdependence_highlights(panel.G))
                elif metric_name == "Modularity":
                    panel.set_highlights(metric_visualizations.get_modularity_highlights(panel.G))
                else:
                    panel.set_highlights([])

        # Helper: Refresh Grid
        def refresh_grid():
            for child in top_frame.winfo_children(): 
                if child != h_row: child.destroy()
            
            grid_f = tk.Frame(top_frame)
            grid_f.pack(fill=tk.X, padx=10)
            
            # Headers
            tk.Label(grid_f, text="Metric", font=("Arial", 12, "bold"), width=18, relief="solid", bd=1, bg="#e0e0e0").grid(row=0, column=0, sticky="nsew")
            for i, (name, _) in enumerate(graph_list):
                tk.Label(grid_f, text=name, font=("Arial", 12, "bold"), width=15, relief="solid", bd=1, bg="#e0e0e0").grid(row=0, column=i+1, sticky="nsew")
            
            metrics = ["Nodes", "Edges", "Density", "Cyclomatic Number", "Total Cycles", "Avg Cycle Length", "Interdependence", "Modularity", "Global Efficiency"]
            
            for r, m in enumerate(metrics):
                # Row Header
                lbl = tk.Label(grid_f, text=m, font=("Arial", 12), relief="solid", bd=1, anchor="w", padx=5)
                lbl.grid(row=r+1, column=0, sticky="nsew")
                if m in ["Total Cycles", "Interdependence", "Modularity"]:
                    lbl.config(fg="blue", cursor="hand2")
                    lbl.bind("<Button-1>", lambda e, name=m: set_highlights(name))

                # Values
                for c, (_, g) in enumerate(graph_list):
                    val = calculate_metric(g, m)
                    tk.Label(grid_f, text=str(val), font=("Arial", 12), relief="solid", bd=1).grid(row=r+1, column=c+1, sticky="nsew")

        # --- THE FIX: Node Comparison Callback ---
        def on_node_clicked(node_label):
            # Clear previous inspector contents
            for child in inspector_frame.winfo_children():
                child.destroy()
                
            tk.Label(inspector_frame, text=f"Node Inspector: '{node_label}'", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=5, anchor="w", padx=10)
            
            table_f = tk.Frame(inspector_frame, bg="white", bd=1, relief="solid")
            table_f.pack(fill=tk.X, padx=10, pady=5)
            
            # Table Headers
            tk.Label(table_f, text="Node Metric", font=("Arial", 10, "bold"), relief="solid", bd=1, bg="#e0e0e0", width=18).grid(row=0, column=0, sticky="nsew")
            for i, (g_name, _) in enumerate(graph_list):
                tk.Label(table_f, text=g_name, font=("Arial", 10, "bold"), relief="solid", bd=1, bg="#e0e0e0", width=15).grid(row=0, column=i+1, sticky="nsew")
            
            node_metrics = ["In-Degree", "Out-Degree", "Degree Centrality", "Betweenness", "Eigenvector"]
            for r, m in enumerate(node_metrics):
                tk.Label(table_f, text=m, font=("Arial", 10), relief="solid", bd=1, anchor="w", padx=5).grid(row=r+1, column=0, sticky="nsew")
            
            # Populate Data
            for col, (g_name, g) in enumerate(graph_list):
                # 1. Find the node ID by its string label
                target_id = None
                for n, d in g.nodes(data=True):
                    if d.get('label') == node_label:
                        target_id = n
                        break
                
                # 2. If node doesn't exist in this graph, fill with dashes
                if target_id is None:
                    for r in range(len(node_metrics)):
                        tk.Label(table_f, text="-", font=("Arial", 10), relief="solid", bd=1).grid(row=r+1, column=col+1, sticky="nsew")
                    continue
                
                # 3. Calculate metrics safely
                def safe_m(func, **kwargs):
                    try: return f"{func(g, **kwargs)[target_id]:.3f}"
                    except: return "0.000"

                vals = [
                    str(g.in_degree(target_id)),
                    str(g.out_degree(target_id)),
                    safe_m(nx.degree_centrality),
                    safe_m(nx.betweenness_centrality),
                    safe_m(nx.eigenvector_centrality, max_iter=100, tol=1e-04)
                ]
                
                for r, val in enumerate(vals):
                    tk.Label(table_f, text=val, font=("Arial", 10), relief="solid", bd=1).grid(row=r+1, column=col+1, sticky="nsew")
        # -----------------------------------------

        # Initialize Panels
        for name, g in graph_list:
            # We now pass `on_node_clicked` instead of `lambda x: None`
            p = InteractiveComparisonPanel(graph_container, g, name, config.NODE_RADIUS, self.agents, None, on_node_clicked)
            panels.append((name, p))
            
        refresh_grid()

    # Utils 
    
    def get_layer_from_y(self, y):
        closest, min_dist = None, 9999
        for name, ly in config.JSAT_LAYERS.items():
            dist = abs(y - ly)
            if dist < min_dist:
                min_dist, closest = dist, name
        return closest

    def on_sidebar_node_press(self, event, node_id):
        # 1. Set Drag Data
        self.sidebar_drag_data = node_id
        
        # 2. Manually Select the Node (Update internal state)
        self.selected_node = node_id
        self.inspected_node = node_id
        
        # 3. Redraw the CANVAS ONLY (Blue outline)
        # We pass False here so the sidebar buttons are NOT destroyed/recreated
        self.redraw(rebuild_dash=False)
        
        # 4. Setup Global Release (Start the Drag)
        self.root.config(cursor="hand2")
        self.root.bind("<ButtonRelease-1>", self.on_sidebar_node_release)

    def on_sidebar_node_release(self, event):
        self.root.config(cursor="")
        self.root.unbind("<ButtonRelease-1>")

        if self.sidebar_drag_data:
            mx, my = event.x_root, event.y_root
            target_agent = None

            # Geometry Check
            for name, frame in self.agent_ui_frames.items():
                fx, fy = frame.winfo_rootx(), frame.winfo_rooty()
                fw, fh = frame.winfo_width(), frame.winfo_height()
                
                if fx <= mx <= fx + fw and fy <= my <= fy + fh:
                    target_agent = name
                    break
            
            # Apply Move
            if target_agent:
                self.save_state()
                self.G.nodes[self.sidebar_drag_data]['agent'] = [target_agent]
                
            self.sidebar_drag_data = None

        # NOW we allow the dashboard to rebuild to show the changes
        self.redraw(rebuild_dash=True)

    def find_edge_at(self, x, y):
        threshold = 8 
        for u, v in self.G.edges():
            wx1, wy1 = self.get_draw_pos(u)
            wx2, wy2 = self.get_draw_pos(v)
            sx1, sy1 = self.to_screen(wx1, wy1)
            sx2, sy2 = self.to_screen(wx2, wy2)
            
            # Distance from point to segment
            dx, dy = sx2 - sx1, sy2 - sy1
            if dx == 0 and dy == 0: dist = math.hypot(x - sx1, y - sy1)
            else:
                t = ((x - sx1) * dx + (y - sy1) * dy) / (dx*dx + dy*dy)
                t = max(0, min(1, t))
                dist = math.hypot(x - (sx1 + t * dx), y - (sy1 + t * dy))
            
            if dist < threshold: return (u, v)
        return None

    def trigger_visual_analytics(self, mode):
        if self.active_vis_mode == mode:
            self.current_highlights = []
            self.active_vis_mode = None
        else:
            self.active_vis_mode = mode
            if mode == "cycles":
                self.current_highlights = metric_visualizations.get_cycle_highlights(self.G)
            elif mode == "interdependence":
                self.current_highlights = metric_visualizations.get_interdependence_highlights(self.G)
            elif mode == "modularity":
                self.current_highlights = metric_visualizations.get_modularity_highlights(self.G)
        self.redraw()
    
    def trigger_single_cycle_vis(self, index, graph_source=None):
        target = graph_source if graph_source else self.G
        hl = metric_visualizations.get_single_cycle_highlight(target, index)
        if graph_source: return hl
        
        self.current_highlights = hl
        self.active_vis_mode = f"cycle_{index}"
        self.redraw()

    def trigger_single_modularity_vis(self, index, graph_source=None):
        target = graph_source if graph_source else self.G
        hl = metric_visualizations.get_single_modularity_highlight(target, index)
        if graph_source: return hl
        
        self.current_highlights = hl
        self.active_vis_mode = f"mod_group_{index}"
        self.redraw()
    
    def on_right_click(self, event):
        node = self._get_node_at(event.x, event.y)
        if node is not None:
            self.open_sharing_dialog(node)

    def open_sharing_dialog(self, node_id):
        win = Toplevel(self.root)
        win.title("Share Authority")
        win.geometry("300x400")
        
        current_label = self.G.nodes[node_id].get('label', 'Node')
        tk.Label(win, text=f"Share '{current_label}' with:", font=("Arial", 11, "bold")).pack(pady=10)

        frame = tk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=10)

        # get current agents assigned to this node
        current_agents = self.G.nodes[node_id].get('agent', ["Unassigned"])
        if not isinstance(current_agents, list): current_agents = [current_agents]

        # hold True/False variables for each agent
        check_vars = {}

        for agent_name in self.agents.keys():
            var = tk.BooleanVar(value=(agent_name in current_agents))
            check_vars[agent_name] = var
            
            cb = tk.Checkbutton(frame, text=agent_name, variable=var, anchor="w", font=("Arial", 10))
            cb.pack(fill=tk.X, pady=2)

        def save_shares():
            # colect all checked agents
            selected = [name for name, var in check_vars.items() if var.get()]
            
            # fallback if none selected
            if not selected: selected = ["Unassigned"]

            self.save_state()
            self.G.nodes[node_id]['agent'] = selected
            self.redraw()
            win.destroy()

        # footer buttons
        btn_frame = tk.Frame(win, pady=10)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="Apply Shares", command=save_shares, bg="#90ee90", height=2).pack(fill=tk.X, padx=10)