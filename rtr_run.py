import argparse
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from config import load_config
from logger import setup_logging
from report import RingResult, format_summary, write_summary
from rings_csv import read_rings
from runner import run_batch
from shards import parse_shard, select_shard


def _playwright_factory(cfg):
    """Real browser: one visible Chrome for the whole batch, one fresh tab per ring."""
    from playwright.sync_api import sync_playwright

    from rtr_page import RtrPage

    pw = sync_playwright().start()

    @contextmanager
    def open_driver():
        # a brand-new Chrome per ring: long-running browsers degrade (crashes, viewer never loads)
        browser = pw.chromium.launch(channel=cfg.browser_channel, headless=cfg.headless)
        try:
            context = browser.new_context(accept_downloads=True, viewport={"width": 1914, "height": 874})
            yield RtrPage(context.new_page(), cfg.base_url)
        finally:
            try:
                browser.close()
            except Exception:  # noqa: BLE001 - a crashed browser may already be gone
                pass

    open_driver.close = lambda: pw.stop()
    return open_driver


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate RTR ring images for each row of a CSV.")
    p.add_argument("csv", help="CSV with columns: sku, shape, carat")
    p.add_argument("--output-dir", help="override OUTPUT_DIR")
    p.add_argument("--log-dir", help="override LOG_DIR")
    p.add_argument("--max-images", type=int, help="stop each ring after N images (smoke test)")
    p.add_argument("--limit", type=int, help="only process the first N valid CSV rows")
    p.add_argument("--force", action="store_true", help="rebuild rings already marked complete")
    p.add_argument("--max-failures", type=int, default=5,
                   help="stop after N rings in a row fail (0 = never stop); default 5")
    p.add_argument("--shard", help="I/N: process only the I-th of N slices of the SKUs (parallel workers)")
    p.add_argument("--summary", help="summary file (default summary.csv, or summary_shard_I.csv with --shard)")
    return p


def main(argv=None, open_driver_factory=None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv()
    try:
        cfg = load_config()
        if args.output_dir:
            cfg = replace(cfg, output_dir=Path(args.output_dir))
        if args.log_dir:
            cfg = replace(cfg, log_dir=Path(args.log_dir))
        shard = parse_shard(args.shard) if args.shard else None
        run_log = setup_logging(cfg.log_dir, f"_run_shard{shard[0]}.log" if shard else "_run.log")
        requests, row_errors = read_rings(args.csv, cfg.ring_prefix)
        if shard:
            requests = select_shard(requests, *shard)
            if shard[0] != 1:  # invalid rows are reported once, by worker 1
                row_errors = []
    except (ValueError, OSError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.limit is not None:
        requests = requests[: args.limit]
    run_log.info("read %d valid ring(s), %d invalid row(s) from %s", len(requests), len(row_errors), args.csv)
    results: list[RingResult] = []
    for e in row_errors:
        run_log.error("invalid CSV row %d: %s (%s)", e.line, e.message, e.raw)
    invalid = [RingResult(e.raw.split(",")[0] or "?", "", "", "invalid", message=f"line {e.line}: {e.message}")
               for e in row_errors]

    factory = (open_driver_factory or _playwright_factory)(cfg)
    stop = None
    try:
        done, stop = run_batch(requests, factory, cfg, run_log, max_images=args.max_images,
                               force=args.force, max_consecutive_failures=args.max_failures)
        results = done + invalid
    finally:
        close = getattr(factory, "close", None)
        if close:
            close()
    summary = args.summary or (f"summary_shard_{shard[0]}.csv" if shard else "summary.csv")
    write_summary(results, summary)
    run_log.info("summary:\n%s", format_summary(results))
    if stop == "interrupted":
        return 130
    if stop == "unhealthy":
        return 3
    ok = {"done", "skipped"}
    return 0 if (results or shard) and all(r.status in ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
