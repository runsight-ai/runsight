from pathlib import Path


class GitService:
    """Small git helper service for dependency wiring and future expansion."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
