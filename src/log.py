"""Per-run structured logging: one file per run under logs/, plus console."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path("logs")


def setup_logging(run_name: str) -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOGS_DIR / f"{run_name}-{stamp}.log"

    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(console)

    logger.info("log file: %s", log_path)
    return logger
