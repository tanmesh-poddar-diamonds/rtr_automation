import time

from downloads import ring_dir, save_download
from logger import ring_logger
from report import RingResult


def _collect(drv, folder, seen, res, log) -> int:
    got = 0
    for download in drv.drain_downloads():
        got += 1
        folder.mkdir(parents=True, exist_ok=True)  # created on the first image, never earlier
        r = save_download(download, folder, seen)
        if r.status == "saved":
            res.downloaded += 1
            log.info("saved %s%s", r.name, f" ({r.detail})" if r.detail else "")
            if r.detail:
                log.warning("name collision handled: %s", r.name)
        elif r.status == "skipped":
            res.skipped += 1
            log.info("skipped existing %s", r.name)
        else:
            res.failed += 1
            log.error("download failed: %s (%s)", r.name, r.detail)
    return got


def _open_with_retry(req, drv, log, res) -> bool:
    for attempt in (1, 2):
        try:
            if not drv.open_ring(req.label):
                log.warning("ring not found: %s", req.label)
                res.status = "not_found"
                return False
            drv.open_panel()
            return True
        except Exception as exc:  # noqa: BLE001 - retried once, then reported
            log.warning("open attempt %d failed: %s", attempt, exc)
            if attempt == 2:
                res.status = "failed"
                res.message = str(exc)
                return False
    return False


def run_ring(req, drv, cfg, log, now=time.monotonic, max_images=None, force=False) -> RingResult:
    started = now()
    res = RingResult(sku=req.sku, shape=req.shape, carat=req.carat, status="failed")
    folder = ring_dir(cfg.output_dir, req.key, create=False)
    marker = folder / ".complete"
    if force:
        marker.unlink(missing_ok=True)
    elif marker.exists():
        res.status = "skipped"
        res.message = "already complete (.complete marker); use --force to rebuild"
        log.info(res.message)
        return _finish(res, started, now, log)
    seen: set[str] = set()
    try:
        log.info("ring %s | shape %s | carat %s", req.label, req.shape, req.carat)
        if not _open_with_retry(req, drv, log, res):
            return _finish(res, started, now, log)
        drv.set_carat(req.carat)
        drv.select_only_shape(req.shape)
        ticked = drv.ensure_all_colours(req.shape)
        log.info("panel set: carat=%s shape=%s (ticked %s extra colours)", req.carat, req.shape, ticked)
        drv.drain_downloads()  # discard anything that arrived before BUILD
        drv.start_build()
        log.info("BUILD started")

        status, last, last_logged = "done", None, -10**9
        last_change = now()
        while True:
            _collect(drv, folder, seen, res, log)
            prog = drv.read_progress()
            if prog is not None:
                if prog != last:
                    last, last_change = prog, now()
                    if prog[0] - last_logged >= cfg.progress_log_every:
                        log.info("progress %d (from %d)", prog[0], prog[1])
                        last_logged = prog[0]
                # the counter stops one short of the total, so completion is judged by files saved
                if prog[1] > 0 and (prog[0] >= prog[1] or res.downloaded + res.skipped >= prog[1]):
                    break
            if max_images is not None and res.downloaded + res.skipped >= max_images:
                drv.stop_build()
                status = "partial"
                res.message = f"stopped after {max_images} images (--max-images)"
                log.info(res.message)
                break
            if now() - last_change > cfg.stall_timeout_s:
                drv.stop_build()
                status = "stalled"
                res.message = f"no progress for {cfg.stall_timeout_s}s at {last}"
                log.error(res.message)
                break
            drv.pump(500)

        for _ in range(30):  # let the last downloads land
            drv.pump(1000)
            if _collect(drv, folder, seen, res, log) == 0:
                break
        if res.failed and status == "done":
            status = "partial"
        if status == "done" and last and res.downloaded + res.skipped != last[1]:
            log.warning("expected %d files (counter total) but got %d",
                        last[1], res.downloaded + res.skipped)
        res.status = status
        if status == "done":
            folder.mkdir(parents=True, exist_ok=True)
            marker.write_text(time.strftime("completed %Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
    except KeyboardInterrupt:
        res.status, res.message, res.interrupted = "partial", "interrupted by user", True
        log.warning("interrupted by user")
    except Exception as exc:  # noqa: BLE001 - one ring must never kill the batch
        log.exception("ring failed")
        res.status = "partial" if res.downloaded + res.skipped else "failed"
        res.message = str(exc)
    return _finish(res, started, now, log)


def _finish(res, started, now, log) -> RingResult:
    res.seconds = now() - started
    log.info("finished: %s (saved %d, skipped %d, failed %d, %.0fs) %s",
             res.status, res.downloaded, res.skipped, res.failed, res.seconds, res.message)
    return res


def run_batch(requests, open_driver, cfg, run_log, max_images=None, now=time.monotonic, force=False,
              max_consecutive_failures=5):
    """Run every ring. Returns (results, stop) where stop is None, "interrupted" (Ctrl+C) or
    "unhealthy" (too many rings in a row failed: the site or browser is in trouble)."""
    results: list[RingResult] = []
    stop = None
    streak = 0
    for i, req in enumerate(requests, 1):
        run_log.info("[%d/%d] %s", i, len(requests), req.key)
        with ring_logger(cfg.log_dir, req.key) as log, open_driver() as drv:
            res = run_ring(req, drv, cfg, log, now=now, max_images=max_images, force=force)
        results.append(res)
        run_log.info("%s -> %s", req.key, res.status)
        if res.interrupted:
            stop = "interrupted"
            break
        if res.status == "failed":
            streak += 1
        elif res.status not in ("not_found", "skipped"):
            streak = 0
        if max_consecutive_failures and streak >= max_consecutive_failures:
            run_log.error("stopping: %d rings in a row failed (site or browser unhealthy); "
                          "re-run the same command to resume", streak)
            stop = "unhealthy"
            break
    return results, stop
