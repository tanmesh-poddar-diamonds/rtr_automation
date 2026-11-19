import pytest

from shapes import SHAPES, build_label, resolve_shape


def test_table_matches_user_confirmed_mapping():
    assert SHAPES == {
        "Asscher": "AR", "Emerald": "ED", "Oval": "OL", "Pear": "PR",
        "Princess": "PS", "Widecushion2": "WC", "Round": "RD",
        "Radiant": "RT", "Squarecushion": "SC", "Marquise": "MS",
        "Heart": "HT", "Wideradiant": "WR",
    }


def test_resolve_is_case_and_space_insensitive():
    assert resolve_shape("pear") == ("Pear", "PR")
    assert resolve_shape("  WIDECUSHION2 ") == ("Widecushion2", "WC")


def test_unknown_shape_raises():
    with pytest.raises(ValueError, match="Unknown shape"):
        resolve_shape("Cushion")


def test_build_label_exact_format_uppercases_sku():
    assert build_label("afdre13200", "Pear") == "833-AFDRE13200-not_resizable_PR-0.00-01"


def test_build_label_custom_prefix():
    assert build_label("X1", "Round", prefix="900") == "900-X1-not_resizable_RD-0.00-01"


def test_pair_sku_with_underscore_builds_pair_label_exactly():
    assert (build_label("AFDR4300_AFDR4301", "Round")
            == "833-AFDR4300_AFDR4301-not_resizable_RD-0.00-01")


@pytest.mark.parametrize("bad", ["", "  ", "AFD RE", "A-B", "A/B", "../x"])
def test_build_label_rejects_bad_sku(bad):
    with pytest.raises(ValueError, match="Invalid SKU"):
        build_label(bad, "Pear")
