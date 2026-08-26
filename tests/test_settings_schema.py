"""Entity.settings has a shape, so config changes never need code changes."""
import pytest

from core.services.settings_schema import SettingsError, parse


class TestDefaults:
    def test_empty_settings_are_valid(self):
        settings = parse({})
        assert settings.daily_budget_usd > 0
        assert settings.briefing_hour == 8

    def test_exploration_defaults_to_fifteen_percent(self):
        exploration = parse({}).exploration
        assert exploration.total() == pytest.approx(0.15)
        assert exploration.adjacent == pytest.approx(0.07)
        assert exploration.counter == pytest.approx(0.05)
        assert exploration.random == pytest.approx(0.03)

    def test_quota_is_a_floor_not_a_ceiling(self):
        """SPEC 7: a busy day must not push exploration to zero."""
        assert parse({}).exploration.min_briefing_items >= 1

    def test_mesh_is_off_until_enabled(self):
        assert parse({}).mesh.enabled is False


class TestOverrides:
    def test_lane_shares_can_be_retuned_without_code_changes(self):
        settings = parse({"exploration": {"adjacent": 0.15, "counter": 0.05, "random": 0.05}})
        assert settings.exploration.total() == pytest.approx(0.25)

    def test_partial_nested_override_keeps_other_defaults(self):
        settings = parse({"exploration": {"random": 0.10}})
        assert settings.exploration.random == pytest.approx(0.10)
        assert settings.exploration.adjacent == pytest.approx(0.07)


class TestRejection:
    def test_unknown_top_level_key(self):
        with pytest.raises(SettingsError, match="unknown settings key"):
            parse({"daily_budget": 5})

    def test_unknown_nested_key(self):
        with pytest.raises(SettingsError, match="exploration.lane"):
            parse({"exploration": {"lane": "x"}})

    def test_lane_shares_over_one(self):
        with pytest.raises(SettingsError, match="must not exceed"):
            parse({"exploration": {"adjacent": 0.7, "counter": 0.4, "random": 0.1}})

    def test_negative_budget(self):
        with pytest.raises(SettingsError, match="daily_budget_usd"):
            parse({"daily_budget_usd": 0})

    def test_briefing_hour_out_of_range(self):
        with pytest.raises(SettingsError, match="briefing_hour"):
            parse({"briefing_hour": 24})

    def test_zero_exploration_items_while_enabled(self):
        with pytest.raises(SettingsError, match="min_briefing_items"):
            parse({"exploration": {"min_briefing_items": 0}})

    def test_mesh_ratio_out_of_range(self):
        with pytest.raises(SettingsError, match="unrelated_peer_ratio"):
            parse({"mesh": {"unrelated_peer_ratio": 1.5}})
