import tkinter as tk
import math

class InteractiveComparisonPanel:
    """
    A standalone viewport for comparing system architectures side-by-side.
    Supports node manipulation, viewport panning, and multi-agent rendering.
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
        self.highlights = []

        self.outer = tk.Frame(parent, bd=2, relief=tk.GROOVE)
        self.outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(self.outer, text=name, font=("Arial", 13, "bold"), bg="#ddd").pack(fill=tk.X)
        self.canvas = tk.Canvas(self.outer, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Interaction Bindings
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<MouseWheel>", self.on_zoom)      
        self.canvas.bind("<Button-4>", lambda e: self.on_zoom(e, 1))  
        self.canvas.bind("<Button-5>", lambda e: self.on_zoom(e, -1)) 
        self.canvas.bind("<Configure>", self.on_resize)

    def set_highlights(self, highlights):
        self.highlights = highlights
        self.redraw()

    def on_resize(self, event):
        """Handle initial viewport centering on first render."""
        if not self.initialized:
            self.center_view(event.width, event.height)
            self.initialized = True
        self.redraw()

    def center_view(self, width, height):
        if self.G.number_of_nodes() == 0: return
        xs = [d.get('pos', (0,0))[0] for n, d in self.G.nodes(data=True)]
        ys = [d.get('pos', (0,0))[1] for n, d in self.G.nodes(data=True)]
        if not xs: return
        
        graph_cx = (min(xs) + max(xs)) / 2
        graph_cy = (min(ys) + max(ys)) / 2
        
        self.offset_x = (width / 2) - (graph_cx * self.zoom)
        self.offset_y = (height / 2) - (graph_cy * self.zoom)

    def to_screen(self, wx, wy):
        return (wx * self.zoom) + self.offset_x, (wy * self.zoom) + self.offset_y

    def to_world(self, sx, sy):
        return (sx - self.offset_x) / self.zoom, (sy - self.offset_y) / self.zoom

    def redraw(self):
        self.canvas.delete("all")
        r = self.node_radius * self.zoom 
        
        # 1. Highlights (Cycles, Modularity, etc.)
        if self.highlights:
            edge_counts = {}
            for h in self.highlights:
                color = h.get('color', 'yellow')
                width = h.get('width', 8) * self.zoom
                
                for n in h.get('nodes', []):
                    wx, wy = self.G.nodes[n].get('pos', (0,0))
                    sx, sy = self.to_screen(wx, wy)
                    self.canvas.create_oval(sx-(r+width/2), sy-(r+width/2), 
                                          sx+(r+width/2), sy+(r+width/2), fill=color, outline=color)

                for u, v in h.get('edges', []):
                    edge_key = tuple(sorted((u, v)))
                    count = edge_counts.get(edge_key, 0)
                    edge_counts[edge_key] = count + 1
                    
                    p1, p2 = self.G.nodes[u].get('pos', (0,0)), self.G.nodes[v].get('pos', (0,0))
                    sx1, sy1 = self.to_screen(p1[0], p1[1])
                    sx2, sy2 = self.to_screen(p2[0], p2[1])
                    
                    dx, dy = sx2 - sx1, sy2 - sy1
                    length = math.hypot(dx, dy)
                    if length == 0: continue
                    
                    nx, ny = -dy / length, dx / length
                    os_x, os_y = nx * ((count * width) - width/2), ny * ((count * width) - width/2)
                    
                    self.canvas.create_line(sx1+os_x, sy1+os_y, sx2+os_x, sy2+os_y, 
                                          fill=color, width=width, capstyle=tk.ROUND)

        # 2. Standard Edges
        for u, v in self.G.edges():
            p1, p2 = self.G.nodes[u].get('pos', (0,0)), self.G.nodes[v].get('pos', (0,0))
            sx1, sy1 = self.to_screen(p1[0], p1[1])
            sx2, sy2 = self.to_screen(p2[0], p2[1])
            self.canvas.create_line(sx1, sy1, sx2, sy2, arrow=tk.LAST, width=2*self.zoom)

        # 3. Standard Nodes
        for n, d in self.G.nodes(data=True):
            wx, wy = d.get('pos', (0,0))
            sx, sy = self.to_screen(wx, wy)
            
            # Shared Authority Rendering logic
            ag_list = d.get('agent', ["Unassigned"])
            if not isinstance(ag_list, list): ag_list = [ag_list]

            if d.get('type') == "Function":
                self._draw_split_rect(sx, sy, r, ag_list)
            else:
                self._draw_split_circle(sx, sy, r, ag_list)
            
            lbl = d.get('label', '')
            font_size = max(15, int(10 * self.zoom))
            self.canvas.create_text(sx, sy-(r + 5*self.zoom), text=lbl, font=("Arial", font_size, "bold"), anchor="s")

    def _draw_split_rect(self, sx, sy, r, agents):
        strip_w = (r * 2) / len(agents)
        for i, ag in enumerate(agents):
            fill = self.agents.get(ag, "white")
            x1 = (sx - r) + (i * strip_w)
            self.canvas.create_rectangle(x1, sy-r, x1+strip_w, sy+r, fill=fill, outline="")
        self.canvas.create_rectangle(sx-r, sy-r, sx+r, sy+r, fill="", outline="black")

    def _draw_split_circle(self, sx, sy, r, agents):
        if len(agents) == 1:
            fill = self.agents.get(agents[0], "white")
            self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill=fill, outline="black")
        else:
            extent = 360 / len(agents)
            start = 90
            for ag in agents:
                fill = self.agents.get(ag, "white")
                self.canvas.create_arc(sx-r, sy-r, sx+r, sy+r, start=start, extent=extent, fill=fill, outline="")
                start += extent
            self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill="", outline="black")

    def on_zoom(self, event, direction=None):
        factor = 1.1 if (direction or event.delta) > 0 else 0.9
        self.zoom *= factor
        self.redraw()

    def on_mouse_down(self, event):
        r_screen = self.node_radius * self.zoom
        for n, d in self.G.nodes(data=True):
            wx, wy = d.get('pos', (0,0))
            sx, sy = self.to_screen(wx, wy)
            if math.hypot(event.x-sx, event.y-sy) <= r_screen:
                self.drag_mode, self.drag_data = "NODE", n
                if self.click_callback: self.click_callback(d.get('label', ''))
                return
        
        self.drag_mode, self.drag_data = "PAN", (event.x, event.y)

    def on_mouse_drag(self, event):
        if self.drag_mode == "NODE":
            wx, wy = self.to_world(event.x, event.y)
            self.G.nodes[self.drag_data]['pos'] = (wx, wy)
            self.redraw()
            if self.redraw_callback: self.redraw_callback()
        elif self.drag_mode == "PAN":
            dx, dy = event.x - self.drag_data[0], event.y - self.drag_data[1]
            self.offset_x += dx
            self.offset_y += dy
            self.drag_data = (event.x, event.y)
            self.redraw()

    def on_mouse_up(self, event):
        self.drag_mode = self.drag_data = None

class CreateToolTip:
    """Standard hovering tooltip for UI elements."""
    def __init__(self, widget, text='info'):
        self.widget = widget
        self.text = text
        self.tw = None
        self.widget.bind("<Enter>", lambda e: self.widget.after(500, self.showtip))
        self.widget.bind("<Leave>", self.hidetip)

    def showtip(self, event=None):
        if not self.text: return
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tw, text=self.text, justify='left', background="#ffffe0", 
                 relief='solid', borderwidth=1, font=("tahoma", "8")).pack(ipadx=1)

    def hidetip(self, event=None):
        if self.tw: self.tw.destroy()
        self.tw = None