"""설정 로딩.

`config/base.yaml`(비밀 아님)과 `.env`/환경 변수(비밀)를 합쳐 `Settings`를 만든다.
비밀값은 `SecretStr`로 감싸므로 print/repr/로그에 원문이 나오지 않는다.
원문이 필요하면 호출하는 쪽에서 `.get_secret_value()`를 명시적으로 쓴다.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "base.yaml"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PathsConfig(_Frozen):
    data_raw: Path
    data_processed: Path
    logs: Path
    experiments: Path
    token_cache: Path


class LoggingConfig(_Frozen):
    level: str = "INFO"
    file_prefix: str = "kquant"


class KisEndpoint(_Frozen):
    rest: str
    websocket: str


class KisConfig(_Frozen):
    real: KisEndpoint
    paper: KisEndpoint


class Secrets(BaseSettings):
    """환경 변수 또는 .env에서 읽는 비밀값. 없으면 None."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    kis_real_app_key: SecretStr | None = None
    kis_real_app_secret: SecretStr | None = None
    kis_paper_app_key: SecretStr | None = None
    kis_paper_app_secret: SecretStr | None = None
    kis_paper_account: SecretStr | None = None


class Settings(_Frozen):
    timezone: str
    paths: PathsConfig
    logging: LoggingConfig
    kis: KisConfig
    secrets: Secrets


def _resolve_paths(paths: dict, root: Path) -> dict:
    return {k: (Path(v) if Path(v).is_absolute() else root / v) for k, v in paths.items()}


def load_settings(
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    env_file: Path | str | None = DEFAULT_ENV_FILE,
    root: Path | str = PROJECT_ROOT,
) -> Settings:
    """설정을 읽는다.

    env_file=None이면 .env를 읽지 않고 프로세스 환경 변수만 쓴다(테스트용).
    같은 키가 둘 다 있으면 환경 변수가 우선한다.
    """
    with Path(config_path).open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if raw.get("timezone") != "Asia/Seoul":
        raise ValueError("timezone은 Asia/Seoul이어야 합니다")
    raw["paths"] = _resolve_paths(raw["paths"], Path(root))
    secrets = Secrets(_env_file=env_file)  # type: ignore[call-arg]
    return Settings(**raw, secrets=secrets)
