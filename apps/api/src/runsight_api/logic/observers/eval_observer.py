"""EvalObserver: runs assertion configs on block completion, persists eval results."""

import logging
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from runsight_core.assertions.base import AssertionContext, GradingResult
from runsight_core.assertions.registry import NOT_PREFIX, _get_handler
from runsight_core.assertions.scoring import AssertionsResult
from runsight_core.observer import compute_prompt_hash, compute_soul_version
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import RunNode

logger = logging.getLogger(__name__)


def _run_assertion_sync(
    *,
    type: str,
    output: str,
    context: AssertionContext,
    value: Any = "",
    threshold: float | None = None,
    weight: float = 1.0,
) -> GradingResult:
    """Dispatch a single assertion synchronously, forwarding all kwargs to the handler."""
    negated = type.startswith(NOT_PREFIX)
    base_type = type[len(NOT_PREFIX) :] if negated else type

    handler_cls = _get_handler(base_type)
    try:
        handler = handler_cls(value=value, threshold=threshold)
    except TypeError:
        try:
            handler = handler_cls(value=value)
        except TypeError:
            handler = handler_cls()
    result = handler.evaluate(output, context)

    if negated:
        return GradingResult(
            passed=not result.passed,
            score=1.0 - result.score,
            reason=result.reason,
            named_scores=result.named_scores,
            tokens_used=result.tokens_used,
            component_results=result.component_results,
            assertion_type=result.assertion_type,
            metadata=result.metadata,
        )

    return result


def _run_assertions_sync(
    config: List[Dict[str, Any]],
    *,
    output: str,
    context: AssertionContext,
) -> AssertionsResult:
    """Run a list of assertion configs synchronously and return aggregated results."""
    agg = AssertionsResult()
    if not config:
        return agg

    for cfg in config:
        weight = cfg.get("weight", 1.0)
        result = _run_assertion_sync(
            type=cfg["type"],
            output=output,
            context=context,
            value=cfg.get("value", ""),
            threshold=cfg.get("threshold"),
            weight=weight,
        )
        if cfg.get("metric"):
            result.named_scores[cfg["metric"]] = result.score
        agg.add_result(result, weight=weight)

    return agg


class EvalObserver:
    """Implements WorkflowObserver protocol for assertion-based evaluation.

    Runs assertion configs on block completion, persists eval scores on RunNode,
    and emits SSE events with eval results and baseline deltas.

    All methods are defensively wrapped — exceptions are logged, never raised.
    """

    def __init__(
        self,
        *,
        engine: Any,
        run_id: str,
        sse_queue: Any,
        assertion_configs: Dict[str, List[Dict[str, Any]]] | None = None,
    ) -> None:
        self.engine = engine
        self.run_id = run_id
        self.sse_queue = sse_queue
        self.assertion_configs = assertion_configs

    # ------------------------------------------------------------------
    # No-op protocol methods
    # ------------------------------------------------------------------

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        pass

    def on_block_start(
        self, workflow_name: str, block_id: str, block_type: str, *, soul: Optional[Soul] = None
    ) -> None:
        pass

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        pass

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        pass

    # ------------------------------------------------------------------
    # on_block_complete — run assertions, persist, emit SSE
    # ------------------------------------------------------------------

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        *,
        soul: Optional[Soul] = None,
    ) -> None:
        try:
            self._handle_block_complete(
                workflow_name, block_id, block_type, duration_s, state, soul=soul
            )
        except Exception:
            logger.warning("EvalObserver.on_block_complete failed", exc_info=True)

    def _handle_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        *,
        soul: Optional[Soul] = None,
    ) -> None:
        # Early return if no assertions configured for this block
        if not self.assertion_configs:
            return
        block_configs = self.assertion_configs.get(block_id)
        if not block_configs:
            return

        # Ensure deterministic assertion plugins are registered
        import runsight_core.assertions.deterministic  # noqa: F401

        # Extract output from state
        raw_result = state.results.get(block_id)
        output = raw_result.output if isinstance(raw_result, BlockResult) else (raw_result or "")

        # Look up the RunNode for cost/token context
        node: Optional[RunNode] = None
        with Session(self.engine) as session:
            node = session.get(RunNode, f"{self.run_id}:{block_id}")

        node_cost = node.cost_usd if node else 0.0
        node_tokens = (node.tokens or {}).get("total", 0) if node else 0

        # Build assertion context
        context = AssertionContext(
            output=output,
            prompt=soul.system_prompt if soul else "",
            prompt_hash=compute_prompt_hash(soul) or "",
            soul_id=soul.id if soul else "",
            soul_version=compute_soul_version(soul) or "",
            block_id=block_id,
            block_type=block_type,
            cost_usd=node_cost,
            total_tokens=node_tokens,
            latency_ms=duration_s * 1000,
            variables={},
            run_id=self.run_id,
            workflow_id=workflow_name,
        )

        # Run assertions synchronously
        assertion_result = _run_assertions_sync(block_configs, output=output, context=context)
        eval_score = assertion_result.aggregate_score
        eval_passed = assertion_result.passed()

        # Query baseline if soul is available
        baseline = None
        delta = None
        if soul:
            with Session(self.engine) as session:
                repo = RunRepository(session)
                baseline = repo.get_baseline(soul.id, compute_soul_version(soul) or "")

        if baseline:
            delta = {
                "cost_pct": (
                    ((node_cost - baseline.avg_cost) / baseline.avg_cost * 100)
                    if baseline.avg_cost
                    else 0
                ),
                "tokens_pct": (
                    ((node_tokens - baseline.avg_tokens) / baseline.avg_tokens * 100)
                    if baseline.avg_tokens
                    else 0
                ),
                "score_delta": (
                    eval_score - baseline.avg_score if baseline.avg_score is not None else None
                ),
                "baseline_run_count": baseline.run_count,
            }

        # Persist eval results on RunNode
        eval_results_data = {
            "assertions": [
                {
                    "type": r.assertion_type,
                    "passed": r.passed,
                    "score": r.score,
                    "reason": r.reason,
                }
                for r in assertion_result.results
            ],
        }

        with Session(self.engine) as session:
            node = session.get(RunNode, f"{self.run_id}:{block_id}")
            if node:
                node.eval_score = eval_score
                node.eval_passed = eval_passed
                node.eval_results = eval_results_data
                session.add(node)
                session.commit()

        # Emit SSE event
        self.sse_queue.put_nowait(
            {
                "event": "node_eval_complete",
                "data": {
                    "node_id": block_id,
                    "eval_score": eval_score,
                    "passed": eval_passed,
                    "assertions": [
                        {
                            "type": r.assertion_type,
                            "passed": r.passed,
                            "score": r.score,
                            "reason": r.reason,
                        }
                        for r in assertion_result.results
                    ],
                    "delta": delta,
                },
            }
        )

    # ------------------------------------------------------------------
    # on_workflow_complete — compute run-level aggregate
    # ------------------------------------------------------------------

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        try:
            self._handle_workflow_complete(workflow_name, state, duration_s)
        except Exception:
            logger.warning("EvalObserver.on_workflow_complete failed", exc_info=True)

    def _handle_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        with Session(self.engine) as session:
            nodes = list(
                session.exec(
                    select(RunNode).where(
                        RunNode.run_id == self.run_id, RunNode.eval_score.isnot(None)
                    )
                ).all()
            )
            if not nodes:
                return

            avg_score = sum(n.eval_score for n in nodes) / len(nodes)
            logger.info(
                "Run %s eval aggregate: %.3f across %d nodes",
                self.run_id,
                avg_score,
                len(nodes),
            )
