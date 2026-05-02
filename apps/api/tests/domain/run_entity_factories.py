from sqlmodel import SQLModel, create_engine

EXPLICIT_BRANCH = "sim/test/20260330/abc12"


def make_run(*, branch: str = EXPLICIT_BRANCH, **overrides):
    from runsight_api.domain.entities.run import Run

    defaults = {
        "id": "run-data-model",
        "workflow_id": "workflow-data-model",
        "workflow_name": "Data model workflow",
        "task_json": '{"instruction": "summarize research notes"}',
        "branch": branch,
    }
    defaults.update(overrides)
    return Run(**defaults)


def in_memory_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine
