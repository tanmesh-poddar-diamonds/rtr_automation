import pytest

from rings_csv import fmt_carat, read_rings


def write(tmp_path, text, encoding="utf-8"):
    p = tmp_path / "rings.csv"
    p.write_bytes(text.encode(encoding))
    return p


def test_fmt_carat_normalises():
    assert [fmt_carat(c) for c in ("1.5", "1.50", "10", "0.50")] == ["1.5", "1.5", "10", "0.5"]


def test_valid_rows_without_card_use_constructed_label(tmp_path):
    p = write(tmp_path, "sku,shape,carat\nAFDRE13200,Pear,1.5\nafdre1,round,2\n")
    rings, errors = read_rings(p)
    assert errors == []
    assert rings[0].sku == "AFDRE13200" and rings[0].code == "PR"
    assert rings[0].carat == "1.5"
    assert rings[0].label == "833-AFDRE13200-not_resizable_PR-0.00-01"
    assert rings[0].key == "AFDRE13200_PR_1.5"
    assert rings[1].sku == "AFDRE1" and rings[1].key == "AFDRE1_RD_2"


def test_card_column_overrides_label_and_strips_glb(tmp_path):
    p = write(tmp_path, "sku,shape,carat,card\nAFDRE45204,Pear,1.5,833-AFDRE45204-round-1.00-00.glb\n")
    rings, errors = read_rings(p)
    assert errors == []
    assert rings[0].label == "833-AFDRE45204-round-1.00-00"
    assert rings[0].key == "AFDRE45204_PR_1.5"


def test_card_for_a_different_sku_is_rejected(tmp_path):
    p = write(tmp_path, "sku,shape,carat,card\nAFDRE45204,Pear,1.5,833-OTHER-round-1.00-00\n")
    rings, errors = read_rings(p)
    assert rings == [] and len(errors) == 1 and "card" in errors[0].message.lower()


def test_card_with_bad_characters_is_rejected(tmp_path):
    p = write(tmp_path, "sku,shape,carat,card\nA1,Pear,1.5,../x\n")
    rings, errors = read_rings(p)
    assert rings == [] and "card" in errors[0].message.lower()


def test_excel_bom_mixed_case_headers_blank_lines_and_spaces(tmp_path):
    p = write(tmp_path, "\ufeffSKU, Shape ,Carat\n\n  AFDRE13200 , Pear , 1.5 \n\n", "utf-8")
    rings, errors = read_rings(p)
    assert errors == []
    assert [r.key for r in rings] == ["AFDRE13200_PR_1.5"]
    assert rings[0].carat == "1.5"


def test_missing_column_raises(tmp_path):
    p = write(tmp_path, "sku,shape\nA,Pear\n")
    with pytest.raises(ValueError, match="carat"):
        read_rings(p)


def test_bad_rows_become_errors_with_line_numbers(tmp_path):
    p = write(tmp_path, "sku,shape,carat\n,Pear,1\nA1,Cushion,1\nA2,Pear,abc\nA3,Pear,0\nA4,Pear,1\n")
    rings, errors = read_rings(p)
    assert [r.sku for r in rings] == ["A4"]
    assert [e.line for e in errors] == [2, 3, 4, 5]
    assert "SKU" in errors[0].message
    assert "shape" in errors[1].message.lower()
    assert "carat" in errors[2].message.lower()
    assert "carat" in errors[3].message.lower()


def test_same_sku_and_shape_with_different_carats_are_separate_rings(tmp_path):
    p = write(tmp_path, "sku,shape,carat\nA1,Pear,1.5\nA1,Pear,2\nA1,Round,1.5\n")
    rings, errors = read_rings(p)
    assert errors == []
    assert [r.key for r in rings] == ["A1_PR_1.5", "A1_PR_2", "A1_RD_1.5"]


def test_duplicate_sku_shape_carat_is_rejected_even_if_spelled_differently(tmp_path):
    p = write(tmp_path, "sku,shape,carat\nA1,Pear,1.5\na1,pear,1.50\nA1,Round,1.5\n")
    rings, errors = read_rings(p)
    assert [r.key for r in rings] == ["A1_PR_1.5", "A1_RD_1.5"]
    assert len(errors) == 1 and errors[0].line == 3 and "duplicate" in errors[0].message.lower()
