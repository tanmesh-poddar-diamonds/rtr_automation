import argparse
import csv
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import openpyxl
from dotenv import load_dotenv

from card_index import Cards, fetch_labels, parse_cards, read_labels, write_labels
from config import load_config
from shapes import resolve_shape

CARATS = [0.5, 1, 1.5, 2, 2.5, 3, 5, 10, 15, 20]
FIXED_CARAT = 1.5
FLAG_SHAPES = {
    "round": ["Round"],
    "princess": ["Princess"],
    "cushion": ["Squarecushion", "Widecushion2"],
    "emerald": ["Emerald"],
    "heart": ["Heart"],
    "marquise": ["Marquise"],
    "radiant": ["Radiant"],
    "pear": ["Pear"],
    "oval": ["Oval"],
    "asscher": ["Asscher"],
}
REQUIRED = ["main_sku", "is_rtr_resizable", *FLAG_SHAPES]


@dataclass(frozen=True)
class Row:
    sku: str
    shape: str
    carat: str
    card: str


@dataclass(frozen=True)
class Skip:
    sku: str
    shape: str
    reason: str


def fmt_carat(c: float) -> str:
    return f"{c:g}"


def load_skus(path: Path | str) -> list[dict]:
    """One record per main_sku (the first row wins; metal variants share these columns)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        it = wb.active.iter_rows(values_only=True)
        header = next(it, None) or ()
        cols = {str(n).strip(): i for i, n in enumerate(header) if n is not None}
        missing = [c for c in REQUIRED if c not in cols]
        if missing:
            raise ValueError(f"Excel file is missing column(s): {', '.join(missing)}")
        out, seen = [], set()
        for row in it:
            raw = row[cols["main_sku"]]
            sku = str(raw).strip().upper() if raw is not None else ""
            if not sku or sku in seen:
                continue
            seen.add(sku)
            rec = {c: row[cols[c]] for c in REQUIRED}
            rec["main_sku"] = sku
            out.append(rec)
    finally:
        wb.close()
    return out


def plan_rows(rec: dict, cards: Cards) -> tuple[list[Row], list[Skip]]:
    sku = rec["main_sku"]
    if not cards.has_sku(sku):
        return [], [Skip(sku, "", "no card on page")]
    resizable = rec["is_rtr_resizable"] == 1
    carats = CARATS if resizable else [FIXED_CARAT]
    rows: list[Row] = []
    skips: list[Skip] = []
    for flag, names in FLAG_SHAPES.items():
        if rec.get(flag) != 1:
            continue
        for shape in names:
            _, code = resolve_shape(shape)
            if resizable:
                card = cards.round_card(sku) or cards.fixed_card(sku, code)
            elif cards.has_fixed(sku):
                card = cards.fixed_card(sku, code)
            else:
                card = cards.round_card(sku)
            if card is None:
                skips.append(Skip(sku, shape, "no card for this shape"))
                continue
            rows.extend(Row(sku, shape, fmt_carat(c), card) for c in carats)
    return rows, skips


def build_all(recs: list[dict], cards: Cards):
    rows: list[Row] = []
    skips: list[Skip] = []
    stats: Counter = Counter()
    for rec in recs:
        r, s = plan_rows(rec, cards)
        rows += r
        skips += s
        kind = "resizable" if rec["is_rtr_resizable"] == 1 else "fixed"
        stats[f"skus_{kind}"] += 1
        stats[f"rows_{kind}"] += len(r)
    return rows, skips, stats


def write_csv(rows: list[Row], path: Path | str) -> None:
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["sku", "shape", "carat", "card"])
        for r in rows:
            w.writerow([r.sku, r.shape, r.carat, r.card])
    os.replace(tmp, path)


def format_report(stats: Counter, rows: list[Row], skips: list[Skip]) -> str:
    total = stats["skus_resizable"] + stats["skus_fixed"]
    lines = [
        f"SKUs read: {total} (resizable {stats['skus_resizable']}, fixed {stats['skus_fixed']})",
        f"Rows written: {len(rows)} (resizable {stats['rows_resizable']}, fixed {stats['rows_fixed']})",
        f"Skipped: {len(skips)}",
    ]
    by_reason: dict[str, list[str]] = defaultdict(list)
    for s in skips:
        by_reason[s.reason].append(f"{s.sku} {s.shape}".strip())
    for reason, items in sorted(by_reason.items()):
        lines.append(f"  {reason} ({len(items)}): " + ", ".join(items))
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Build rings.csv from the product Excel export.")
    p.add_argument("--xlsx", required=True)
    p.add_argument("--out", default="rings.csv")
    p.add_argument("--report", default="rings_report.txt")
    p.add_argument("--cards-file", help="use a saved card list (JSON) instead of reading the page")
    p.add_argument("--save-cards", help="save the card list read from the page to this JSON file")
    p.add_argument("--limit-skus", type=int, help="only the first N SKUs of the file")
    args = p.parse_args(argv)
    try:
        recs = load_skus(args.xlsx)
        if args.limit_skus is not None:
            recs = recs[: args.limit_skus]
        if args.cards_file:
            labels = read_labels(args.cards_file)
        else:
            load_dotenv()
            labels = fetch_labels(load_config().base_url)
        if args.save_cards:
            write_labels(args.save_cards, labels)
        rows, skips, stats = build_all(recs, parse_cards(labels))
        report = format_report(stats, rows, skips)
        write_csv(rows, args.out)
        Path(args.report).write_text(report, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - any failure: clear message, existing CSV untouched
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
