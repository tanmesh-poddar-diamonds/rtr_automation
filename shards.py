import csv
import sys
from pathlib import Path


def parse_shard(text: str) -> tuple[int, int]:
    """'3/10' -> (3, 10); raises ValueError for anything that is not 1 <= i <= n."""
    try:
        i, n = (int(part) for part in text.split("/"))
    except ValueError:
        raise ValueError(f"Invalid shard {text!r}: use I/N, for example 3/10") from None
    if n < 1 or not 1 <= i <= n:
        raise ValueError(f"Invalid shard {text!r}: need 1 <= I <= N")
    return i, n


def select_shard(requests: list, index: int, total: int) -> list:
    """Every SKU belongs to exactly one shard (round-robin by first appearance), so two
    workers never touch the same SKU's folders."""
    order: dict[str, int] = {}
    for req in requests:
        order.setdefault(req.sku, len(order))
    return [req for req in requests if order[req.sku] % total == index - 1]


def build_commands(csv_path: str, workers: int, extra: list[str],
                   python: str = sys.executable, script: str = "rtr_run.py") -> list[list[str]]:
    return [[python, script, csv_path, "--shard", f"{i}/{workers}", *extra]
            for i in range(1, workers + 1)]


def merge_summaries(paths: list[Path | str], out: Path | str) -> int:
    """Concatenate per-worker summary files (one header); missing files are skipped."""
    rows = 0
    header = None
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for path in paths:
            if not Path(path).exists():
                continue
            with open(path, newline="", encoding="utf-8") as src:
                reader = csv.reader(src)
                head = next(reader, None)
                if head is None:
                    continue
                if header is None:
                    header = head
                    writer.writerow(header)
                for row in reader:
                    writer.writerow(row)
                    rows += 1
    return rows
