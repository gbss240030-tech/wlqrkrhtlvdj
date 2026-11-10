"""콘솔과 날짜별 파일에 동시에 남기는 로거.

파일 이름은 `{prefix}_YYYY-MM-DD.log`이고, 날짜와 로그 시각은 모두 KST 기준이다.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from kquant.common.timeutil import KST

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_ROOT_NAME = "kquant"


class KSTFormatter(logging.Formatter):
    """asctime을 KST ISO 형식으로 찍는 포매터."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        dt = datetime.fromtimestamp(record.created, KST)
        return dt.strftime(datefmt) if datefmt else dt.isoformat(timespec="milliseconds")


class KSTDailyFileHandler(logging.Handler):
    """레코드의 KST 날짜에 맞는 파일로 기록한다. 날짜가 바뀌면 새 파일을 연다."""

    def __init__(self, log_dir: Path | str, prefix: str = "kquant") -> None:
        super().__init__()
        self.log_dir = Path(log_dir)
        self.prefix = prefix
        self._date: str | None = None
        self._stream = None

    def path_for(self, date_str: str) -> Path:
        return self.log_dir / f"{self.prefix}_{date_str}.log"

    def emit(self, record: logging.LogRecord) -> None:
        try:
            date_str = datetime.fromtimestamp(record.created, KST).strftime("%Y-%m-%d")
            if date_str != self._date:
                self._close_stream()
                self.log_dir.mkdir(parents=True, exist_ok=True)
                self._stream = self.path_for(date_str).open("a", encoding="utf-8")
                self._date = date_str
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except Exception:  # noqa: BLE001 - logging 규약: 로깅 실패가 프로그램을 멈추지 않게 한다
            self.handleError(record)

    def _close_stream(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    def close(self) -> None:
        self.acquire()
        try:
            self._close_stream()
        finally:
            self.release()
        super().close()


def setup_logging(
    log_dir: Path | str, level: str = "INFO", prefix: str = "kquant", console: bool = True
) -> logging.Logger:
    """`kquant` 루트 로거를 설정한다. 여러 번 불러도 핸들러가 중복되지 않는다."""
    logger = logging.getLogger(_ROOT_NAME)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    logger.setLevel(level.upper())
    logger.propagate = False
    formatter = KSTFormatter(_FORMAT)

    file_handler = KSTDailyFileHandler(log_dir, prefix)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if console:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    """`kquant.<name>` 하위 로거."""
    return logging.getLogger(f"{_ROOT_NAME}.{name}")
