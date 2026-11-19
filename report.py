import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ["sku", "shape", "carat", "status", "downloaded", "skipped", "failed", "seconds"]


@dataclass
class RingResult:
    sku: str
    shape: str
    carat: str
    status: str
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    seconds: float = 0.0
    message: str = ""
    interrupted: bool = False


def write_summary(results: list[RingResult], path: Path | str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        for r in results:
            w.writerow([r.sku, r.shape, r.carat, r.status, r.downloaded, r.skipped, r.failed, f"{r.seconds:.1f}"])


def format_summary(results: list[RingResult]) -> str:
    counts = Counter(r.status for r in results)
    head = f"{len(results)} ring(s): " + ", ".join(f"{s}: {n}" for s, n in sorted(counts.items()))
    lines = [head]
    for r in results:
        extra = f" - {r.message}" if r.message else ""
        lines.append(f"  {r.sku}_{r.shape}: {r.status} "
                     f"(saved {r.downloaded}, skipped {r.skipped}, failed {r.failed}, {r.seconds:.0f}s){extra}")
    return "\n".join(lines)
