"""
Runsight YAML parser and auto-discovery engine.
"""


def __getattr__(name: str):
    if name == "parse_workflow_yaml":
        from runsight_core.yaml.parser import parse_workflow_yaml

        return parse_workflow_yaml
    if name == "parse_task_yaml":
        from runsight_core.yaml.parser import parse_task_yaml

        return parse_task_yaml
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["parse_workflow_yaml", "parse_task_yaml"]
