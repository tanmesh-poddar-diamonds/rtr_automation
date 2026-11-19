import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_GO = re.compile(r"Go\('([^']+?)(?:\.glb)?'\)")
_FIXED = re.compile(
    r"^(?P<prefix>[^-]+)-(?P<sku>[A-Za-z0-9_]+?)-not_resizable_(?P<code>[A-Za-z]{2})-0\.00-\d\d$", re.IGNORECASE)
_ROUND = re.compile(r"^(?P<prefix>[^-]+)-(?P<sku>[A-Za-z0-9]+)-round-\d\.\d\d-\d\d$", re.IGNORECASE)


@dataclass(frozen=True)
class Cards:
    fixed: dict   # (SKU, CODE) -> label
    round: dict   # SKU -> label
    fixed_skus: frozenset

    def fixed_card(self, sku: str, code: str) -> str | None:
        return self.fixed.get((sku.upper(), code.upper()))

    def round_card(self, sku: str) -> str | None:
        return self.round.get(sku.upper())

    def has_fixed(self, sku: str) -> bool:
        return sku.upper() in self.fixed_skus

    def has_sku(self, sku: str) -> bool:
        return self.has_fixed(sku) or self.round_card(sku) is not None


def parse_cards(labels: Iterable[str], prefix: str = "833") -> Cards:
    fixed: dict = {}
    rnd: dict = {}
    for label in sorted(labels):  # sorted: deterministic when a SKU has several cards
        m = _FIXED.match(label)
        if m and m.group("prefix") == prefix:
            fixed.setdefault((m.group("sku").upper(), m.group("code").upper()), label)
            continue
        m = _ROUND.match(label)
        if m and m.group("prefix") == prefix:
            rnd.setdefault(m.group("sku").upper(), label)
    return Cards(fixed, rnd, frozenset(sku for sku, _ in fixed))


def labels_from_onclicks(onclicks: Iterable[str | None]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for text in onclicks:
        m = _GO.search(text or "")
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(m.group(1))
    return out


def fetch_labels(base_url: str) -> list[str]:
    """One read-only headless visit to the ring grid; returns every card's true label."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(base_url, wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(2000)
            clicks = page.evaluate(
                "() => [...document.querySelectorAll('img[onclick^=\"Go(\"]')]"
                ".map(i => i.getAttribute('onclick'))")
        finally:
            browser.close()
    return labels_from_onclicks(clicks)


def write_labels(path: Path | str, labels: list[str]) -> None:
    Path(path).write_text(json.dumps(labels, indent=0), encoding="utf-8")


def read_labels(path: Path | str) -> list[str]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
