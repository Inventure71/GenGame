# Core Conflict (GenGame)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Pygame](https://img.shields.io/badge/pygame-2.0+-green.svg)](https://www.pygame.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Core Conflict is a modular, multiplayer battle arena framework built with Python and Pygame. It distinguishes itself through real-time code synchronization and an integrated AI agent system capable of dynamic content generation and collaborative feature merging.

---

## Technical Innovation: Collaborative AI Evolution

The core innovation of this project is its integrated Large Language Model (LLM) agent and its decentralized patch management system. This architecture allows the game to evolve programmatically based on user input during live sessions.

### Integrated AI Agent
The system includes a specialized agent (supporting Gemini and OpenAI models) that facilitates rapid prototyping and deployment:
- **Natural Language Implementation:** Users can describe new gameplay mechanics or balance adjustments in plain English. The agent analyzes the existing codebase and generates functional Python code.
- **Automated Validation:** Every generated feature undergoes automated testing via `pytest` to ensure compatibility and stability before being integrated into the active game state.

### Collaborative Patch Merging
The networking architecture functions similarly to a decentralized version control system:
- **Feature Selection:** In a multiplayer lobby, players select individual "patches" (modular code changes) they wish to include in the upcoming session.
- **Server-Side Merging:** Upon game start, the authoritative server collects these patches and performs an iterative merge. If conflicts arise (e.g., multiple patches modifying the same logic), the AI agent is invoked to resolve them and synthesize a unified version of the game.
- **Real-Time Synchronization:** The resulting merged codebase is instantly synchronized to all connected clients, ensuring a consistent and unique gameplay experience for every session.

---

## Gameplay Overview

Core Conflict features a fast-paced arena environment where players control characters ("Cows") with the objective of being the last remaining participant within a shrinking safe zone.

### Mechanics
- **Movement and Combat:** Supports standard directional movement, dashing, and primary/passive ability usage.
- **Dynamic Growth:** Characters can consume world objects to increase size and health, which also grants additional ability charges.
- **Environment:** A shrinking boundary damages players outside the safe zone, forcing engagement as the session progresses.

---

## Getting Started

### Prerequisites
- **Python 3.12+**
- **API Access:** (Optional) An OpenAI or Gemini API key is required to utilize the AI agent and automated patch merging features.

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/GenGame.git
   cd GenGame
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Execution
1. **Start the Authoritative Server:**
   ```bash
   python server.py
   ```
2. **Start the Game Client:**
   ```bash
   python main.py
   ```

---

## Project Architecture

- `main.py`: The entry point for the client-side application and menu system.
- `server.py`: The authoritative server responsible for simulation, physics, and patch distribution.
- `GameFolder/`: The primary directory for game logic (characters, abilities, arenas). This directory is synchronized across the network.
- `BASE_files/` & `BASE_components/`: The underlying framework providing networking primitives, UI components, and base class definitions.
- `coding/`: Contains the AI agent logic, toolsets, and model handlers.
- `visual_logger/`: A diagnostic toolset for monitoring agent actions and game events.