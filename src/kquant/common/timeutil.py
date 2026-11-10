"""KST 시간 유틸리티.

규칙
- 모든 datetime은 Asia/Seoul 타임존이 붙어 있어야 한다. naive datetime은 받지 않는다.
- 1분봉(및 N분봉)의 시각은 봉 "시작" 시각으로 통일한다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    """현재 KST 시각."""
    return datetime.now(KST)


def today_kst() -> date:
    """현재 KST 날짜."""
    return now_kst().date()


def ensure_kst(dt: datetime) -> datetime:
    """aware datetime을 KST로 변환한다. naive datetime이면 ValueError."""
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"naive datetime은 허용하지 않습니다: {dt!r}")
    return dt.astimezone(KST)


def parse_kst(text: str) -> datetime:
    """ISO 8601 문자열을 KST datetime으로 바꾼다.

    오프셋이 있으면 KST로 변환하고, 없으면 KST 벽시계 시각으로 해석한다.
    """
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def parse_compact(date_str: str, time_str: str = "000000") -> datetime:
    """'YYYYMMDD'와 'HHMMSS' 형식 문자열을 KST datetime으로 바꾼다."""
    if len(date_str) != 8 or not date_str.isdigit():
        raise ValueError(f"날짜는 YYYYMMDD 형식이어야 합니다: {date_str!r}")
    if len(time_str) != 6 or not time_str.isdigit():
        raise ValueError(f"시각은 HHMMSS 형식이어야 합니다: {time_str!r}")
    naive = datetime.strptime(date_str + time_str, "%Y%m%d%H%M%S")  # noqa: DTZ007
    return naive.replace(tzinfo=KST)


def format_kst(dt: datetime, fmt: str | None = None) -> str:
    """KST 기준 문자열. fmt가 없으면 ISO 8601(+09:00)."""
    kst = ensure_kst(dt)
    return kst.isoformat() if fmt is None else kst.strftime(fmt)


def to_compact(dt: datetime) -> tuple[str, str]:
    """KST datetime을 ('YYYYMMDD', 'HHMMSS')로 바꾼다."""
    kst = ensure_kst(dt)
    return kst.strftime("%Y%m%d"), kst.strftime("%H%M%S")


def bar_start(dt: datetime, minutes: int = 1) -> datetime:
    """dt가 속한 N분봉의 시작 시각(KST).

    봉 경계는 KST 자정 기준으로 N분 단위로 자른다. 예) 1분봉에서 09:00:59 → 09:00:00.
    """
    if minutes <= 0 or (24 * 60) % minutes != 0:
        raise ValueError(f"minutes는 1440의 양의 약수여야 합니다: {minutes}")
    kst = ensure_kst(dt)
    midnight = kst.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = int((kst - midnight).total_seconds()) // 60
    return midnight + timedelta(minutes=elapsed - elapsed % minutes)


def bar_end(dt: datetime, minutes: int = 1) -> datetime:
    """dt가 속한 N분봉의 끝 시각(다음 봉 시작 시각, 미포함)."""
    return bar_start(dt, minutes) + timedelta(minutes=minutes)
