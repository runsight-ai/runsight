from typing import Dict, Any


class RunObserver:
    def __init__(self):
        self.subscribers = []

    def subscribe(self, callback):
        self.subscribers.append(callback)

    def unsubscribe(self, callback):
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def notify(self, event_type: str, data: Dict[str, Any]):
        event = {"type": event_type, "data": data}
        for callback in self.subscribers:
            try:
                callback(event)
            except Exception as e:
                # Log error but don't stop notifying other subscribers
                print(f"Error in observer callback: {e}")

    # Specific event methods for convenience
    def on_run_started(self, run_id: str):
        self.notify("run_started", {"run_id": run_id})

    def on_node_started(self, run_id: str, node_id: str):
        self.notify("node_started", {"run_id": run_id, "node_id": node_id})

    def on_node_completed(self, run_id: str, node_id: str, result: Any):
        self.notify("node_completed", {"run_id": run_id, "node_id": node_id, "result": result})

    def on_node_failed(self, run_id: str, node_id: str, error: str):
        self.notify("node_failed", {"run_id": run_id, "node_id": node_id, "error": error})

    def on_run_completed(self, run_id: str):
        self.notify("run_completed", {"run_id": run_id})

    def on_run_failed(self, run_id: str, error: str):
        self.notify("run_failed", {"run_id": run_id, "error": error})
