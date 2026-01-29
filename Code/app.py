import tkinter as tk
from tkinter import simpledialog, messagebox, Toplevel, filedialog, ttk
import networkx as nx
import math
import json

import config
from utils import calculate_metric
from components import InteractiveComparisonPanel
import metric_visualizations

class GraphBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Interactive JSAT")
        self.root.geometry("1400x900") 
        
        # --- Backend Data ---
        self.G = nx.DiGraph()
        self.saved_archs = {} 
        self.undo_stack = []
        self.redo_stack = []
        
        # --- State ---
        self.selected_node = None     
        self.inspected_node = None    
        self.drag_node = None      
        self.drag_start_pos = None 
        self.is_dragging = False   
        self.pre_drag_graph_state = None
        self.sidebar_drag_data = None
        self.current_highlights = [] 
        self.active_vis_mode = None

        # --- View Settings ---
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_start = None 
        
        # --- Mode Settings ---
        self.mode = "SELECT"
        self.mode_buttons = {}
        self.view_mode = config.VIEW_MODE_FREE
        
        self.agents = config.DEFAULT_AGENTS.copy()
        self.current_agent = config.DEFAULT_CURRENT_AGENT
        
        self.setup_ui()
        
    def setup_ui(self):
        # Toolbar
        toolbar_frame = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        self.build_toolbar(toolbar_frame)

        # Main Layout
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(main_container, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Canvas Bindings
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        
        # Zooming
        self.canvas.bind("<MouseWheel>", self.on_zoom)      
        self.canvas.bind("<Button-4>", lambda e: self.on_zoom(e, 1))  
        self.canvas.bind("<Button-5>", lambda e: self.on_zoom(e, -1)) 

        # Dashboard Sidebar
        self.dashboard_frame = tk.Frame(main_container, width=350, bg="#f0f0f0", bd=1, relief=tk.SUNKEN)
        self.dashboard_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.dashboard_frame.pack_propagate(False) 
        
        tk.Label(self.dashboard_frame, text="Network Dashboard", font=("Arial", 14, "bold"), bg="#4a4a4a", fg="white", pady=8).pack(fill=tk.X)
        
        self.inspector_frame = tk.Frame(self.dashboard_frame, bg="#fff8e1", bd=2, relief=tk.GROOVE)
        self.inspector_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Scrollable Area for Stats/Agents
        self.scroll_canvas = tk.Canvas(self.dashboard_frame, bg="#f0f0f0")
        self.scrollbar = tk.Scrollbar(self.dashboard_frame, orient="vertical", command=self.scroll_canvas.yview)
        self.scrollable_content = tk.Frame(self.scroll_canvas, bg="#f0f0f0")

        self.scroll_canvas.create_window((0, 0), window=self.scrollable_content, anchor="nw", width=330)
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrollable_content.bind("<Configure>", lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))

        # Footer Status
        self.status_label = tk.Label(self.root, text="Mode: Select & Inspect", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.redraw()

    # --- Core Helpers ---

    def get_node_layer(self, data):
        """Returns the Y-axis layer name. Uses saved data or defaults based on type."""
        # 1. Use existing layer if set
        if 'layer' in data and data['layer'] in config.JSAT_LAYERS:
            return data['layer']
        
        # 2. Fallback default
        if data.get('type') == "Resource":
            return "Base Environment" 
        return "Distributed Work"

    def get_draw_pos(self, node_id):
        """Calculates WORLD coordinates based on current view mode."""
        data = self.G.nodes[node_id]
        raw_x, raw_y = data.get('pos', (100, 100))
        
        # If dragging in JSAT mode, show raw position until dropped
        if self.view_mode == config.VIEW_MODE_JSAT and self.drag_node == node_id and self.is_dragging:
            return raw_x, raw_y
        
        if self.view_mode == config.VIEW_MODE_FREE:
            return raw_x, raw_y
        else:
            # Snap Y to the layer height
            return raw_x, config.JSAT_LAYERS[self.get_node_layer(data)]

    # --- Coordinate Transforms ---

    def to_screen(self, wx, wy):
        sx = (wx * self.zoom) + self.offset_x
        sy = (wy * self.zoom) + self.offset_y
        return sx, sy

    def to_world(self, sx, sy):
        wx = (sx - self.offset_x) / self.zoom
        wy = (sy - self.offset_y) / self.zoom
        return wx, wy

    def on_zoom(self, event, direction=None):
        if direction is None:
            factor = 1.1 if event.delta > 0 else 0.9
        else:
            factor = 1.1 if direction > 0 else 0.9
        self.zoom *= factor
        self.redraw()

    # --- Interaction Logic ---

    def on_mouse_down(self, event):
        clicked_node = None
        # Hit detection
        for n in self.G.nodes:
            wx, wy = self.get_draw_pos(n)
            sx, sy = self.to_screen(wx, wy)
            if math.hypot(event.x - sx, event.y - sy) <= (config.NODE_RADIUS * self.zoom):
                clicked_node = n
                break
                
        if clicked_node is not None:
            self.pre_drag_graph_state = self.G.copy()
            self.drag_node = clicked_node
            self.drag_start_pos = (event.x, event.y)
            self.is_dragging = False
        else:
            # Edge Deletion Check
            if self.mode == "DELETE":
                clicked_edge = self.find_edge_at(event.x, event.y)
                if clicked_edge:
                    self.save_state()
                    self.G.remove_edge(*clicked_edge)
                    self.redraw()
                    return 

            # Background Click (Pan or Add)
            self.inspected_node = None
            self.pan_start = (event.x, event.y)
            self.is_dragging = False
            self.redraw()

    def on_mouse_drag(self, event):
        if self.drag_node is not None:
            # Drag threshold prevents accidental moves
            if math.hypot(event.x - self.drag_start_pos[0], event.y - self.drag_start_pos[1]) > 5: 
                self.is_dragging = True
                wx, wy = self.to_world(event.x, event.y)
                self.G.nodes[self.drag_node]['pos'] = (wx, wy)
                self.redraw()

        elif self.pan_start is not None:
            if math.hypot(event.x - self.pan_start[0], event.y - self.pan_start[1]) > 5:
                self.is_dragging = True
                dx = event.x - self.pan_start[0]
                dy = event.y - self.pan_start[1]
                self.offset_x += dx
                self.offset_y += dy
                self.pan_start = (event.x, event.y)
                self.redraw()

    def on_mouse_up(self, event):
        if self.drag_node is not None:
            if self.is_dragging: 
                # Save history
                self.undo_stack.append(self.pre_drag_graph_state)
                if len(self.undo_stack) > config.HISTORY_LIMIT: 
                    self.undo_stack.pop(0)
                self.redo_stack.clear()
                
                # JSAT Snapping Logic
                if self.view_mode == config.VIEW_MODE_JSAT:
                    _, world_y = self.to_world(event.x, event.y)
                    new_layer = self.get_layer_from_y(world_y)
                    if new_layer:
                        self.G.nodes[self.drag_node]['layer'] = new_layer
                        world_x, _ = self.to_world(event.x, event.y)
                        self.G.nodes[self.drag_node]['pos'] = (world_x, config.JSAT_LAYERS[new_layer])
                        self.redraw()
            else: 
                # It was just a click, not a drag
                self.handle_click(self.drag_node)
            
            self.drag_node = None
            self.is_dragging = False

        elif self.pan_start is not None:
            if not self.is_dragging:
                # Background click -> Add Node?
                if self.mode in ["ADD_FUNC", "ADD_RES"]:
                    self.save_state()
                    wx, wy = self.to_world(event.x, event.y)
                    self.add_node(wx, wy)
            self.pan_start = None
            self.is_dragging = False

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
            if not self.selected_node: 
                self.selected_node = node_id
                self.redraw()
            else:
                if self.selected_node != node_id:
                    # Enforce Alternating Types (Func <-> Res)
                    type_start = self.G.nodes[self.selected_node].get('type')
                    type_end = self.G.nodes[node_id].get('type')
                    
                    if type_start == type_end:
                        messagebox.showerror("Connection Error", 
                                             f"Cannot connect {type_start} to {type_end}.\nConnections must alternate (Func <-> Res).")
                    else:
                        self.save_state()
                        self.G.add_edge(self.selected_node, node_id)
                
                self.selected_node = None
                self.redraw()
                
        elif self.mode == "ASSIGN_AGENT":
            if self.G.nodes[node_id]['agent'] != self.current_agent:
                self.save_state()
                self.assign_agent_logic(node_id, self.current_agent)
                self.redraw()

    def redraw(self):
        self.canvas.delete("all")

        # Add highlight first so it aapear behind the nodes/edges, with overlap highlighting
        if self.current_highlights:
            edge_counts = {}
            
            for h in self.current_highlights:
                color = h.get('color', 'yellow')
                width = h.get('width', 8) * self.zoom
                
                # 1. Draw Nodes (Halo) - Moved first to match components.py structure
                for n in h.get('nodes', []):
                    wx, wy = self.get_draw_pos(n)
                    sx, sy = self.to_screen(wx, wy)
                    rad = (config.NODE_RADIUS * self.zoom) + (width/2)
                    self.canvas.create_oval(sx-rad, sy-rad, sx+rad, sy+rad, fill=color, outline=color)
                
                # 2. Draw Edges (Offset)
                for u, v in h.get('edges', []):
                    edge_key = tuple(sorted((u, v)))
                    count = edge_counts.get(edge_key, 0)
                    edge_counts[edge_key] = count + 1
                    
                    # Calculate Offset
                    offset_step = width / 2
                    current_offset = (count * width) - offset_step
                    
                    wx1, wy1 = self.get_draw_pos(u)
                    wx2, wy2 = self.get_draw_pos(v)
                    sx1, sy1 = self.to_screen(wx1, wy1)
                    sx2, sy2 = self.to_screen(wx2, wy2)
                    
                    dx, dy = sx2 - sx1, sy2 - sy1
                    length = math.hypot(dx, dy)
                    if length == 0: continue
                    
                    nx, ny = -dy / length, dx / length
                    
                    os_x = nx * current_offset
                    os_y = ny * current_offset
                    
                    self.canvas.create_line(sx1+os_x, sy1+os_y, sx2+os_x, sy2+os_y, 
                                          fill=color, width=width, capstyle=tk.ROUND)
        
        # 1. Draw Layer Lines (JSAT Mode only)
        if self.view_mode == config.VIEW_MODE_JSAT:
            for layer_name in config.LAYER_ORDER:
                world_y = config.JSAT_LAYERS[layer_name]
                _, screen_y = self.to_screen(0, world_y)
                self.canvas.create_line(0, screen_y, 20000, screen_y, fill="#ddd", dash=(4, 4))
                self.canvas.create_text(10, screen_y - 10, text=layer_name, anchor="w", fill="#888", font=("Arial", 8, "italic"))

        # 2. Draw Edges
        r = config.NODE_RADIUS * self.zoom
        for u, v in self.G.edges():
            wx1, wy1 = self.get_draw_pos(u)
            wx2, wy2 = self.get_draw_pos(v)
            sx1, sy1 = self.to_screen(wx1, wy1)
            sx2, sy2 = self.to_screen(wx2, wy2)
            
            dx, dy = sx2 - sx1, sy2 - sy1
            dist = math.hypot(dx, dy)
            if dist == 0: continue
            
            gap = r + 2
            # Shorten line so arrow doesn't overlap node
            tx = sx2 - (dx/dist)*gap
            ty = sy2 - (dy/dist)*gap
            self.canvas.create_line(sx1, sy1, tx, ty, arrow=tk.LAST, width=2*self.zoom)
            
        # 3. Draw Nodes
        for n, d in self.G.nodes(data=True):
            wx, wy = self.get_draw_pos(n)
            sx, sy = self.to_screen(wx, wy)
            
            fill = self.agents.get(d.get('agent'), "white")
            
            # Outline logic
            outline = "black"
            width = 1
            if n == self.selected_node:
                outline, width = "blue", 3
            elif n == self.inspected_node:
                outline, width = "orange", 3
            
            # Shape logic
            if d.get('type') == "Function":
                self.canvas.create_rectangle(sx-r, sy-r, sx+r, sy+r, fill=fill, outline=outline, width=width)
            else:
                self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill=fill, outline=outline, width=width)
            
            font_size = max(15, int(10 * self.zoom))
            label_offset = r + (5 * self.zoom)
            self.canvas.create_text(sx, sy-label_offset, text=d.get('label',''), font=("Arial", font_size, "bold"), anchor = "s")
            
        self.rebuild_dashboard()

    def trigger_visual_analytics(self, mode):
        # Toggle: If clicking same mode, turn off.
        if self.active_vis_mode == mode:
            self.current_highlights = []
            self.active_vis_mode = None
            self.redraw()
            return

        self.active_vis_mode = mode
        
        if mode == "cycles":
            self.current_highlights = metric_visualizations.get_cycle_highlights(self.G)
        elif mode == "interdependence":
            self.current_highlights = metric_visualizations.get_interdependence_highlights(self.G)
            
        self.redraw()

    def rebuild_dashboard(self):
        """Refreshes the sidebar. Careful not to duplicate widgets."""
        
        # 1. Clear Inspector (we will rebuild it at the end)
        for w in self.inspector_frame.winfo_children(): w.destroy()

        # 2. Clear Scrollable Content (Stats & Agent List)
        for w in self.scrollable_content.winfo_children(): w.destroy()
        
        # --- Stats Section ---
        tk.Label(self.scrollable_content, text="Network Statistics", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(fill=tk.X, pady=(10, 5))
        stats_frame = tk.Frame(self.scrollable_content, bg="white", bd=1, relief=tk.SOLID)
        stats_frame.pack(fill=tk.X, padx=5)
        
        tk.Label(stats_frame, text=f"Density: {calculate_metric(self.G, 'Density')}", bg="white").pack(anchor="w", padx=5)
        tk.Label(stats_frame, text=f"Avg Clustering: {calculate_metric(self.G, 'Avg Clustering')}", bg="white").pack(anchor="w", padx=5)
        tk.Label(stats_frame, text=f"Cyclomatic No.: {calculate_metric(self.G, 'Cyclomatic Number')}", bg="white").pack(anchor="w", padx=5)
        tk.Label(stats_frame, text=f"Critical Loop Nodes: {calculate_metric(self.G, 'Critical Loop Nodes')}", bg="white").pack(anchor="w", padx=5)
        # Making Total Cycles label a clickable button
        # tk.Label(stats_frame, text=f"Total Cycles: {calculate_metric(self.G, 'Total Cycles')}", bg="white").pack(anchor="w", padx=5)
        cyc_val = calculate_metric(self.G, 'Total Cycles')
        lbl_cyc = tk.Label(stats_frame, text=f"Total Cycles: {cyc_val}", bg="white", cursor="hand2", fg="blue")
        lbl_cyc.pack(anchor="w", padx=5)
        lbl_cyc.bind("<Button-1>", lambda e: self.trigger_visual_analytics("cycles"))

        #Making Interdependence a clickable button
        # tk.Label(stats_frame, text=f"Interdependence: {calculate_metric(self.G, 'Interdependence')}", bg="white").pack(anchor="w", padx=5)
        int_val = calculate_metric(self.G, 'Interdependence')
        lbl_int = tk.Label(stats_frame, text=f"Interdependence: {int_val}", bg="white", cursor="hand2", fg="blue")
        lbl_int.pack(anchor="w", padx=5)
        lbl_int.bind("<Button-1>", lambda e: self.trigger_visual_analytics("interdependence"))

        # Add click-able buttons for individual cycle highglighting
        #tk.Label(stats_frame, text=f"Avg Cycle Len: {calculate_metric(self.G, 'Avg Cycle Length')}", bg="white").pack(anchor="w", padx=5)
        # --- Interactive Avg Cycle Length (Scrollable) ---
        # 1. Main Container for the Row
        ac_container = tk.Frame(stats_frame, bg="white")
        ac_container.pack(fill=tk.X, padx=5, pady=2)
        
        try:
            cycles = list(nx.simple_cycles(self.G))
            if not cycles:
                 tk.Label(ac_container, text="Avg Cycle Length: 0.0", bg="white").pack(anchor="w")
            else:
                lengths = [len(c) for c in cycles]
                avg = sum(lengths) / len(lengths)
                
                # 2. Fixed Label on Left: "Avg Cycle Length: 4.67 ["
                tk.Label(ac_container, text=f"Avg Cycle Length: {avg:.2f} [", bg="white").pack(side=tk.LEFT, anchor="n", pady=2)
                
                # 3. Scrollable Area for the Numbers
                scroll_wrapper = tk.Frame(ac_container, bg="white")
                scroll_wrapper.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="n")

                # Horizontal Scrollbar
                h_scroll = tk.Scrollbar(scroll_wrapper, orient=tk.HORIZONTAL)
                h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
                
                # Canvas (Holds the buttons)
                h_canvas = tk.Canvas(scroll_wrapper, height=25, bg="white", highlightthickness=0, xscrollcommand=h_scroll.set)
                h_canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
                h_scroll.config(command=h_canvas.xview)
                
                # Inner Frame (Lives inside Canvas)
                inner_frame = tk.Frame(h_canvas, bg="white")
                h_canvas.create_window((0, 0), window=inner_frame, anchor="nw")
                
                # 4. Interactive Buttons
                cycle_colors = [
                    "#FF1493", "#00C000", "#008B8B", "#DAA520", 
                    "#FF4500", "#9400D3", "#32CD32", "#1E90FF"
                ]

                for i, length in enumerate(lengths):
                    txt_color = cycle_colors[i % len(cycle_colors)]
                    
                    btn = tk.Label(inner_frame, text=str(length), font=("Arial", 14, "bold"), 
                                   fg="blue", cursor="hand2", bg="white")
                    btn.pack(side=tk.LEFT)
                    btn.bind("<Button-1>", lambda e, idx=i: self.trigger_single_cycle_vis(idx))
                    
                    # Add comma
                    if i < len(lengths) - 1:
                        tk.Label(inner_frame, text=", ", bg="white").pack(side=tk.LEFT)
                
                # Closing Bracket
                tk.Label(inner_frame, text=" ]", bg="white").pack(side=tk.LEFT)
                
                # 5. Update Scroll Region (Crucial step to make scrolling work)
                inner_frame.update_idletasks()
                h_canvas.config(scrollregion=h_canvas.bbox("all"))
                
                # Optional: Mousewheel scrolling support
                def _on_scroll(event):
                    h_canvas.xview_scroll(int(-1*(event.delta/120)), "units")
                h_canvas.bind("<MouseWheel>", _on_scroll)

        except Exception as e:
            tk.Label(ac_container, text="Err", bg="white").pack(side=tk.LEFT)
            print(f"Cycle calc error: {e}")

        tk.Label(stats_frame, text=f"Global Efficiency: {calculate_metric(self.G, 'Global Efficiency')}", bg="white").pack(anchor="w", padx=5)
        tk.Label(stats_frame, text=f"Modularity: {calculate_metric(self.G, 'Modularity')}", bg="white").pack(anchor="w", padx=5)

        # --- Agent Overview Section ---
        tk.Label(self.scrollable_content, text="Agent Overview", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(fill=tk.X, pady=(15, 2))
        
        # Controls
        ctrl_frame = tk.Frame(self.scrollable_content, bg="#e0e0e0", bd=1, relief=tk.RAISED)
        ctrl_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(ctrl_frame, text="New Agent", command=self.create_agent, bg="white").pack(pady=5)

        # Group Nodes by Agent
        agent_map = {name: [] for name in self.agents.keys()}
        for node, data in self.G.nodes(data=True):
            ag = data.get('agent', 'Unassigned')
            agent_map.setdefault(ag, []).append(node)

        # Render Agent List
        for agent_name, color in self.agents.items():
            af = tk.Frame(self.scrollable_content, bg="#e0e0e0", bd=1, relief=tk.RAISED)
            af.pack(fill=tk.X, pady=2, padx=5)
            # Store name on widget for drag-and-drop detection
            af.agent_name = agent_name 
            
            # Header (Color + Name)
            hf = tk.Frame(af, bg="#e0e0e0")
            hf.pack(fill=tk.X)
            hf.agent_name = agent_name
            
            # Color Box
            cb = tk.Label(hf, bg=color, width=3)
            cb.pack(side=tk.LEFT, padx=5)
            cb.bind("<Button-1>", lambda e, a=agent_name: self.edit_agent(a))
            
            # Name Label
            lbl = tk.Label(hf, text=agent_name, bg="#e0e0e0", font=("Arial", 10, "bold"))
            lbl.pack(side=tk.LEFT, fill=tk.X)
            lbl.bind("<Button-1>", lambda e, a=agent_name: self.edit_agent(a))

            # Nodes List
            nodes_list = agent_map.get(agent_name, [])
            if nodes_list:
                for nid in nodes_list:
                    nlbl = self.G.nodes[nid].get('label', str(nid))
                    btn = tk.Button(af, text=f"• {nlbl}", anchor="w", bg="white", relief=tk.FLAT, font=("Arial", 9),
                                    command=lambda n=nid: self.handle_click(n))
                    btn.pack(fill=tk.X, padx=10, pady=1)
                    
                    # Sidebar Drag Events
                    btn.bind("<Button-1>", lambda e, n=nid: self.on_sidebar_node_press(e, n))
                    btn.bind("<B1-Motion>", lambda e: None) 
                    btn.bind("<ButtonRelease-1>", self.on_sidebar_node_release)
            else:
                tk.Label(af, text="(Empty)", bg="#e0e0e0", fg="#666", font=("Arial", 8, "italic")).pack(anchor="w", padx=10)

        # --- Inspector Section (Built only once!) ---
        if self.inspected_node is not None and self.G.has_node(self.inspected_node):
            d = self.G.nodes[self.inspected_node]
            
            tk.Label(self.inspector_frame, text="SELECTED NODE INSPECTOR", bg="#fff8e1", font=("Arial", 10, "bold")).pack(pady=2)
            
            # ID & Label
            r1 = tk.Frame(self.inspector_frame, bg="#fff8e1"); r1.pack(fill=tk.X, padx=5)
            tk.Label(r1, text=f"ID: {self.inspected_node} | Lbl: {d.get('label')}", bg="#fff8e1", font=("Arial", 9, "bold")).pack(anchor="w")
            
            # Layer Selector
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

            # Node Metrics
            r3 = tk.Frame(self.inspector_frame, bg="#fff8e1"); r3.pack(fill=tk.X, padx=5, pady=5)
            
            in_d = self.G.in_degree(self.inspected_node)
            out_d = self.G.out_degree(self.inspected_node)
            
            try: deg_c = nx.degree_centrality(self.G)[self.inspected_node]
            except: deg_c = 0.0
            
            try: eig_c = nx.eigenvector_centrality(self.G, max_iter=100, tol=1e-04).get(self.inspected_node, 0)
            except: eig_c = 0.0

            try: 
                # Betweenness finds "Bottlenecks"
                bet_c = nx.betweenness_centrality(self.G)[self.inspected_node]
            except: bet_c = 0.0
            
            stat_txt = (f"In-Degree:     {in_d}\n"
                        f"Out-Degree:    {out_d}\n"
                        f"Degree Cent.:  {deg_c:.3f}\n"
                        f"Eigenvector:   {eig_c:.3f}\n"
                        f"Betweenness:   {bet_c:.3f}\n"
                        )
            
            tk.Label(r3, text=stat_txt, bg="#fff8e1", justify=tk.LEFT, font=("Consolas", 13)).pack(anchor="w")

        else:
            tk.Label(self.inspector_frame, text="(Select a node to inspect)", bg="#fff8e1", fg="#888").pack(pady=5)

    def toggle_view(self):
        if self.view_mode == config.VIEW_MODE_FREE:
            self.view_mode = config.VIEW_MODE_JSAT
            self.view_btn.config(text="👁 View: JSAT Layers")
        else:
            self.view_mode = config.VIEW_MODE_FREE
            self.view_btn.config(text="👁 View: Free")
        self.redraw()

    # --- UI Components ---
    
    def build_toolbar(self, parent):
        r1 = tk.Frame(parent)
        r1.pack(fill=tk.X, pady=2)
        
        # History & View
        tk.Button(r1, text="↶", command=self.undo, width=2).pack(side=tk.LEFT, padx=1)
        tk.Button(r1, text="↷", command=self.redo, width=2).pack(side=tk.LEFT, padx=1)
        tk.Frame(r1, width=10).pack(side=tk.LEFT)
        self.view_btn = tk.Button(r1, text="👁 View: Free", command=self.toggle_view, bg="#e1bee7", font=("Arial", 9, "bold"))
        self.view_btn.pack(side=tk.LEFT, padx=10)
        
        # Mode Buttons
        self.create_mode_button(r1, "SELECT", "➤ Select")
        self.create_mode_button(r1, "ADD_FUNC", "Add Func")
        self.create_mode_button(r1, "ADD_RES", "Add Res")
        self.create_mode_button(r1, "ADD_EDGE", "Connect")
        self.create_mode_button(r1, "DELETE", "Delete")
        
        # File/Agent Ops
        r2 = tk.Frame(parent)
        r2.pack(fill=tk.X, pady=2)
        
        tk.Label(r2, text="| RAM:", fg="#888").pack(side=tk.LEFT, padx=5)
        tk.Button(r2, text="Store Architecture", command=self.save_architecture_internal).pack(side=tk.LEFT, padx=2)
        tk.Button(r2, text="Compare Architecture", command=self.open_comparison_dialog, bg="#ffd700", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        tk.Label(r2, text="| Disk:", fg="#888").pack(side=tk.LEFT, padx=5)
        tk.Button(r2, text="Save Network", command=self.initiate_save_json).pack(side=tk.LEFT, padx=2)
        tk.Button(r2, text="Open Network", command=self.load_from_json).pack(side=tk.LEFT, padx=2)
        
        self.update_mode_indicator()

    def create_mode_button(self, parent, mode_key, text):
        btn = tk.Button(parent, text=text, command=lambda: self.set_mode(mode_key))
        btn.pack(side=tk.LEFT, padx=2)
        self.mode_buttons[mode_key] = btn

    def set_mode(self, m): 
        self.mode = m
        self.selected_node = None
        self.status_label.config(text=f"Mode: {'Select' if m=='SELECT' else m}")
        self.update_mode_indicator()
        self.redraw()
    
    def update_mode_indicator(self):
        ACTIVE_BG = "#87CEFA"
        INACTIVE_BG = "#f0f0f0"
        DELETE_BG = "#ffcccc"
        
        for mode_key, btn in self.mode_buttons.items():
            if mode_key == self.mode:
                btn.config(bg=ACTIVE_BG, relief=tk.SUNKEN)
            else:
                bg = DELETE_BG if mode_key == "DELETE" else INACTIVE_BG
                btn.config(bg=bg, relief=tk.RAISED)

    # --- Node/Agent Logic ---

    def assign_agent_logic(self, node_id, agent_name):
        self.G.nodes[node_id]['agent'] = agent_name
        # Propagate agent to connected nodes if they are functions
        if self.G.nodes[node_id]['type'] == "Function":
            for n in self.G.successors(node_id): 
                self.G.nodes[n]['agent'] = agent_name

    def on_double_click(self, event):
        # Find clicked node
        r_screen = config.NODE_RADIUS * self.zoom
        clicked = None
        for n in self.G.nodes:
            dwx, dwy = self.get_draw_pos(n)
            sx, sy = self.to_screen(dwx, dwy)
            if math.hypot(event.x - sx, event.y - sy) <= r_screen:
                clicked = n
                break
        if clicked is not None:
            self.open_node_editor(clicked)
            
    def open_node_editor(self, nid):
        win = Toplevel(self.root)
        win.title("Edit Node")
        d = self.G.nodes[nid]
        
        tk.Label(win, text="Label:").pack()
        e_lbl = tk.Entry(win)
        e_lbl.insert(0, d.get('label', ''))
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
        default_layer = "Base Environment" if typ == "Resource" else "Distributed Work"
        
        self.G.add_node(nid, 
                        pos=(x, y), 
                        type=typ, 
                        agent="Unassigned", 
                        label="F" if typ=="Function" else "R",
                        layer=default_layer)
        self.redraw()

    def create_agent(self):
        n = simpledialog.askstring("Input", "Name:")
        if n and n not in self.agents:
            c = simpledialog.askstring("Input", "Color:") or "grey"
            self.agents[n] = c
            self.rebuild_dashboard()
    
    def edit_agent(self, agent_name):
        win = Toplevel(self.root)
        win.title("Edit Agent")
        win.geometry("250x220")
        
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
                
                # Update nodes linked to old agent name
                for n, d in self.G.nodes(data=True): 
                    if d.get('agent') == agent_name: 
                        self.G.nodes[n]['agent'] = new_name
                
                self.redraw()
                win.destroy()

        def delete_this_agent():
            if agent_name == "Unassigned":
                messagebox.showwarning("Restricted", "Cannot delete 'Unassigned'.")
                return

            if messagebox.askyesno("Delete Agent", f"Delete '{agent_name}'? Nodes will revert to Unassigned."):
                self.save_state()
                for n, d in self.G.nodes(data=True):
                    if d.get('agent') == agent_name:
                        self.G.nodes[n]['agent'] = "Unassigned"
                
                del self.agents[agent_name]
                self.redraw()
                win.destroy()

        tk.Button(win, text="Save Changes", command=save, bg="#e1bee7").pack(pady=(15, 5), fill=tk.X, padx=20)
        tk.Button(win, text="Delete Agent", command=delete_this_agent, bg="#ffcccc", fg="red").pack(pady=5, fill=tk.X, padx=20)

    # --- File Operations ---

    def save_state(self):
        self.undo_stack.append(self.G.copy())
        if len(self.undo_stack) > config.HISTORY_LIMIT: 
            self.undo_stack.pop(0)
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

    def initiate_save_json(self): 
        self.finalize_json_save(self.G, "curr")
        
    def finalize_json_save(self, g, n):
        # ask for file location
        fp = filedialog.asksaveasfilename(initialfile=n, defaultextension=".json")
        if not fp: return

        # build nodes dictionary
        nodes_dict = {}
        
        # Pre-calculate Agent Authorities (Which agent owns which node label?)
        agent_authorities = {name: [] for name in self.agents.keys()}

        for nid, d in g.nodes(data=True):
            label = d.get('label', f"Node_{nid}")
            layer = d.get('layer', "Base Environment")
            n_type = d.get('type', "Function")
            
            # Format Type string: e.g. "Distributed Work" -> "DistributedWork"
            formatted_layer = layer.replace(" ", "")
            combined_type = f"{formatted_layer}{n_type}" # e.g., "DistributedWorkFunction"
            
            nodes_dict[label] = {
                "Type": combined_type,
                "UserData": label
            }

            # Add to agent authority list
            agent_name = d.get('agent', 'Unassigned')
            if agent_name in agent_authorities:
                agent_authorities[agent_name].append(label)

        # Build the edge list
        edges_list = []
        for u, v in g.edges():
            u_lbl = g.nodes[u].get('label', f"Node_{u}")
            v_lbl = g.nodes[v].get('label', f"Node_{v}")
            
            edges_list.append({
                "Source": u_lbl,
                "Target": v_lbl,
                "UserData": {"QOS": ""}
            })

        # Build the agents dictionary
        agents_dict = {}
        for name, _ in self.agents.items():
            agents_dict[name] = {
                "Authority": agent_authorities.get(name, [])
            }

        # Construct Final JSON Structure
        final_data = {
            "GraphData": {
                "Nodes": nodes_dict,
                "Edges": edges_list,
                "Agents": agents_dict
            }
        }

        # Save to Disk
        with open(fp, 'w') as f:
            json.dump(final_data, f, indent=4)
                
    def load_from_json(self):
        fp = filedialog.askopenfilename()
        if not fp: return
        
        try:
            # Use 'utf-8-sig' to handle potential invisible characters
            with open(fp, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                
            if "GraphData" not in data:
                messagebox.showerror("Error", "Invalid file format: Missing 'GraphData' key.")
                return

            self.save_state()
            self.G.clear()
            self.agents = config.DEFAULT_AGENTS.copy()
            
            graph_data = data["GraphData"]
            
            # --- 1. Load Agents ---
            raw_agents = graph_data.get("Agents", {})
            import random
            
            def get_random_color():
                return "#" + ''.join([random.choice('ABCDEF89') for _ in range(6)])

            label_to_agent = {} 
            
            for agent_name, agent_data in raw_agents.items():
                if agent_name not in self.agents:
                    self.agents[agent_name] = get_random_color()
                
                for node_label in agent_data.get("Authority", []):
                    label_to_agent[node_label] = agent_name

            # --- 2. Load Nodes ---
            nodes_data = graph_data.get("Nodes", {})
            label_to_id = {} 
            
            # Initialize counters for all known layers
            layer_x_counters = {l: 100 for l in config.LAYER_ORDER}
            
            for i, (label_key, node_props) in enumerate(nodes_data.items()):
                combined_type = node_props.get("Type", "BaseEnvironmentResource")
                user_data_lbl = node_props.get("UserData", label_key)
                
                # --- PARSING LOGIC START ---
                node_type = "Resource" # Default
                layer_prefix = combined_type
                
                # 1. Determine Type (Function vs Resource)
                if combined_type.endswith("Function"):
                    node_type = "Function"
                    layer_prefix = combined_type.replace("Function", "")
                elif combined_type.endswith("Resource"):
                    node_type = "Resource"
                    layer_prefix = combined_type.replace("Resource", "")
                
                # 2. Determine Layer
                # We normalize both strings to ignore spaces and casing for comparison
                # e.g. "DistributedWork" matches "Distributed Work"
                node_layer = "Base Environment" # Default fallback
                
                normalized_prefix = layer_prefix.lower().replace(" ", "")
                
                for known_layer in config.LAYER_ORDER:
                    normalized_known = known_layer.lower().replace(" ", "")
                    if normalized_known == normalized_prefix:
                        node_layer = known_layer
                        break
                # --- PARSING LOGIC END ---

                # Safety check: if layer not in counters, init it
                if node_layer not in layer_x_counters:
                    layer_x_counters[node_layer] = 100

                pos_y = config.JSAT_LAYERS.get(node_layer, 550)
                pos_x = layer_x_counters[node_layer]
                layer_x_counters[node_layer] += 120 
                
                assigned_agent = label_to_agent.get(label_key, "Unassigned")
                
                self.G.add_node(i, 
                                pos=(pos_x, pos_y), 
                                layer=node_layer, 
                                type=node_type, 
                                label=user_data_lbl, 
                                agent=assigned_agent)
                
                label_to_id[label_key] = i

            # --- 3. Load Edges ---
            edges_data = graph_data.get("Edges", [])
            for edge in edges_data:
                src_lbl = edge.get("Source")
                tgt_lbl = edge.get("Target")
                
                if src_lbl in label_to_id and tgt_lbl in label_to_id:
                    u = label_to_id[src_lbl]
                    v = label_to_id[tgt_lbl]
                    self.G.add_edge(u, v)
                    
            self.redraw()
            
        except Exception as e:
            messagebox.showerror("Critical Error", f"Failed to load file:\n{str(e)}")
            print(f"Full error: {e}")
            
    def save_architecture_internal(self):
        n = simpledialog.askstring("Name", "Name:")
        if n: 
            self.saved_archs[n] = self.G.copy()
    
    def open_comparison_dialog(self):
        av = ["Current"] + list(self.saved_archs.keys())
        if len(av) < 1: 
            messagebox.showinfo("Info", "No archs")
            return
            
        w = Toplevel(self.root)
        tk.Label(w, text="Select (Ctrl+Click)").pack()
        lb = tk.Listbox(w, selectmode=tk.MULTIPLE)
        lb.pack()
        
        for o in av:
            lb.insert(tk.END, o)
        
        lb.selection_set(0)
        
        def go():
            idx = lb.curselection()
            names = [lb.get(i) for i in idx]
            # Create list of (name, graph_copy)
            gs = [(n, self.G.copy() if n == "Current" else self.saved_archs[n].copy()) for n in names]
            
            # Inject colors for comparison view
            for _, g in gs:
                for n, d in g.nodes(data=True): 
                    d['_color_cache'] = self.agents.get(d.get('agent'), "white")
            
            w.destroy()
            self.launch_compare(gs)
            
        tk.Button(w, text="Go", command=go).pack()
        
    def launch_compare(self, gs):
        w = Toplevel(self.root)
        w.title("Comparative Analytics")
        w.geometry("1400x900") # Slightly wider to accommodate new columns
        w.update_idletasks()
        
        # Top Frame for System Metrics
        tf = tk.Frame(w, bd=2, relief=tk.RAISED)
        tf.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Paned Window for Graphs vs Inspector
        paned = tk.PanedWindow(w, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        graph_container = tk.Frame(paned)
        paned.add(graph_container, minsize=400)
        
        inspector_frame = tk.Frame(paned, bd=2, relief=tk.SUNKEN, bg="#f0f0f0")
        paned.add(inspector_frame, minsize=200)

        panels = []

        def toggle_compare_vis(metric_name):
            for name, panel in panels:
                if metric_name == "Total Cycles":
                    hl = metric_visualizations.get_cycle_highlights(panel.G)
                    panel.set_highlights(hl)
                elif metric_name == "Interdependence":
                    hl = metric_visualizations.get_interdependence_highlights(panel.G)
                    panel.set_highlights(hl)
                else:
                    panel.set_highlights([]) # Clear

        def refresh_metrics():
            # Clear previous widgets
            for widget in tf.winfo_children(): widget.destroy()
            tk.Label(tf, text="System Metrics Comparison", font=("Arial", 16, "bold")).pack(pady=5)
            
            grid_f = tk.Frame(tf)
            grid_f.pack(fill=tk.X, padx=10)
            
            metrics = ["Nodes", "Edges", "Density", "Avg Clustering", "Cyclomatic Number", 
                       "Critical Loop Nodes", "Total Cycles", "Avg Cycle Length", 
                       "Interdependence", "Modularity", "Global Efficiency"]
            
            # Headers
            tk.Label(grid_f, text="Metric", font=("Arial", 12, "bold"), width=18, relief="solid", bd=1, bg="#e0e0e0").grid(row=0, column=0, sticky="nsew")
            for i, (name, _) in enumerate(gs):
                tk.Label(grid_f, text=name, font=("Arial", 12, "bold"), width=15, relief="solid", bd=1, bg="#e0e0e0").grid(row=0, column=i+1, sticky="nsew")
                
            # Rows
            for r, m in enumerate(metrics):
                # 1. Metric Name Label
                lbl = tk.Label(grid_f, text=m, font=("Arial", 12), relief="solid", bd=1, anchor="w", padx=5)
                lbl.grid(row=r+1, column=0, sticky="nsew")
                
                # Special clickable handling for Name Column
                if m in ["Total Cycles", "Interdependence"]:
                    lbl.config(fg="blue", cursor="hand2")
                    lbl.bind("<Button-1>", lambda e, name=m: toggle_compare_vis(name))

                # 2. Metric Values (Columns)
                for c, (_, g) in enumerate(gs):
                    
                    # --- SPECIAL LOGIC FOR AVG CYCLE LENGTH ---
                    if m == "Avg Cycle Length":
                        cell_frame = tk.Frame(grid_f, bd=1, relief="solid", bg="#f0f0f0")
                        cell_frame.grid(row=r+1, column=c+1, sticky="nsew")
                        
                        try:
                            cycles = list(nx.simple_cycles(g))
                            if not cycles:
                                tk.Label(cell_frame, text="0.0", font=("Arial", 12), bg="#f0f0f0").pack()
                            else:
                                lengths = [len(x) for x in cycles]
                                avg = sum(lengths) / len(lengths)
                                
                                # Display Average
                                tk.Label(cell_frame, text=f"{avg:.2f} [", font=("Arial", 12), bg="#f0f0f0").pack(side=tk.LEFT)
                                
                                # Display Clickable Buttons
                                for idx, length in enumerate(lengths):
                                    btn = tk.Label(cell_frame, text=str(length), font=("Arial", 12, "bold"), 
                                                   fg="blue", cursor="hand2", bg="#f0f0f0")
                                    btn.pack(side=tk.LEFT)
                                    
                                    if idx < len(lengths) - 1:
                                        tk.Label(cell_frame, text=", ", font=("Arial", 12), bg="#f0f0f0").pack(side=tk.LEFT)
                                    
                                    # Handle Click
                                    def on_cycle_click(e, i=idx, graph=g, panel_idx=c):
                                        target_panel = panels[panel_idx][1] 
                                        hl = self.trigger_single_cycle_vis(i, graph)
                                        target_panel.set_highlights(hl)
                                        
                                    btn.bind("<Button-1>", on_cycle_click)
                                    
                                tk.Label(cell_frame, text="]", font=("Arial", 12), bg="#f0f0f0").pack(side=tk.LEFT)

                        except Exception as e:
                            tk.Label(cell_frame, text="Err", font=("Arial", 12)).pack()
                            print(e)
                    
                    # --- STANDARD LOGIC ---
                    else:
                        val = calculate_metric(g, m)
                        tk.Label(grid_f, text=str(val), font=("Arial", 12), relief="solid", bd=1).grid(row=r+1, column=c+1, sticky="nsew")

        def refresh_inspector(label):
            # Clear previous widgets
            for widget in inspector_frame.winfo_children(): widget.destroy()
            
            if not label:
                tk.Label(inspector_frame, text="Click a node to inspect across networks.", bg="#f0f0f0", font=("Arial", 20)).pack(pady=20)
                return
            
            tk.Label(inspector_frame, text=f"Inspecting Node: '{label}'", bg="#f0f0f0", font=("Arial", 16, "bold")).pack(pady=5)
            grid_f = tk.Frame(inspector_frame, bg="#f0f0f0")
            grid_f.pack(padx=10, pady=5)
            
            # --- 2. Define Node Metrics List (Matched to Main Inspector) ---
            headers = [
                "Network", 
                "Agent", 
                "In-Degree", 
                "Out-Degree", 
                "Degree Cent.", 
                "Eigenvector",
                "Betweenness",
            ]
            
            # Draw Headers
            for i, h in enumerate(headers):
                tk.Label(grid_f, text=h, font=("Arial", 13, "bold"), bg="#ddd", relief="solid", bd=1, width=14).grid(row=0, column=i, sticky="nsew")
            
            # Calculate and Draw Rows
            for r, (name, g) in enumerate(gs):
                target_node = None
                # Find the node ID by label in this specific graph
                for n, d in g.nodes(data=True):
                    if d.get('label') == label:
                        target_node = n
                        break
                
                vals = [name]
                if target_node is not None:
                    d = g.nodes[target_node]
                    vals.append(d.get('agent', 'N/A'))
                    vals.append(g.in_degree(target_node))
                    vals.append(g.out_degree(target_node))
                    
                    # Degree Centrality
                    try: dc = f"{nx.degree_centrality(g)[target_node]:.3f}"
                    except: dc = "0.00"
                    vals.append(dc)
                    
                    # Eigenvector
                    try: ec = f"{nx.eigenvector_centrality(g, max_iter=500, tol=1e-04).get(target_node, 0):.3f}"
                    except: ec = "0.00"
                    vals.append(ec)

                    # Betweenness (Added)
                    try: bc = f"{nx.betweenness_centrality(g)[target_node]:.3f}"
                    except: bc = "0.00"
                    vals.append(bc)

                else:
                    # If node doesn't exist in this graph variation
                    vals.extend(["(Not Found)", "-", "-", "-", "-", "-", "-"])
                
                # Render Row
                for c, v in enumerate(vals):
                    tk.Label(grid_f, text=str(v), font=("Arial", 14), relief="solid", bd=1, bg="white").grid(row=r+1, column=c, sticky="nsew")

        # Initial Render
        refresh_metrics()
        refresh_inspector(None)
        
        # Load interactive graph panels
        for n, g in gs:
            # FIX: Assign the new instance to variable 'p'
            p = InteractiveComparisonPanel(graph_container, g, n, config.NODE_RADIUS, self.agents, None, refresh_inspector)
            
            # Now 'p' exists and can be added to the list
            panels.append((n, p))
            
    # --- Helpers ---

    def get_layer_from_y(self, y):
        """Finds closest JSAT layer key given a Y coordinate."""
        closest_layer = None
        min_dist = 9999
        for name, ly in config.JSAT_LAYERS.items():
            dist = abs(y - ly)
            if dist < min_dist:
                min_dist = dist
                closest_layer = name
        return closest_layer

    def on_sidebar_node_press(self, event, node_id):
        self.sidebar_drag_data = node_id
        self.root.config(cursor="hand2")

    def on_sidebar_node_release(self, event):
        self.root.config(cursor="")
        if self.sidebar_drag_data is None: return
        
        # Detect drop on agent label
        target_widget = self.root.winfo_containing(event.x_root, event.y_root)
        found_agent = None
        curr = target_widget
        while curr:
            if hasattr(curr, "agent_name"):
                found_agent = curr.agent_name
                break
            curr = curr.master
            if curr == self.root: break
            
        if found_agent:
            self.save_state()
            self.assign_agent_logic(self.sidebar_drag_data, found_agent)
            self.redraw()
        self.sidebar_drag_data = None

    def distance_point_to_segment(self, px, py, x1, y1, x2, y2):
        """Math helper for edge detection."""
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        
        t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
        t = max(0, min(1, t))
        
        nearest_x = x1 + t * dx
        nearest_y = y1 + t * dy
        return math.hypot(px - nearest_x, py - nearest_y)
    
    def find_edge_at(self, x, y):
        threshold = 8 
        for u, v in self.G.edges():
            wx1, wy1 = self.get_draw_pos(u)
            wx2, wy2 = self.get_draw_pos(v)
            sx1, sy1 = self.to_screen(wx1, wy1)
            sx2, sy2 = self.to_screen(wx2, wy2)
            
            dist = self.distance_point_to_segment(x, y, sx1, sy1, sx2, sy2)
            if dist < threshold:
                return (u, v)
        return None

    def trigger_single_cycle_vis(self, index, graph_source=None):
        """
        index: The index of the cycle in the list [0, 1, 2...]
        graph_source: Used for comparison window to know WHICH graph to highlight
        """
        # If no graph provided, use the main self.G
        target_graph = graph_source if graph_source else self.G
        
        hl = metric_visualizations.get_single_cycle_highlight(target_graph, index)
        
        if graph_source:
            # logic for comparison window (handled via callback later)
            return hl 
        else:
            # logic for main window
            self.current_highlights = hl
            self.active_vis_mode = f"cycle_{index}"
            self.redraw()