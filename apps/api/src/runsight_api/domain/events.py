from dataclasses import dataclass
from typing import Optional


@dataclass
class RunStarted:
    run_id: str
    timestamp: float


@dataclass
class NodeCompleted:
    run_id: str
    node_id: str
    timestamp: float
    output: Optional[str] = None
    cost_usd: float = 0.0


@dataclass
class NodeFailed:
    run_id: str
    node_id: str
    timestamp: float
    error: str


@dataclass
class RunCompleted:
    run_id: str
    timestamp: float


@dataclass
class RunFailed:
    run_id: str
    timestamp: float
    error: str


@dataclass
class RunCancelled:
    run_id: str
    timestamp: float
    reason: Optional[str] = None
