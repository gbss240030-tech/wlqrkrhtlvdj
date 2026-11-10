from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kquant.common import timeutil as tu
from kquant.common.config import DEFAULT_CONFIG_PATH, load_settings
from kquant.common.logging import get_logger, setup_logging

SECRET_ENV = {
    "KIS_REAL_APP_KEY": "real-key-SHOULD-NOT-LEAK",
    "KIS_REAL_APP_SECRET": "real-secret-SHOULD-NOT-LEAK",
    "KIS_PAPER_APP_KEY": "paper-key-SHOULD-NOT-LEAK",
    "KIS_PAPER_APP_SECRET": "paper-secret-SHOULD-NOT-LEAK",
    "KIS_PAPER_ACCOUNT": "12345678-01",
}


@pytest.fixture
def secret_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    for k, v in SECRET_ENV.items():
        monkeypatch.setenv(k, v)
    return SECRET_ENV


@pytest.fixture
def no_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in SECRET_ENV:
        monkeypatch.delenv(k, raising=False)


# ---------- 설정 ----------


def test_load_base_yaml(no_secret_env: None, tmp_path: Path) -> None:
    s = load_settings(env_file=None, root=tmp_path)
    assert s.timezone == "Asia/Seoul"
    assert s.paths.data_raw == tmp_path / "data" / "raw"
    assert s.paths.logs == tmp_path / "logs"
    assert s.kis.real.rest.startswith("https://")
    assert s.kis.paper.rest.startswith("https://")
    assert s.kis.real.rest != s.kis.paper.rest
    assert s.secrets.kis_real_app_key is None


def test_secrets_from_env(secret_env: dict[str, str]) -> None:
    s = load_settings(env_file=None)
    assert s.secrets.kis_real_app_key is not None
    assert s.secrets.kis_real_app_key.get_secret_value() == secret_env["KIS_REAL_APP_KEY"]
    assert s.secrets.kis_paper_account.get_secret_value() == secret_env["KIS_PAPER_ACCOUNT"]


def test_secrets_from_env_file(no_secret_env: None, tmp_path: Path) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text("KIS_PAPER_APP_KEY=from-file\n", encoding="utf-8")
    s = load_settings(env_file=env_file)
    assert s.secrets.kis_paper_app_key.get_secret_value() == "from-file"


def test_env_var_overrides_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text("KIS_PAPER_APP_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("KIS_PAPER_APP_KEY", "from-env")
    s = load_settings(env_file=env_file)
    assert s.secrets.kis_paper_app_key.get_secret_value() == "from-env"


def test_secrets_masked_everywhere(
    secret_env: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    s = load_settings(env_file=None)
    print(s)
    print(repr(s))
    print(s.secrets)
    rendered = capsys.readouterr().out + s.model_dump_json() + str(s.model_dump())
    for value in secret_env.values():
        assert value not in rendered
    assert "**********" in rendered


def test_rejects_non_kst_timezone(no_secret_env: None, tmp_path: Path) -> None:
    cfg = tmp_path / "bad.yaml"
    text = DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    cfg.write_text(text.replace("timezone: Asia/Seoul", "timezone: UTC"), encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(config_path=cfg, env_file=None)


def test_settings_frozen(no_secret_env: None) -> None:
    s = load_settings(env_file=None)
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError
        s.timezone = "UTC"  # type: ignore[misc]


# ---------- 시간 ----------


def test_now_kst_is_aware() -> None:
    now = tu.now_kst()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 9 * 3600


def test_ensure_kst_rejects_naive() -> None:
    with pytest.raises(ValueError):
        tu.ensure_kst(datetime(2024, 1, 2, 9, 0))  # noqa: DTZ001 - 의도적 naive


def test_ensure_kst_converts_utc() -> None:
    utc = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    assert tu.ensure_kst(utc) == datetime(2024, 1, 2, 9, 0, tzinfo=tu.KST)
    assert tu.ensure_kst(utc).hour == 9


def test_parse_kst_naive_string_is_kst() -> None:
    assert tu.parse_kst("2024-01-02T09:00:00") == datetime(2024, 1, 2, 9, 0, tzinfo=tu.KST)


def test_parse_kst_with_offset_converted() -> None:
    dt = tu.parse_kst("2024-01-02T00:00:00+00:00")
    assert dt.hour == 9
    assert dt.tzinfo == tu.KST


def test_parse_compact_roundtrip() -> None:
    dt = tu.parse_compact("20240102", "093015")
    assert dt == datetime(2024, 1, 2, 9, 30, 15, tzinfo=tu.KST)
    assert tu.to_compact(dt) == ("20240102", "093015")


@pytest.mark.parametrize("d,t", [("2024012", "090000"), ("20240102", "0900"), ("2024-1-2", "")])
def test_parse_compact_rejects_bad_format(d: str, t: str) -> None:
    with pytest.raises(ValueError):
        tu.parse_compact(d, t)


def test_format_kst() -> None:
    dt = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    assert tu.format_kst(dt) == "2024-01-02T09:00:00+09:00"
    assert tu.format_kst(dt, "%Y%m%d %H%M") == "20240102 0900"


@pytest.mark.parametrize(
    "hms,minutes,expected",
    [
        ((9, 0, 0), 1, (9, 0)),
        ((9, 0, 59), 1, (9, 0)),
        ((9, 1, 0), 1, (9, 1)),
        ((15, 29, 59), 1, (15, 29)),
        ((9, 4, 59), 5, (9, 0)),
        ((9, 5, 0), 5, (9, 5)),
        ((10, 59, 59), 60, (10, 0)),
    ],
)
def test_bar_start(hms: tuple[int, int, int], minutes: int, expected: tuple[int, int]) -> None:
    dt = datetime(2024, 1, 2, *hms, 123456, tzinfo=tu.KST)
    assert tu.bar_start(dt, minutes) == datetime(2024, 1, 2, *expected, tzinfo=tu.KST)


def test_bar_start_from_utc_input() -> None:
    utc = datetime(2024, 1, 2, 0, 0, 30, tzinfo=UTC)  # KST 09:00:30
    assert tu.bar_start(utc) == datetime(2024, 1, 2, 9, 0, tzinfo=tu.KST)


def test_bar_end_is_next_bar_start() -> None:
    dt = datetime(2024, 1, 2, 9, 0, 30, tzinfo=tu.KST)
    assert tu.bar_end(dt) == datetime(2024, 1, 2, 9, 1, tzinfo=tu.KST)


@pytest.mark.parametrize("minutes", [0, -1, 7])
def test_bar_start_rejects_bad_minutes(minutes: int) -> None:
    with pytest.raises(ValueError):
        tu.bar_start(tu.now_kst(), minutes)


# ---------- 로깅 ----------


def test_logging_writes_console_and_daily_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = setup_logging(tmp_path / "logs", level="INFO", prefix="t")
    try:
        get_logger("test").info("hello")
        get_logger("test").debug("hidden")
        files = list((tmp_path / "logs").glob("t_*.log"))
        assert len(files) == 1
        assert files[0].name == f"t_{tu.today_kst():%Y-%m-%d}.log"
        content = files[0].read_text(encoding="utf-8")
        assert "hello" in content and "+09:00" in content
        assert "hidden" not in content
        assert "hello" in capsys.readouterr().err
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
            h.close()


def test_logging_setup_is_idempotent(tmp_path: Path) -> None:
    setup_logging(tmp_path, console=True)
    root = setup_logging(tmp_path, console=True)
    try:
        assert len(root.handlers) == 2
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
            h.close()
    assert logging.getLogger("kquant").handlers == []


def test_daily_file_switches_on_kst_date(tmp_path: Path) -> None:
    from kquant.common.logging import KSTDailyFileHandler

    handler = KSTDailyFileHandler(tmp_path, prefix="d")
    try:
        # 2024-01-01 23:59:59 KST, 2024-01-02 00:00:00 KST (UTC 기준으로는 같은 날)
        for ts, msg in [
            (datetime(2024, 1, 1, 23, 59, 59, tzinfo=tu.KST).timestamp(), "before"),
            (datetime(2024, 1, 2, 0, 0, 0, tzinfo=tu.KST).timestamp(), "after"),
        ]:
            rec = logging.LogRecord("kquant.t", logging.INFO, __file__, 0, msg, None, None)
            rec.created = ts
            handler.emit(rec)
    finally:
        handler.close()
    assert (tmp_path / "d_2024-01-01.log").read_text(encoding="utf-8").strip() == "before"
    assert (tmp_path / "d_2024-01-02.log").read_text(encoding="utf-8").strip() == "after"
