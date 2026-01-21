# components.py
# Contains custom UI widgets. The InteractiveComparisonPanel is isolated here. 
# This makes it reusable and easier to fix drawing bugs.

import tkinter as tk
import math

class InteractiveComparisonPanel:
    """
    A specific panel for the Comparison Window.
    Features: Move Nodes, Pan View (Background Drag), Zoom (Scroll).
    """
    def __init__(self, parent, graph, name, node_radius, agents_map, redraw_callback, click_callback):
        self.G = graph
        self.name = name
        self.node_radius = node_radius
        self.agents = agents_map
        self.redraw_callback = redraw_callback 
        self.click_callback = click_callback   

        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drag_mode = None 
        self.drag_data = None 
        self.initialized = False

        self.outer = tk.Frame(parent, bd=2, relief=tk.GROOVE)
        self.outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(self.outer, text=name, font=("Arial", 11, "bold"), bg="#ddd").pack(fill=tk.X)
        self.canvas = tk.Canvas(self.outer, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bindings
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        
        # Mouse Wheel
        self.canvas.bind("<MouseWheel>", self.on_zoom)      
        self.canvas.bind("<Button-4>", lambda e: self.on_zoom(e, 1))  
        self.canvas.bind("<Button-5>", lambda e: self.on_zoom(e, -1)) 
        
        # Resize event for centering
        self.canvas.bind("<Configure>", self.on_resize)

    def on_resize(self, event):
        if not self.initialized:
            self.center_view(event.width, event.height)
            self.initialized = True
        self.redraw()

    def center_view(self, width, height):
        if self.G.number_of_nodes() == 0: return
        xs = [d.get('pos', (0,0))[0] for n, d in self.G.nodes(data=True)]
        ys = [d.get('pos', (0,0))[1] for n, d in self.G.nodes(data=True)]
        if not xs: return
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        graph_cx = (min_x + max_x) / 2
        graph_cy = (min_y + max_y) / 2
        
        self.offset_x = (width / 2) - (graph_cx * self.zoom)
        self.offset_y = (height / 2) - (graph_cy * self.zoom)

    def to_screen(self, wx, wy):
        sx = (wx * self.zoom) + self.offset_x
        sy = (wy * self.zoom) + self.offset_y
        return sx, sy

    def to_world(self, sx, sy):
        wx = (sx - self.offset_x) / self.zoom
        wy = (sy - self.offset_y) / self.zoom
        return wx, wy

    def redraw(self):
        self.canvas.delete("all")
        r = self.node_radius * self.zoom 
        
        # Edges
        for u, v in self.G.edges():
            p1 = self.G.nodes[u].get('pos', (0,0))
            p2 = self.G.nodes[v].get('pos', (0,0))
            sx1, sy1 = self.to_screen(p1[0], p1[1])
            sx2, sy2 = self.to_screen(p2[0], p2[1])
            self.canvas.create_line(sx1, sy1, sx2, sy2, arrow=tk.LAST, width=2*self.zoom)

        # Nodes
        for n, d in self.G.nodes(data=True):
            wx, wy = d.get('pos', (0,0))
            sx, sy = self.to_screen(wx, wy)
            
            ag = d.get('agent', "Unassigned")
            fill = self.agents.get(ag, "white")
            if '_color_cache' in d: fill = d['_color_cache']

            if d.get('type') == "Function":
                self.canvas.create_rectangle(sx-r, sy-r, sx+r, sy+r, fill=fill, outline="black")
            else:
                self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill=fill, outline="black")
            
            lbl = d.get('label', '')
            font_size = max(8, int(10 * self.zoom))
            self.canvas.create_text(sx, sy, text=lbl, font=("Arial", font_size, "bold"))

    def on_zoom(self, event, direction=None):
        if direction is None:
            factor = 1.1 if event.delta > 0 else 0.9
        else:
            factor = 1.1 if direction > 0 else 0.9
        self.zoom *= factor
        self.redraw()

    def on_mouse_down(self, event):
        mx, my = event.x, event.y
        clicked_node = None
        r_screen = self.node_radius * self.zoom
        for n, d in self.G.nodes(data=True):
            wx, wy = d.get('pos', (0,0))
            sx, sy = self.to_screen(wx, wy)
            if math.hypot(mx-sx, my-sy) <= r_screen:
                clicked_node = n; break
        
        if clicked_node is not None:
            self.drag_mode = "NODE"; self.drag_data = clicked_node
            label = self.G.nodes[clicked_node].get('label', '')
            if self.click_callback: self.click_callback(label)
        else:
            self.drag_mode = "PAN"; self.drag_data = (mx, my)

    def on_mouse_drag(self, event):
        mx, my = event.x, event.y
        if self.drag_mode == "NODE":
            wx, wy = self.to_world(mx, my)
            self.G.nodes[self.drag_data]['pos'] = (wx, wy)
            self.redraw()
            if self.redraw_callback: self.redraw_callback()
        elif self.drag_mode == "PAN":
            start_x, start_y = self.drag_data
            dx = mx - start_x; dy = my - start_y
            self.offset_x += dx; self.offset_y += dy
            self.drag_data = (mx, my)
            self.redraw()

    def on_mouse_up(self, event):
        self.drag_mode = None; self.drag_data = None