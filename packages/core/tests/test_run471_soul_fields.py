"""Red tests for RUN-471: add provider/temperature/max_tokens/avatar_color to Soul and SoulDef."""

from runsight_core.primitives import Soul
from runsight_core.yaml.schema import SoulDef


class TestSoulFieldAdditions:
    def test_soul_accepts_new_optional_fields(self):
        soul = Soul(
            id="researcher_1",
            role="Researcher",
            system_prompt="Investigate the problem carefully.",
            provider="openai",
            temperature=0.7,
            max_tokens=4096,
            avatar_color="#44aa88",
        )

        assert soul.provider == "openai"
        assert soul.temperature == 0.7
        assert soul.max_tokens == 4096
        assert soul.avatar_color == "#44aa88"

    def test_soul_new_fields_default_to_none(self):
        soul = Soul(
            id="reviewer_1",
            role="Reviewer",
            system_prompt="Review the draft.",
        )

        assert soul.provider is None
        assert soul.temperature is None
        assert soul.max_tokens is None
        assert soul.avatar_color is None

    def test_soul_temperature_accepts_boundary_values(self):
        cold = Soul(
            id="cold_soul",
            role="Deterministic Agent",
            system_prompt="Be precise.",
            temperature=0.0,
        )
        hot = Soul(
            id="hot_soul",
            role="Creative Agent",
            system_prompt="Be imaginative.",
            temperature=2.0,
        )

        assert cold.temperature == 0.0
        assert hot.temperature == 2.0


class TestSoulDefFieldAdditions:
    def test_souldef_accepts_new_optional_fields(self):
        soul_def = SoulDef(
            id="planner_1",
            role="Planner",
            system_prompt="Plan the work.",
            provider="anthropic",
            temperature=0.5,
            max_tokens=2048,
            avatar_color="hsl(210 60% 50%)",
        )

        assert soul_def.provider == "anthropic"
        assert soul_def.temperature == 0.5
        assert soul_def.max_tokens == 2048
        assert soul_def.avatar_color == "hsl(210 60% 50%)"

    def test_souldef_new_fields_default_to_none(self):
        soul_def = SoulDef(
            id="writer_1",
            role="Writer",
            system_prompt="Write the response.",
        )

        assert soul_def.provider is None
        assert soul_def.temperature is None
        assert soul_def.max_tokens is None
        assert soul_def.avatar_color is None
