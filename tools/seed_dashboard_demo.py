#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "runsight.db"


def _run_row(
    run_id: str,
    workflow_id: str,
    workflow_name: str,
    *,
    status: str,
    created_at: float,
    total_cost_usd: float,
    total_tokens: int,
    duration_s: float | None,
    source: str = "manual",
    branch: str = "main",
    started_at: float | None = None,
    completed_at: float | None = None,
) -> tuple:
    updated_at = completed_at or started_at or created_at
    return (
        run_id,
        workflow_id,
        workflow_name,
        status,
        "{}",
        started_at,
        completed_at,
        duration_s,
        total_cost_usd,
        total_tokens,
        None,
        None,
        None,
        created_at,
        updated_at,
        None,
        None,
        branch,
        source,
        None,
    )


def _node_row(
    run_id: str,
    node_id: str,
    *,
    block_type: str = "llm",
    status: str,
    started_at: float | None,
    completed_at: float | None,
    duration_s: float | None,
    cost_usd: float,
    total_tokens: int,
    soul_id: str | None,
    soul_version: str | None,
    eval_score: float | None,
    eval_passed: bool | None,
    created_at: float,
    prompt_hash: str | None = None,
) -> tuple:
    return (
        f"{run_id}:{node_id}",
        run_id,
        node_id,
        block_type,
        status,
        started_at,
        completed_at,
        duration_s,
        cost_usd,
        json.dumps(
            {"prompt": total_tokens // 2, "completion": total_tokens // 2, "total": total_tokens}
        ),
        None,
        None,
        None,
        soul_id,
        "gpt-5.4",
        created_at,
        completed_at or started_at or created_at,
        "results",
        prompt_hash or f"{node_id}:{soul_version or 'na'}",
        soul_version,
        eval_score,
        eval_passed,
        json.dumps({"assertions": [{"name": "default", "passed": bool(eval_passed)}]})
        if eval_passed is not None
        else None,
    )


def main() -> None:
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("delete from runnode where run_id like 'dash_%'")
    cur.execute("delete from logentry where run_id like 'dash_%'")
    cur.execute("delete from run where id like 'dash_%'")

    runs: list[tuple] = []
    nodes: list[tuple] = []

    workflows = {
        "research": ("research-review-lm8pn", "Research & Review"),
        "pipeline": ("mockup_pipeline", "Mockup Pipeline"),
        "review": ("mockup_generate_review", "Generate Review"),
    }

    def add_run(
        run_id: str,
        workflow_key: str,
        *,
        status: str,
        age_hours: float,
        total_cost_usd: float,
        total_tokens: int,
        duration_s: float | None,
        source: str = "manual",
        branch: str = "main",
        started_offset_s: float | None = None,
    ) -> float:
        workflow_id, workflow_name = workflows[workflow_key]
        created_at = now - age_hours * 3600
        started_at = created_at if started_offset_s is None else now - started_offset_s
        completed_at = created_at + duration_s if duration_s is not None else None
        if status in {"pending", "queued"}:
            started_at = None
        if status == "running":
            completed_at = None
            duration_s = None
        runs.append(
            _run_row(
                run_id,
                workflow_id,
                workflow_name,
                status=status,
                created_at=created_at,
                total_cost_usd=total_cost_usd,
                total_tokens=total_tokens,
                duration_s=duration_s,
                source=source,
                branch=branch,
                started_at=started_at,
                completed_at=completed_at,
            )
        )
        return created_at

    def add_node(
        run_id: str,
        node_id: str,
        *,
        created_at: float,
        cost_usd: float,
        total_tokens: int,
        soul_id: str | None,
        soul_version: str | None,
        eval_score: float | None,
        eval_passed: bool | None,
        offset_s: float,
    ) -> None:
        started_at = created_at + offset_s
        completed_at = started_at + 12 if eval_passed is not None else None
        nodes.append(
            _node_row(
                run_id,
                node_id,
                status="completed" if eval_passed is not None else "pending",
                started_at=started_at,
                completed_at=completed_at,
                duration_s=12 if completed_at is not None else None,
                cost_usd=cost_usd,
                total_tokens=total_tokens,
                soul_id=soul_id,
                soul_version=soul_version,
                eval_score=eval_score,
                eval_passed=eval_passed,
                created_at=started_at,
            )
        )

    # Previous 24h window, used for "vs yesterday" deltas.
    prev_1 = add_run(
        "dash_prev_1",
        "research",
        status="completed",
        age_hours=36,
        total_cost_usd=0.15,
        total_tokens=910,
        duration_s=145,
    )
    add_node(
        "dash_prev_1",
        "research",
        created_at=prev_1,
        offset_s=15,
        cost_usd=0.04,
        total_tokens=260,
        soul_id="researcher_1",
        soul_version="sv_research_v1",
        eval_score=0.97,
        eval_passed=True,
    )
    add_node(
        "dash_prev_1",
        "write_summary",
        created_at=prev_1,
        offset_s=52,
        cost_usd=0.05,
        total_tokens=330,
        soul_id="writer_1",
        soul_version="sv_writer_v1",
        eval_score=0.92,
        eval_passed=True,
    )
    add_node(
        "dash_prev_1",
        "quality_review",
        created_at=prev_1,
        offset_s=89,
        cost_usd=0.03,
        total_tokens=180,
        soul_id="reviewer_1",
        soul_version="sv_review_v1",
        eval_score=0.91,
        eval_passed=True,
    )

    prev_2 = add_run(
        "dash_prev_2",
        "pipeline",
        status="completed",
        age_hours=33,
        total_cost_usd=0.12,
        total_tokens=760,
        duration_s=132,
        source="schedule",
    )
    add_node(
        "dash_prev_2",
        "inner_research",
        created_at=prev_2,
        offset_s=20,
        cost_usd=0.03,
        total_tokens=220,
        soul_id="pipeline_researcher",
        soul_version="sv_pipeline_research_v1",
        eval_score=0.94,
        eval_passed=True,
    )
    add_node(
        "dash_prev_2",
        "draft",
        created_at=prev_2,
        offset_s=60,
        cost_usd=0.04,
        total_tokens=270,
        soul_id="pipeline_writer",
        soul_version="sv_pipeline_writer_v1",
        eval_score=0.9,
        eval_passed=True,
    )

    prev_3 = add_run(
        "dash_prev_3",
        "review",
        status="completed",
        age_hours=29,
        total_cost_usd=0.11,
        total_tokens=700,
        duration_s=121,
        source="webhook",
    )
    add_node(
        "dash_prev_3",
        "extract",
        created_at=prev_3,
        offset_s=18,
        cost_usd=0.03,
        total_tokens=210,
        soul_id="review_extract",
        soul_version="sv_review_extract_v1",
        eval_score=0.89,
        eval_passed=True,
    )
    add_node(
        "dash_prev_3",
        "score",
        created_at=prev_3,
        offset_s=58,
        cost_usd=0.03,
        total_tokens=230,
        soul_id="review_score",
        soul_version="sv_review_score_v1",
        eval_score=0.91,
        eval_passed=True,
    )

    prev_4 = add_run(
        "dash_prev_4",
        "research",
        status="completed",
        age_hours=26,
        total_cost_usd=0.14,
        total_tokens=820,
        duration_s=138,
    )
    add_node(
        "dash_prev_4",
        "research",
        created_at=prev_4,
        offset_s=16,
        cost_usd=0.04,
        total_tokens=250,
        soul_id="researcher_1",
        soul_version="sv_research_v1",
        eval_score=0.95,
        eval_passed=True,
    )
    add_node(
        "dash_prev_4",
        "quality_review",
        created_at=prev_4,
        offset_s=71,
        cost_usd=0.03,
        total_tokens=190,
        soul_id="reviewer_1",
        soul_version="sv_review_v1",
        eval_score=0.89,
        eval_passed=True,
    )

    # Current dashboard window.
    cur_1 = add_run(
        "dash_cur_1",
        "research",
        status="completed",
        age_hours=9,
        total_cost_usd=0.26,
        total_tokens=1210,
        duration_s=168,
    )
    add_node(
        "dash_cur_1",
        "research",
        created_at=cur_1,
        offset_s=18,
        cost_usd=0.11,
        total_tokens=340,
        soul_id="researcher_1",
        soul_version="sv_research_v1",
        eval_score=0.36,
        eval_passed=False,
    )
    add_node(
        "dash_cur_1",
        "write_summary",
        created_at=cur_1,
        offset_s=68,
        cost_usd=0.05,
        total_tokens=360,
        soul_id="writer_1",
        soul_version="sv_writer_v2",
        eval_score=0.94,
        eval_passed=True,
    )
    add_node(
        "dash_cur_1",
        "quality_review",
        created_at=cur_1,
        offset_s=110,
        cost_usd=0.03,
        total_tokens=190,
        soul_id="reviewer_1",
        soul_version="sv_review_v1",
        eval_score=0.88,
        eval_passed=True,
    )

    cur_2 = add_run(
        "dash_cur_2",
        "pipeline",
        status="completed",
        age_hours=7,
        total_cost_usd=0.18,
        total_tokens=980,
        duration_s=150,
        source="schedule",
    )
    add_node(
        "dash_cur_2",
        "inner_research",
        created_at=cur_2,
        offset_s=21,
        cost_usd=0.05,
        total_tokens=260,
        soul_id="pipeline_researcher",
        soul_version="sv_pipeline_research_v1",
        eval_score=0.78,
        eval_passed=True,
    )
    add_node(
        "dash_cur_2",
        "draft",
        created_at=cur_2,
        offset_s=67,
        cost_usd=0.04,
        total_tokens=300,
        soul_id="pipeline_writer",
        soul_version="sv_pipeline_writer_v1",
        eval_score=0.89,
        eval_passed=True,
    )

    cur_3 = add_run(
        "dash_cur_3",
        "research",
        status="completed",
        age_hours=5,
        total_cost_usd=0.24,
        total_tokens=1170,
        duration_s=162,
    )
    add_node(
        "dash_cur_3",
        "research",
        created_at=cur_3,
        offset_s=14,
        cost_usd=0.10,
        total_tokens=330,
        soul_id="researcher_1",
        soul_version="sv_research_v1",
        eval_score=0.33,
        eval_passed=False,
    )
    add_node(
        "dash_cur_3",
        "write_summary",
        created_at=cur_3,
        offset_s=58,
        cost_usd=0.07,
        total_tokens=390,
        soul_id="writer_1",
        soul_version="sv_writer_v2",
        eval_score=0.76,
        eval_passed=True,
    )
    add_node(
        "dash_cur_3",
        "quality_review",
        created_at=cur_3,
        offset_s=102,
        cost_usd=0.04,
        total_tokens=210,
        soul_id="reviewer_1",
        soul_version="sv_review_v1",
        eval_score=0.42,
        eval_passed=False,
    )

    cur_4 = add_run(
        "dash_cur_4",
        "review",
        status="completed",
        age_hours=4,
        total_cost_usd=0.17,
        total_tokens=840,
        duration_s=144,
        source="webhook",
    )
    add_node(
        "dash_cur_4",
        "extract",
        created_at=cur_4,
        offset_s=22,
        cost_usd=0.05,
        total_tokens=250,
        soul_id="review_extract",
        soul_version="sv_review_extract_v1",
        eval_score=0.7,
        eval_passed=True,
    )
    add_node(
        "dash_cur_4",
        "score",
        created_at=cur_4,
        offset_s=65,
        cost_usd=0.04,
        total_tokens=260,
        soul_id="review_score",
        soul_version="sv_review_score_v1",
        eval_score=0.78,
        eval_passed=True,
    )

    cur_5 = add_run(
        "dash_cur_5",
        "pipeline",
        status="completed",
        age_hours=3,
        total_cost_usd=0.13,
        total_tokens=690,
        duration_s=118,
        source="schedule",
    )
    add_node(
        "dash_cur_5",
        "inner_research",
        created_at=cur_5,
        offset_s=18,
        cost_usd=0.04,
        total_tokens=240,
        soul_id="pipeline_researcher",
        soul_version="sv_pipeline_research_v1",
        eval_score=0.86,
        eval_passed=True,
    )
    add_node(
        "dash_cur_5",
        "draft",
        created_at=cur_5,
        offset_s=52,
        cost_usd=0.03,
        total_tokens=210,
        soul_id="pipeline_writer",
        soul_version="sv_pipeline_writer_v1",
        eval_score=0.88,
        eval_passed=True,
    )

    cur_6 = add_run(
        "dash_cur_6",
        "research",
        status="completed",
        age_hours=2,
        total_cost_usd=0.16,
        total_tokens=780,
        duration_s=124,
    )
    add_node(
        "dash_cur_6",
        "research",
        created_at=cur_6,
        offset_s=17,
        cost_usd=0.05,
        total_tokens=240,
        soul_id="researcher_1",
        soul_version="sv_research_v1",
        eval_score=0.83,
        eval_passed=True,
    )
    add_node(
        "dash_cur_6",
        "write_summary",
        created_at=cur_6,
        offset_s=57,
        cost_usd=0.04,
        total_tokens=260,
        soul_id="writer_1",
        soul_version="sv_writer_v2",
        eval_score=0.9,
        eval_passed=True,
    )

    cur_7 = add_run(
        "dash_active_1",
        "pipeline",
        status="pending",
        age_hours=0.35,
        total_cost_usd=0.0,
        total_tokens=0,
        duration_s=None,
        source="schedule",
    )
    add_node(
        "dash_active_1",
        "inner_research",
        created_at=cur_7,
        offset_s=0,
        cost_usd=0.0,
        total_tokens=0,
        soul_id="pipeline_researcher",
        soul_version="sv_pipeline_research_v1",
        eval_score=None,
        eval_passed=None,
    )

    cur_8 = add_run(
        "dash_active_2",
        "review",
        status="pending",
        age_hours=0.18,
        total_cost_usd=0.0,
        total_tokens=0,
        duration_s=None,
        source="manual",
    )
    add_node(
        "dash_active_2",
        "extract",
        created_at=cur_8,
        offset_s=0,
        cost_usd=0.0,
        total_tokens=0,
        soul_id="review_extract",
        soul_version="sv_review_extract_v1",
        eval_score=None,
        eval_passed=None,
    )

    sim_1 = add_run(
        "dash_sim_1",
        "pipeline",
        status="pending",
        age_hours=0.12,
        total_cost_usd=0.0,
        total_tokens=0,
        duration_s=None,
        source="simulation",
        branch="sim/mockup_pipeline/demo",
    )
    add_node(
        "dash_sim_1",
        "draft",
        created_at=sim_1,
        offset_s=0,
        cost_usd=0.0,
        total_tokens=0,
        soul_id="pipeline_writer",
        soul_version="sv_pipeline_writer_v1",
        eval_score=None,
        eval_passed=None,
    )

    cur.executemany(
        """
        insert into run (
          id, workflow_id, workflow_name, status, task_json, started_at, completed_at, duration_s,
          total_cost_usd, total_tokens, results_json, error, cancelled_reason, created_at, updated_at,
          error_traceback, workflow_commit_sha, branch, source, commit_sha
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        runs,
    )
    cur.executemany(
        """
        insert into runnode (
          id, run_id, node_id, block_type, status, started_at, completed_at, duration_s, cost_usd,
          tokens, output, error, error_traceback, soul_id, model_name, created_at, updated_at,
          last_phase, prompt_hash, soul_version, eval_score, eval_passed, eval_results
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        nodes,
    )

    conn.commit()
    conn.close()

    print(f"Seeded {len(runs)} runs and {len(nodes)} run nodes into {DB_PATH}")


if __name__ == "__main__":
    main()
