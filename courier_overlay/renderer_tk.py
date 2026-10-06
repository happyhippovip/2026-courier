import tkinter as tk
from typing import List
from courier_overlay.layout_engine import LayoutEngine
from courier_overlay.state_machine import WorkerState

class TkinterRenderer:
    def __init__(self, engine: LayoutEngine):
        self.engine = engine
        self.root = tk.Tk()
        self.root.title("Courier Desktop Swarm")
        self.root.geometry("800x600")
        self.canvas = tk.Canvas(self.root, width=800, height=600, bg="black")
        self.canvas.pack(fill="both", expand=True)
        
    def render(self, states: List[WorkerState]):
        self.canvas.delete("all")
        # For simplicity, assign each worker to a grid slot based on its index
        for idx, state in enumerate(states):
            rect = self.engine.calculate_rect(idx)
            
            # Map status to color
            color = "gray"
            if state.status == "WORKING": color = "green"
            elif state.status == "ASSIGNED": color = "yellow"
            elif state.status == "BLOCKED": color = "red"
            
            # Draw window bounds
            self.canvas.create_rectangle(
                rect.x, rect.y, rect.x + rect.width, rect.y + rect.height,
                outline=color, width=2
            )
            
            # Draw task summary
            text_x = rect.x + 10
            text_y = rect.y + 20
            self.canvas.create_text(
                text_x, text_y, text=f"Agent: {state.agent_id}", fill="white", anchor="w"
            )
            if state.current_task:
                self.canvas.create_text(
                    text_x, text_y + 20, text=f"Task: {state.current_task}", fill="white", anchor="w"
                )
            if state.last_summary:
                # Truncate summary to prevent overflow
                summary = state.last_summary[:240]
                self.canvas.create_text(
                    text_x, text_y + 40, text=summary, fill="lightgray", anchor="w"
                )

    def update(self):
        self.root.update_idletasks()
        self.root.update()
