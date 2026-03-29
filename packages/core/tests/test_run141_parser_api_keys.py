"""Red tests for RUN-141: parse_workflow_yaml accepts api_keys dict instead of api_key.

All tests should FAIL until the implementation exists.
"""

from unittest.mock import patch, MagicMock


from runsight_core.yaml.parser import parse_workflow_yaml


MINIMAL_WORKFLOW_YAML = """
workflow:
  name: test-multi-provider
  entry: b1
  transitions:
    - from: b1
      to: null
blocks:
  b1:
    type: linear
    soul_ref: researcher
souls:
  researcher:
    id: researcher_1
    role: Researcher
    system_prompt: You research things.
config: {}
"""

MULTI_SOUL_WORKFLOW_YAML = """
workflow:
  name: multi-soul-test
  entry: research
  transitions:
    - from: research
      to: review
    - from: review
      to: null
blocks:
  research:
    type: linear
    soul_ref: gpt_researcher
  review:
    type: linear
    soul_ref: claude_reviewer
souls:
  gpt_researcher:
    id: gpt_researcher
    role: Researcher
    system_prompt: Research stuff
    model_name: gpt-4o
  claude_reviewer:
    id: claude_reviewer
    role: Reviewer
    system_prompt: Review stuff
    model_name: claude-3-opus-20240229
config:
  model_name: gpt-4o
"""


class TestParserAcceptsApiKeysDict:
    def test_parse_workflow_yaml_accepts_api_keys_kwarg(self):
        """parse_workflow_yaml() accepts api_keys=Dict[str, str] keyword argument."""
        wf = parse_workflow_yaml(
            MINIMAL_WORKFLOW_YAML,
            api_keys={"openai": "sk-openai", "anthropic": "sk-ant"},
        )
        assert wf is not None

    def test_parse_workflow_yaml_api_keys_signature(self):
        """parse_workflow_yaml has api_keys in its signature (not just api_key)."""
        import inspect

        sig = inspect.signature(parse_workflow_yaml)
        assert "api_keys" in sig.parameters, (
            f"Expected 'api_keys' parameter in parse_workflow_yaml signature, "
            f"got: {list(sig.parameters.keys())}"
        )

    def test_runner_created_with_api_keys(self):
        """When api_keys is passed to parse_workflow_yaml, the RunsightTeamRunner gets api_keys."""
        with patch("runsight_core.yaml.parser.RunsightTeamRunner") as MockRunner:
            MockRunner.return_value = MagicMock()
            parse_workflow_yaml(
                MINIMAL_WORKFLOW_YAML,
                api_keys={"openai": "sk-openai", "anthropic": "sk-ant"},
            )
            MockRunner.assert_called_once()
            call_kwargs = MockRunner.call_args.kwargs
            assert "api_keys" in call_kwargs
            assert call_kwargs["api_keys"] == {"openai": "sk-openai", "anthropic": "sk-ant"}

    def test_backward_compat_api_key_string_still_works(self):
        """Legacy api_key='sk-xxx' still works with parse_workflow_yaml."""
        wf = parse_workflow_yaml(MINIMAL_WORKFLOW_YAML, api_key="sk-legacy")
        assert wf is not None

    def test_multi_soul_workflow_with_api_keys(self):
        """A workflow with souls using different providers parses successfully with api_keys."""
        wf = parse_workflow_yaml(
            MULTI_SOUL_WORKFLOW_YAML,
            api_keys={"openai": "sk-openai", "anthropic": "sk-ant"},
        )
        assert wf is not None
        assert wf.name == "multi-soul-test"
