"""Translation structure tests for the Home Sweet Home Agent integration."""

from __future__ import annotations

import json
from pathlib import Path

COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "custom_components"
    / "home_sweet_home_agent"
)


def test_english_translation_matches_strings() -> None:
    """The English translation exposes the same config-flow keys as strings.json."""
    strings = json.loads((COMPONENT / "strings.json").read_text())
    translation = json.loads((COMPONENT / "translations" / "en.json").read_text())

    assert strings["config"]["step"]["user"]["data"] == (
        translation["config"]["step"]["user"]["data"]
    )
    assert strings["config"]["error"] == translation["config"]["error"]
    assert strings["config"]["abort"] == translation["config"]["abort"]
