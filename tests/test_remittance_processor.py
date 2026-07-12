"""
Tests for remittance_processor.py — CSV parsing and column detection.
"""

import pytest
from pathlib import Path
from src.remittance_processor import normalize_header, process_remittance_csv


class TestNormalizeHeader:
    def test_lowercases(self):
        assert normalize_header("Order No") == "orderno"

    def test_removes_spaces(self):
        assert normalize_header("Order Number") == "ordernumber"

    def test_removes_punctuation(self):
        assert normalize_header("Order #") == "order"

    def test_removes_special_chars(self):
        assert normalize_header("Remittance-Amount!") == "remittanceamount"

    def test_already_normalized(self):
        assert normalize_header("orderno") == "orderno"

    def test_empty_string(self):
        assert normalize_header("") == ""

    def test_none(self):
        assert normalize_header(None) == ""

    def test_ordernumber_variants(self):
        assert normalize_header("Order No.") == "orderno"


class TestProcessRemittanceCsv:
    def test_parses_valid_csv(self, remittance_csv_path):
        result = process_remittance_csv(remittance_csv_path)
        assert len(result) == 2
        assert "1001" in result
        assert "1002" in result

    def test_parses_amount(self, remittance_csv_path):
        result = process_remittance_csv(remittance_csv_path)
        assert result["1001"]["amount"] == "150.00"
        assert result["1002"]["amount"] == "75.00"

    def test_parses_date(self, remittance_csv_path):
        result = process_remittance_csv(remittance_csv_path)
        assert result["1001"]["date"] == "2026-06-20"
        assert result["1002"]["date"] == "2026-06-21"

    def test_detects_columns_by_aliases(self, tmp_path):
        """Should detect columns regardless of exact header names."""
        content = (
            "Order #,Price,Payment Date\n"
            "2001,99.99,2026-07-01\n"
        )
        path = tmp_path / "aliases.csv"
        path.write_text(content, encoding="utf-8-sig")
        result = process_remittance_csv(str(path))
        assert "2001" in result
        assert result["2001"]["amount"] == "99.99"

    def test_detects_amount_via_cod_alias(self, tmp_path):
        content = (
            "Order No,COD Amount,Date\n"
            "3001,50.00,2026-07-02\n"
        )
        path = tmp_path / "cod.csv"
        path.write_text(content, encoding="utf-8-sig")
        result = process_remittance_csv(str(path))
        assert result["3001"]["amount"] == "50.00"

    def test_strips_hash_from_order_number(self, tmp_path):
        content = (
            "Order No,Amount,Date\n"
            "#4001,25.00,2026-07-03\n"
        )
        path = tmp_path / "hash.csv"
        path.write_text(content, encoding="utf-8-sig")
        result = process_remittance_csv(str(path))
        assert "4001" in result  # Not "#4001"

    def test_handles_bom_encoding(self, tmp_path):
        """UTF-8 with BOM should be handled."""
        import codecs
        content = "Order No,Amount,Date\n5001,10.00,2026-07-04\n"
        path = tmp_path / "bom.csv"
        with codecs.open(str(path), "w", encoding="utf-8-sig") as f:
            f.write(content)
        result = process_remittance_csv(str(path))
        assert "5001" in result

    def test_empty_file_raises(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8-sig")
        with pytest.raises(ValueError, match="empty"):
            process_remittance_csv(str(path))

    def test_missing_order_column_raises(self, tmp_path):
        content = "Name,Amount,Date\nTest,10.00,2026-07-01\n"
        path = tmp_path / "nocol.csv"
        path.write_text(content, encoding="utf-8-sig")
        with pytest.raises(ValueError, match="Order Number"):
            process_remittance_csv(str(path))

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            process_remittance_csv("/nonexistent/path.csv")

    def test_skips_empty_order_numbers(self, tmp_path):
        content = (
            "Order No,Amount,Date\n"
            ",10.00,2026-07-01\n"
            "6001,20.00,2026-07-02\n"
        )
        path = tmp_path / "skipempty.csv"
        path.write_text(content, encoding="utf-8-sig")
        result = process_remittance_csv(str(path))
        assert "6001" in result
        assert len(result) == 1
