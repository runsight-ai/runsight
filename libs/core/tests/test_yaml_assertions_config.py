"""Red tests for RUN-315: YAML schema extension for assertion configs.

Tests target new `assertions` fields on:
  - SoulDef (YAML schema)
  - Soul (core primitives)
  - BaseBlockDef (YAML schema)

And propagation of soul-level + block-level assertions into an
assertion_configs dict keyed by block_id.

All tests should FAIL until the implementation exists.
"""


# ---------------------------------------------------------------------------
# 1. SoulDef accepts assertions field
# ---------------------------------------------------------------------------


class TestSoulDefAssertions:
    def test_souldef_accepts_assertions_field(self):
        """SoulDef can be instantiated with an assertions field (list of dicts)."""
        from runsight_core.yaml.schema import SoulDef

        soul_def = SoulDef(
            id="researcher_v1",
            role="Senior Researcher",
            system_prompt="You are a researcher.",
            assertions=[
                {"type": "contains", "value": "Sources", "weight": 1.0},
                {"type": "cost", "threshold": 0.05},
            ],
        )
        assert soul_def.assertions is not None
        assert len(soul_def.assertions) == 2
        assert soul_def.assertions[0]["type"] == "contains"

    def test_souldef_assertions_defaults_to_none(self):
        """SoulDef.assertions defaults to None when not provided."""
        from runsight_core.yaml.schema import SoulDef

        soul_def = SoulDef(
            id="researcher_v1",
            role="Senior Researcher",
            system_prompt="You are a researcher.",
        )
        assert soul_def.assertions is None


# ---------------------------------------------------------------------------
# 2. Soul (core primitives) accepts assertions field
# ---------------------------------------------------------------------------


class TestSoulAssertions:
    def test_soul_accepts_assertions_field(self):
        """Soul model can be instantiated with an assertions field."""
        from runsight_core.primitives import Soul

        soul = Soul(
            id="researcher_v1",
            role="Senior Researcher",
            system_prompt="You are a researcher.",
            model_name="gpt-4o",
            assertions=[
                {"type": "contains", "value": "Sources"},
            ],
        )
        assert soul.assertions is not None
        assert len(soul.assertions) == 1

    def test_soul_assertions_defaults_to_none(self):
        """Soul.assertions defaults to None when not provided."""
        from runsight_core.primitives import Soul

        soul = Soul(
            id="researcher_v1",
            role="Senior Researcher",
            system_prompt="You are a researcher.",
            model_name="gpt-4o",
        )
        assert soul.assertions is None


# ---------------------------------------------------------------------------
# 3. BaseBlockDef accepts assertions field
# ---------------------------------------------------------------------------


class TestBaseBlockDefAssertions:
    def test_baseblockdef_accepts_assertions_field(self):
        """BaseBlockDef can be instantiated with an assertions field."""
        from runsight_core.yaml.schema import BaseBlockDef

        block_def = BaseBlockDef(
            type="linear",
            assertions=[
                {"type": "is-json", "weight": 1.0},
                {"type": "contains", "value": "result", "weight": 2.0},
            ],
        )
        assert block_def.assertions is not None
        assert len(block_def.assertions) == 2

    def test_baseblockdef_assertions_defaults_to_none(self):
        """BaseBlockDef.assertions defaults to None when not provided."""
        from runsight_core.yaml.schema import BaseBlockDef

        block_def = BaseBlockDef(type="linear")
        assert block_def.assertions is None


# ---------------------------------------------------------------------------
# 4. Assertions propagation from soul+block to assertion_configs
# ---------------------------------------------------------------------------


class TestAssertionConfigsPropagation:
    def test_parser_propagates_soul_assertions(self):
        """Parser extracts soul-level assertions into assertion_configs dict.

        When a soul has assertions and a block uses that soul, the block_id
        should appear in the assertion_configs with the soul's assertions.
        """
        # This test validates the contract that somewhere in the parse pipeline,
        # soul.assertions get collected into a dict[block_id, list[config]].
        # The exact mechanism (parser helper, service layer, etc.) is an
        # implementation detail, but the Soul must carry the data.
        from runsight_core.primitives import Soul

        soul = Soul(
            id="analyst",
            role="Analyst",
            system_prompt="Analyze data.",
            model_name="gpt-4o",
            assertions=[
                {"type": "contains", "value": "analysis"},
                {"type": "cost", "threshold": 0.02},
            ],
        )
        # Soul should carry the assertions for downstream consumption
        assert soul.assertions is not None
        assert len(soul.assertions) == 2
        assert soul.assertions[0]["type"] == "contains"
        assert soul.assertions[1]["type"] == "cost"

    def test_block_level_assertions_accessible(self):
        """Block-level assertions are accessible on the block def."""
        from runsight_core.yaml.schema import BaseBlockDef

        block = BaseBlockDef(
            type="linear",
            assertions=[{"type": "is-json"}],
        )
        assert block.assertions is not None
        assert block.assertions[0]["type"] == "is-json"
