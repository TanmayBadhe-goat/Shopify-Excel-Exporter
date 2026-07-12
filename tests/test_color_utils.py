"""
Tests for color_utils.py — color name resolution and hex matching.
"""

import pytest
from src.color_utils import (
    hex_to_rgb,
    get_closest_color,
    resolve_color,
    BASE_COLORS,
)


class TestHexToRgb:
    def test_6_digit_hex(self):
        assert hex_to_rgb("#FF0000") == (255, 0, 0)

    def test_3_digit_hex(self):
        assert hex_to_rgb("#F00") == (255, 0, 0)

    def test_lowercase_hex(self):
        assert hex_to_rgb("#00ff00") == (0, 255, 0)

    def test_without_hash(self):
        # Should still work without hash
        result = hex_to_rgb("0000FF")
        assert result == (0, 0, 255)

    def test_invalid_hex(self):
        assert hex_to_rgb("#GGG") is None

    def test_empty_string(self):
        assert hex_to_rgb("") is None

    def test_none_input(self):
        assert hex_to_rgb(None) is None
        assert hex_to_rgb("") is None

    def test_white(self):
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)


class TestGetClosestColor:
    def test_exact_red(self):
        assert get_closest_color("#FF0000") == "Red"

    def test_exact_blue(self):
        assert get_closest_color("#0000FF") == "Blue"

    def test_near_red(self):
        assert get_closest_color("#FF1111") == "Red"

    def test_dark_blue(self):
        assert get_closest_color("#000080") == "Navy"

    def test_invalid_returns_input(self):
        assert get_closest_color("not-a-color") == "not-a-color"

    def test_empty_string(self):
        assert get_closest_color("") == ""


class TestResolveColor:
    def test_hex_red(self):
        assert resolve_color("#FF0000") == "Red"

    def test_hex_green(self):
        assert resolve_color("#00FF00") == "Lime"

    def test_hex_blue(self):
        assert resolve_color("#0000FF") == "Blue"

    def test_named_color(self):
        assert resolve_color("Red") == "Red"

    def test_named_color_lowercase(self):
        assert resolve_color("red") == "Red"

    def test_mixed_case(self):
        assert resolve_color("RED") == "Red"

    def test_navy_blue_simplifies_to_navy(self):
        assert resolve_color("Navy Blue") == "Navy"

    def test_light_blue_strips_modifier(self):
        assert resolve_color("Light Blue") == "Blue"

    def test_dark_green_strips_modifier(self):
        assert resolve_color("Dark Green") == "Green"

    def test_very_dark_red_strips_modifier(self):
        assert resolve_color("Very Dark Red") == "Red"

    def test_bright_pink(self):
        assert resolve_color("Bright Pink") == "Pink"

    def test_empty_string(self):
        assert resolve_color("") == ""

    def test_none(self):
        assert resolve_color(None) == ""

    def test_hex_with_junk(self):
        result = resolve_color("Color: #FF0000")
        assert result == "Red"

    def test_all_base_colors_resolve_to_themselves(self):
        for name in BASE_COLORS:
            assert resolve_color(name) == name, f"{name} should resolve to itself"

    def test_unknown_color_preserved(self):
        result = resolve_color("MagentaFantasy")
        # Should either match a base color or return the title-cased input
        assert isinstance(result, str) and len(result) > 0
