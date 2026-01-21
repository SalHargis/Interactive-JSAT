# Interactive-JSAT
This is an interactive network modeling tool that allows you to easily create, edit, and compare systems without the use of code! In this software for human factors and cognitive systems engineering applications, you can create graph representations of systems while easily analyzing them with network mathematics.

## Installation

Ensure you have Python installed. You will need the **NetworkX** library for graph calculations.

```bash
pip install networkx
```

## How to Run

### main.py
Navigate to the project directory in your terminal and run the main application file:
python main.py


## File Structure

### app.py
The main entry point. Contains the GUI logic, event listeners (clicks/drags), and visualization engine.
config.py Stores global constants, including layer definitions (JSAT_LAYERS), visual settings (NODE_RADIUS), and default colors.

### utils.py
Handles mathematical calculations for graph metrics (Density, Centrality, Clustering).

### components.py
Contains modular UI elements, specifically the Architecture Comparison window logic.

### config.py
This file serves as the central control panel for the application's settings. It allows you to adjust visualization parameters without modifying the core logic code.

Key settings include:
* **Graph Settings:** Controls visual elements like `NODE_RADIUS` and undo history limits.
* **Layer Definitions:** Defines the specific Y-coordinates (`JSAT_LAYERS`) and render order (`LAYER_ORDER`) for the structured JSAT view.
* **Default Agents:** Sets the initial agent groups available when the app launches.


## Controls & Usage

### Mode Selection
Use the toolbar buttons (Select, Add Func, Connect, etc.) to switch tools.

### Creation
Click on the canvas to add nodes.

### Connection
In Connect mode, click the start node, then the end node.
(Enforces Function ↔ Resource rules)

### Inspection
Click any node to view its layer, agent assignment, and metrics (Centrality, Degree) in the sidebar.

### View Toggle
Switch between Free View (drag anywhere) and JSAT View (auto-organized by layer).
Agents
Create agents in the sidebar and drag nodes into agent groups to assign them.

### Saving & Analysis
Save Network
Exports the current graph state to a .json file.

### Store Architecture
Temporarily saves the current state in RAM to compare against other versions using the Compare Architecture button.
