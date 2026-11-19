import re

SHAPES = {
    "Asscher": "AR", "Emerald": "ED", "Oval": "OL", "Pear": "PR",
    "Princess": "PS", "Widecushion2": "WC", "Round": "RD",
    "Radiant": "RT", "Squarecushion": "SC", "Marquise": "MS",
    "Heart": "HT", "Wideradiant": "WR",
}

_BY_LOWER = {name.lower(): (name, code) for name, code in SHAPES.items()}
_SKU_OK = re.compile(r"^[A-Za-z0-9_]+$")


def resolve_shape(name: str) -> tuple[str, str]:
    """Return (canonical panel name, two-letter card code) for a CSV shape value."""
    found = _BY_LOWER.get((name or "").strip().lower())
    if found is None:
        raise ValueError(f"Unknown shape {name!r}; expected one of {sorted(SHAPES)}")
    return found


def build_label(sku: str, shape: str, prefix: str = "833") -> str:
    """Build the ring card label, e.g. 833-AFDRE13200-not_resizable_PR-0.00-01."""
    sku = (sku or "").strip()
    if not _SKU_OK.match(sku):
        raise ValueError(f"Invalid SKU {sku!r}: use letters, digits and underscores only")
    _, code = resolve_shape(shape)
    return f"{prefix}-{sku.upper()}-not_resizable_{code}-0.00-01"
