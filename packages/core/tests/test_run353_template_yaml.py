"""
RUN-353 — Red tests: Research & Review template YAML parses correctly.

These tests verify the hello-world template YAML (the same string that the
frontend stores as TEMPLATE_YAML) can be parsed by ``parse_workflow_yaml``
and produces the expected Workflow structure:
  - 3 blocks: research (LinearBlock), write_summary (LinearBlock),
              quality_review (GateBlock)
  - 3 souls resolved: researcher, writer, reviewer
  - entry block: research
  - transitions: research -> write_summary, write_summary -> quality_review
  - GateBlock eval_key: write_summary

Expected failures: These should all pass once the template and parser
are compatible. The template YAML is hardcoded here (same as the ticket spec).
"""

from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.linear import LinearBlock
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Template YAML — identical to the TEMPLATE_YAML frontend constant (from ticket)
# ---------------------------------------------------------------------------

TEMPLATE_YAML = """\
version: '1.0'
souls:
  researcher:
    id: researcher_1
    role: Senior Researcher
    system_prompt: >
      You are an expert researcher. Given a topic, provide a concise,
      well-structured summary of the key findings, trends, and insights.
      Cite sources where possible. Be thorough but concise.
  writer:
    id: writer_1
    role: Summary Writer
    system_prompt: >
      You are a skilled technical writer. Take research findings and
      transform them into a polished, readable summary. Structure your
      output with clear sections, highlights, and a conclusion.
      Keep the summary under 500 words.
  reviewer:
    id: reviewer_1
    role: Quality Reviewer
    system_prompt: >
      Evaluate if the content meets quality standards. Check for accuracy,
      completeness, and clarity. Provide specific feedback.
blocks:
  research:
    type: linear
    soul_ref: researcher
  write_summary:
    type: linear
    soul_ref: writer
  quality_review:
    type: gate
    soul_ref: reviewer
    eval_key: write_summary
workflow:
  name: Research & Review
  entry: research
  transitions:
    - from: research
      to: write_summary
    - from: write_summary
      to: quality_review
"""


# ---------------------------------------------------------------------------
# 1. Template YAML parses without errors
# ---------------------------------------------------------------------------


class TestTemplateYamlParses:
    def test_parse_returns_workflow(self):
        """parse_workflow_yaml must return a Workflow instance."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        assert isinstance(wf, Workflow)

    def test_workflow_name(self):
        """Parsed workflow name matches the template."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        assert wf.name == "Research & Review"


# ---------------------------------------------------------------------------
# 2. Blocks
# ---------------------------------------------------------------------------


class TestTemplateBlocks:
    def test_has_exactly_3_blocks(self):
        """Template defines exactly 3 blocks."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        assert len(wf.blocks) == 3

    def test_block_ids(self):
        """Block IDs match the template definition."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        assert set(wf.blocks.keys()) == {"research", "write_summary", "quality_review"}

    def test_research_is_linear_block(self):
        """research block is a LinearBlock."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        assert isinstance(wf.blocks["research"], LinearBlock)

    def test_write_summary_is_linear_block(self):
        """write_summary block is a LinearBlock."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        assert isinstance(wf.blocks["write_summary"], LinearBlock)

    def test_quality_review_is_gate_block(self):
        """quality_review block is a GateBlock."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        assert isinstance(wf.blocks["quality_review"], GateBlock)


# ---------------------------------------------------------------------------
# 3. Soul references
# ---------------------------------------------------------------------------


class TestTemplateSouls:
    def test_research_block_soul_ref(self):
        """research block should reference the researcher soul."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        block = wf.blocks["research"]
        assert isinstance(block, LinearBlock)
        assert block.soul.id == "researcher_1"
        assert block.soul.role == "Senior Researcher"

    def test_write_summary_block_soul_ref(self):
        """write_summary block should reference the writer soul."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        block = wf.blocks["write_summary"]
        assert isinstance(block, LinearBlock)
        assert block.soul.id == "writer_1"
        assert block.soul.role == "Summary Writer"

    def test_quality_review_block_soul_ref(self):
        """quality_review gate should reference the reviewer soul."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        block = wf.blocks["quality_review"]
        assert isinstance(block, GateBlock)
        assert block.gate_soul.id == "reviewer_1"
        assert block.gate_soul.role == "Quality Reviewer"


# ---------------------------------------------------------------------------
# 4. Workflow structure
# ---------------------------------------------------------------------------


class TestTemplateWorkflowStructure:
    def test_entry_block_is_research(self):
        """Workflow entry block should be 'research'."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        assert wf._entry_block_id == "research"

    def test_transition_research_to_write_summary(self):
        """Transition: research -> write_summary."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        assert wf._transitions.get("research") == "write_summary"

    def test_transition_write_summary_to_quality_review(self):
        """Transition: write_summary -> quality_review."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        assert wf._transitions.get("write_summary") == "quality_review"

    def test_exactly_two_transitions(self):
        """Template has exactly 2 plain transitions."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        assert len(wf._transitions) == 2


# ---------------------------------------------------------------------------
# 5. Gate block specifics
# ---------------------------------------------------------------------------


class TestTemplateGateBlock:
    def test_gate_eval_key_is_write_summary(self):
        """GateBlock eval_key must point to write_summary output."""
        wf = parse_workflow_yaml(TEMPLATE_YAML)
        gate = wf.blocks["quality_review"]
        assert isinstance(gate, GateBlock)
        assert gate.eval_key == "write_summary"
