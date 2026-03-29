"""
ArtifactStore ABC and InMemoryArtifactStore for workflow artifact management.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ArtifactStore(ABC):
    """Abstract base class for artifact storage backends."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id

    @abstractmethod
    async def write(
        self, key: str, content: str, *, metadata: Optional[Dict[str, Any]] = None
    ) -> str: ...

    @abstractmethod
    async def read(self, ref: str) -> str: ...

    @abstractmethod
    async def list_artifacts(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def cleanup(self) -> None: ...


class InMemoryArtifactStore(ArtifactStore):
    """In-memory artifact store using mem://{run_id}/{key} refs."""

    def __init__(self, run_id: str) -> None:
        super().__init__(run_id)
        self._content: Dict[str, str] = {}
        self._metadata: Dict[str, Optional[Dict[str, Any]]] = {}

    async def write(
        self, key: str, content: str, *, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        self._content[key] = content
        self._metadata[key] = metadata
        return f"mem://{self.run_id}/{key}"

    async def read(self, ref: str) -> str:
        prefix = f"mem://{self.run_id}/"
        if not ref.startswith(prefix):
            raise KeyError(ref)
        key = ref[len(prefix) :]
        if key not in self._content:
            raise KeyError(ref)
        return self._content[key]

    async def list_artifacts(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": key,
                "ref": f"mem://{self.run_id}/{key}",
                "metadata": self._metadata[key],
            }
            for key in self._content
        ]

    async def cleanup(self) -> None:
        self._content.clear()
        self._metadata.clear()
