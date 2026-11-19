import logging
import re
import sys
from contextlib import contextmanager
from pathlib import Path

_SID = re.compile(r"(SID=)[^&\s'\"<>]+", re.IGNORECASE)
_FMT = "%(asctime)s | %(levelname)s | %(short)s | %(message)s"


def mask_sid(text: str) -> str:
    return _SID.sub(r"\1***", text)


class _MaskingFormatter(logging.Formatter):
    """Masks the session id in the final text, including formatted tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        return mask_sid(super().format(record))


class _ShortName(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.short = record.name.removeprefix("rtr.").removeprefix("ring.")
        return True


def _prepare(handler: logging.Handler) -> logging.Handler:
    handler.setFormatter(_MaskingFormatter(_FMT, datefmt="%Y-%m-%d %H:%M:%S"))
    handler.addFilter(_ShortName())
    return handler


def _clear(logger: logging.Logger) -> None:
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()


def setup_logging(log_dir: Path | str, run_log_name: str = "_run.log") -> logging.Logger:
    """Console + logs/_run.log. Returns the run-level logger."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("rtr")
    root.setLevel(logging.DEBUG)
    root.propagate = False
    _clear(root)
    console = _prepare(logging.StreamHandler(sys.stdout))
    console.setLevel(logging.INFO)
    root.addHandler(console)
    run = logging.getLogger("rtr.run")
    _clear(run)
    run.addHandler(_prepare(logging.FileHandler(log_dir / run_log_name, encoding="utf-8")))
    return run


@contextmanager
def ring_logger(log_dir: Path | str, key: str):
    """Per-ring logger writing logs/<key>.log (append). Handler removed on exit."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"rtr.ring.{key}")
    logger.setLevel(logging.DEBUG)
    handler = _prepare(logging.FileHandler(log_dir / f"{key}.log", encoding="utf-8"))
    logger.addHandler(handler)
    logger.info("run started")
    try:
        yield logger
    finally:
        logger.removeHandler(handler)
        handler.close()
