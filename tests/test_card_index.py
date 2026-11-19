from card_index import labels_from_onclicks, parse_cards, read_labels, write_labels

LABELS = [
    "833-AFDRE13200-not_resizable_PR-0.00-01",
    "833-AFDRE13200-not_resizable_RD-0.00-01",
    "833-AFDRE45204-round-1.00-00",
    "833-AFDRE11200-round-1.50-00",
    "833-AFDR4300_AFDR4301-not_resizable_NA-0.00-01",
    "900-OTHER-round-1.50-00",
    "garbage",
]


def test_fixed_and_round_lookup_is_case_insensitive():
    c = parse_cards(LABELS)
    assert c.fixed_card("afdre13200", "pr") == "833-AFDRE13200-not_resizable_PR-0.00-01"
    assert c.round_card("AFDRE45204") == "833-AFDRE45204-round-1.00-00"
    assert c.round_card("afdre11200") == "833-AFDRE11200-round-1.50-00"
    assert c.fixed_card("AFDRE13200", "ED") is None
    assert c.round_card("AFDRE13200") is None


def test_has_sku_and_has_fixed():
    c = parse_cards(LABELS)
    assert c.has_sku("AFDRE13200") and c.has_fixed("AFDRE13200")
    assert c.has_sku("AFDRE45204") and not c.has_fixed("AFDRE45204")
    assert not c.has_sku("AFDRE14600CR")


def test_pair_cards_are_not_indexed_under_a_single_sku():
    c = parse_cards(LABELS)
    assert not c.has_sku("AFDR4300") and not c.has_sku("AFDR4301")


def test_other_prefix_and_garbage_are_ignored():
    c = parse_cards(LABELS)
    assert not c.has_sku("OTHER")
    assert parse_cards(LABELS, prefix="900").round_card("OTHER") == "900-OTHER-round-1.50-00"


def test_labels_from_onclicks_extracts_strips_glb_and_dedupes():
    clicks = [
        "Go('833-AFDRE45204-round-1.00-00.glb')",
        "Go('833-AFDRE45204-round-1.00-00.glb')",
        "Go('833-AFDRE13200-not_resizable_PR-0.00-01.glb')",
        "nonsense",
        None,
    ]
    assert labels_from_onclicks(clicks) == [
        "833-AFDRE45204-round-1.00-00",
        "833-AFDRE13200-not_resizable_PR-0.00-01",
    ]


def test_labels_json_roundtrip(tmp_path):
    p = tmp_path / "cards.json"
    write_labels(p, LABELS)
    assert read_labels(p) == LABELS


def test_real_page_labels_use_uppercase_ROUND_and_must_still_be_indexed():
    c = parse_cards(["833-AFDRE45204-ROUND-1.00-00", "833-AFDRE11200-ROUND-1.50-00"])
    assert c.round_card("afdre45204") == "833-AFDRE45204-ROUND-1.00-00"
    assert c.has_sku("AFDRE11200") and not c.has_fixed("AFDRE11200")
