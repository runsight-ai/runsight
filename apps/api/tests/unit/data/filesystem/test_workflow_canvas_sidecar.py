import logging
from pathlib import Path

from runsight_api.data.filesystem.workflow_canvas_sidecar import read_canvas_sidecar


def test_read_canvas_sidecar_rejects_non_object_json(
    tmp_path: Path,
    caplog,
) -> None:
    path = tmp_path / "wf.canvas.json"
    path.write_text('["not", "an", "object"]', encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        result = read_canvas_sidecar(path)

    assert result is None
    assert any("JSON root must be an object" in record.message for record in caplog.records)
