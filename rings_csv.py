import csv
import re
from dataclasses import dataclass
from pathlib import Path

from shapes import build_label, resolve_shape

REQUIRED = ("sku", "shape", "carat")
_CARD_OK = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class RingRequest:
    sku: str
    shape: str      # canonical panel name, e.g. "Pear"
    code: str       # two-letter code of the requested shape, e.g. "PR"
    carat: str      # exactly as it will be typed into the Carats field
    label: str      # card label opened in the tool (no ".glb")
    key: str        # "<SKU>_<CODE>_<carat>": folder and log-file name
    card: str = ""  # the CSV card value, if one was given


@dataclass(frozen=True)
class RowError:
    line: int
    message: str
    raw: str


def fmt_carat(carat: str) -> str:
    return f"{float(carat):g}"


def read_rings(path: Path | str, prefix: str = "833") -> tuple[list[RingRequest], list[RowError]]:
    rings: list[RingRequest] = []
    errors: list[RowError] = []
    seen: set[str] = set()
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = next(reader, None) or []
        cols = {name.strip().lower(): i for i, name in enumerate(header)}
        missing = [c for c in REQUIRED if c not in cols]
        if missing:
            raise ValueError(f"rings.csv is missing column(s): {', '.join(missing)}")
        for row in reader:
            line = reader.line_num
            if not any(cell.strip() for cell in row):
                continue
            raw = ",".join(row)

            def cell(name: str) -> str:
                i = cols.get(name)
                return row[i].strip() if i is not None and i < len(row) else ""

            sku, shape, carat, card = cell("sku"), cell("shape"), cell("carat"), cell("card")
            try:
                if not sku:
                    raise ValueError("SKU is empty")
                canonical, code = resolve_shape(shape)
                constructed = build_label(sku, canonical, prefix)
                try:
                    if float(carat) <= 0:
                        raise ValueError
                except ValueError:
                    raise ValueError(f"Carat must be a positive number, got {carat!r}") from None
                label = constructed
                if card:
                    card = card.removesuffix(".glb")
                    if not _CARD_OK.match(card):
                        raise ValueError(f"Invalid card {card!r}")
                    if f"-{sku.upper()}-" not in card.upper():
                        raise ValueError(f"Card {card!r} does not belong to SKU {sku.upper()}")
                    label = card
            except ValueError as exc:
                errors.append(RowError(line, str(exc), raw))
                continue
            key = f"{sku.upper()}_{code}_{fmt_carat(carat)}"
            if key in seen:
                errors.append(RowError(line, f"Duplicate row for {key} (same SKU, shape and carat)", raw))
                continue
            seen.add(key)
            rings.append(RingRequest(sku.upper(), canonical, code, carat, label, key, card))
    return rings, errors
