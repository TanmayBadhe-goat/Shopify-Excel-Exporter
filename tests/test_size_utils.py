"""
Tests for size_utils.py — size upscaling logic.
"""

import pytest
from src.size_utils import get_next_size, _SIZE_UP


class TestGetNextSize:
    def test_s_to_m(self):
        assert get_next_size("S") == "M"

    def test_m_to_l(self):
        assert get_next_size("M") == "L"

    def test_l_to_xl(self):
        assert get_next_size("L") == "XL"

    def test_xl_to_xxl(self):
        assert get_next_size("XL") == "XXL"

    def test_xxl_to_xxxl(self):
        assert get_next_size("XXL") == "XXXL"

    def test_numeric_40_to_41(self):
        assert get_next_size("40") == "41"

    def test_numeric_20_to_21(self):
        assert get_next_size("20") == "21"

    def test_preserves_lowercase_input(self):
        assert get_next_size("xl") == "xxl"

    def test_preserves_capitalized_input(self):
        assert get_next_size("Xl") == "Xxl"

    def test_uppercase_input(self):
        assert get_next_size("XL") == "XXL"

    def test_unknown_size_returns_original(self):
        assert get_next_size("XXXXS") == "XXXXS"

    def test_empty_string(self):
        assert get_next_size("") == ""

    def test_none(self):
        assert get_next_size(None) is None

    def test_whitespace_stripped(self):
        assert get_next_size(" M ") == "L"

    def test_2xl_to_3xl(self):
        assert get_next_size("2XL") == "3XL"

    def test_3xl_to_4xl(self):
        assert get_next_size("3XL") == "4XL"

    def test_5xl_to_6xl(self):
        assert get_next_size("5XL") == "6XL"

    def test_all_mappings_covered(self):
        """Every key in _SIZE_UP should work when passed to get_next_size."""
        for key in _SIZE_UP:
            result = get_next_size(key)
            assert result == _SIZE_UP[key], f"get_next_size('{key}') should return '{_SIZE_UP[key]}'"

    def test_lowercase_numeric(self):
        assert get_next_size("36") == "37"

    def test_does_not_modify_unknown(self):
        assert get_next_size("ExtraLarge") == "ExtraLarge"

    def test_special_chars(self):
        assert get_next_size("M/L") == "M/L"  # Not a known key
