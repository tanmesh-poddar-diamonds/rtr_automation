import openpyxl
import pytest

from card_index import parse_cards, write_labels
from make_rings_csv import CARATS, build_all, format_report, load_skus, main, plan_rows
from rings_csv import read_rings

SHAPE_COLS = ["round", "princess", "cushion", "emerald", "heart", "marquise",
              "radiant", "pear", "oval", "asscher"]
HEADER = ["sn", "main_sku", "color", "kt", "is_rtr_resizable"] + SHAPE_COLS

LABELS = [
    "833-R1-round-1.50-00",
    "833-F1-not_resizable_RD-0.00-01",
    "833-F1-not_resizable_PR-0.00-01",
    "833-ONLY-round-1.00-00",
    "833-RF-not_resizable_PR-0.00-01",
]

# (sku, is_rtr_resizable, viable shape columns)
RECORDS = [
    ("R1", 1, {"round", "cushion"}),
    ("F1", 0, {"round", "pear", "oval"}),
    ("ONLY", 0, {"round", "heart"}),
    ("X1CR", 0, {"round"}),
    ("RF", 1, {"pear", "round"}),
]


def make_xlsx(path, records=RECORDS, variants=3, header=HEADER):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(header)
    n = 0
    for sku, rtr, flags in records:
        for v in range(variants):
            n += 1
            row = {"sn": n, "main_sku": sku, "color": ["white", "yellow", "rose"][v % 3],
                   "kt": "14kt", "is_rtr_resizable": rtr}
            row.update({c: 1 if c in flags else 0 for c in SHAPE_COLS})
            ws.append([row.get(h) for h in header])
    wb.save(path)


def test_load_skus_collapses_metal_variants(tmp_path):
    x = tmp_path / "p.xlsx"
    make_xlsx(x)
    recs = load_skus(x)
    assert [r["main_sku"] for r in recs] == ["R1", "F1", "ONLY", "X1CR", "RF"]
    assert recs[0]["is_rtr_resizable"] == 1 and recs[0]["cushion"] == 1


def test_load_skus_missing_column_raises(tmp_path):
    x = tmp_path / "p.xlsx"
    make_xlsx(x, header=[h for h in HEADER if h != "pear"])
    with pytest.raises(ValueError, match="pear"):
        load_skus(x)


def test_resizable_sku_gets_every_carat_for_each_shape_with_cushion_split(tmp_path):
    x = tmp_path / "p.xlsx"
    make_xlsx(x)
    rec = load_skus(x)[0]
    rows, skips = plan_rows(rec, parse_cards(LABELS))
    assert skips == []
    assert {r.shape for r in rows} == {"Round", "Squarecushion", "Widecushion2"}
    assert len(rows) == 3 * len(CARATS)
    assert {r.carat for r in rows if r.shape == "Round"} == {
        "0.5", "1", "1.5", "2", "2.5", "3", "5", "10", "15", "20"}
    assert {r.card for r in rows} == {"833-R1-round-1.50-00"}


def test_fixed_sku_gets_one_row_per_shape_at_1_5_with_its_own_card(tmp_path):
    x = tmp_path / "p.xlsx"
    make_xlsx(x)
    rec = load_skus(x)[1]
    rows, skips = plan_rows(rec, parse_cards(LABELS))
    assert [(r.shape, r.carat, r.card) for r in rows] == [
        ("Round", "1.5", "833-F1-not_resizable_RD-0.00-01"),
        ("Pear", "1.5", "833-F1-not_resizable_PR-0.00-01"),
    ]
    assert [(s.shape, s.reason) for s in skips] == [("Oval", "no card for this shape")]


def test_fixed_sku_with_only_a_round_card_uses_it_for_every_shape(tmp_path):
    x = tmp_path / "p.xlsx"
    make_xlsx(x)
    rec = load_skus(x)[2]
    rows, skips = plan_rows(rec, parse_cards(LABELS))
    assert skips == []
    assert [(r.shape, r.carat, r.card) for r in rows] == [
        ("Round", "1.5", "833-ONLY-round-1.00-00"),
        ("Heart", "1.5", "833-ONLY-round-1.00-00"),
    ]


def test_sku_with_no_card_is_skipped_with_reason(tmp_path):
    x = tmp_path / "p.xlsx"
    make_xlsx(x)
    rows, skips = plan_rows(load_skus(x)[3], parse_cards(LABELS))
    assert rows == [] and [(s.sku, s.reason) for s in skips] == [("X1CR", "no card on page")]


def test_resizable_sku_without_round_card_falls_back_to_fixed_card_per_shape(tmp_path):
    x = tmp_path / "p.xlsx"
    make_xlsx(x)
    rows, skips = plan_rows(load_skus(x)[4], parse_cards(LABELS))
    assert {r.shape for r in rows} == {"Pear"} and len(rows) == len(CARATS)
    assert {r.card for r in rows} == {"833-RF-not_resizable_PR-0.00-01"}
    assert [(s.shape, s.reason) for s in skips] == [("Round", "no card for this shape")]


def test_report_counts_and_skips(tmp_path):
    x = tmp_path / "p.xlsx"
    make_xlsx(x)
    rows, skips, stats = build_all(load_skus(x), parse_cards(LABELS))
    text = format_report(stats, rows, skips)
    assert "SKUs read: 5 (resizable 2, fixed 3)" in text
    assert f"Rows written: {len(rows)}" in text and "Skipped: 3" in text
    assert "no card on page (1): X1CR" in text
    assert "no card for this shape (2)" in text


def test_main_writes_csv_accepted_by_the_runner_parser_and_a_report(tmp_path):
    x = tmp_path / "p.xlsx"
    make_xlsx(x)
    cards = tmp_path / "cards.json"
    write_labels(cards, LABELS)
    out, rep = tmp_path / "rings.csv", tmp_path / "rep.txt"
    code = main(["--xlsx", str(x), "--cards-file", str(cards), "--out", str(out), "--report", str(rep)])
    assert code == 0
    rings, errors = read_rings(out)
    assert errors == []
    assert len(rings) == 30 + 2 + 2 + 10
    assert len({r.key for r in rings}) == len(rings)
    assert "Rows written: 44" in rep.read_text(encoding="utf-8")


def test_main_limit_skus(tmp_path):
    x = tmp_path / "p.xlsx"
    make_xlsx(x)
    cards = tmp_path / "cards.json"
    write_labels(cards, LABELS)
    out = tmp_path / "rings.csv"
    main(["--xlsx", str(x), "--cards-file", str(cards), "--out", str(out),
          "--report", str(tmp_path / "r.txt"), "--limit-skus", "1"])
    rings, _ = read_rings(out)
    assert {r.sku for r in rings} == {"R1"}


def test_error_leaves_an_existing_csv_untouched(tmp_path):
    x = tmp_path / "p.xlsx"
    make_xlsx(x, header=[h for h in HEADER if h != "pear"])
    cards = tmp_path / "cards.json"
    write_labels(cards, LABELS)
    out = tmp_path / "rings.csv"
    out.write_text("sku,shape,carat\nKEEP,Pear,1.5\n", encoding="utf-8")
    code = main(["--xlsx", str(x), "--cards-file", str(cards), "--out", str(out),
                 "--report", str(tmp_path / "r.txt")])
    assert code == 2
    assert out.read_text(encoding="utf-8") == "sku,shape,carat\nKEEP,Pear,1.5\n"
