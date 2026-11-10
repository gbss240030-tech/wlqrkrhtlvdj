# 진행 기록

## 현재 단계

Phase 0 — 01 저장소 뼈대 **완료**. 다음은 02 KIS 시세 전용 클라이언트.

## 완료한 일

### 2026-11-10 · 01 저장소 뼈대

- `uv` 프로젝트 `kquant` (Python 3.12, `requires-python = ">=3.12,<3.13"`), 소스는 `src/kquant/`
  - 의존성: pandas, pyarrow, duckdb, httpx, websockets, pydantic, pydantic-settings, pyyaml, python-dotenv, tenacity
  - 개발 의존성: pytest, pytest-asyncio, ruff
- CLAUDE.md 디렉터리 구조대로 패키지 폴더와 `__init__.py`, `tests/fixtures/`, `experiments/`
- `common/config.py`: `config/base.yaml` + `.env`/환경 변수 → 불변(frozen) `Settings`. 비밀값은 `SecretStr`
- `common/logging.py`: 콘솔(stderr) + `logs/kquant_YYYY-MM-DD.log`. 날짜와 로그 시각 모두 KST
- `common/timeutil.py`: `now_kst`, `ensure_kst`, `parse_kst`, `parse_compact`/`to_compact`(YYYYMMDD·HHMMSS), `format_kst`, `bar_start`/`bar_end`
- `config/base.yaml`, `.gitignore`, `.env.example`
- `.claude/settings.json`: `.env` 읽기·수정 거부 규칙, 파일 수정 후 `ruff check` + `pytest -q` hook(`.claude/hooks/check.sh`)
- `tests/test_common.py`: 33개 테스트

완료 기준 확인: `uv run pytest` 33 passed, `uv run ruff check` 통과, 설정 객체 print 시 `SecretStr('**********')`로 가려짐(테스트 `test_secrets_masked_everywhere`로 고정).

## 결정과 이유

- **naive datetime은 받지 않는다.** `ensure_kst`가 ValueError를 낸다. 타임존을 추측하면 9시간 어긋난 데이터가 조용히 섞일 수 있어서다. 예외는 `parse_kst`/`parse_compact`로, 타임존 표기가 없는 문자열은 KST 벽시계 시각으로 해석한다(KIS 응답이 KST 문자열이라고 보고).
- **봉 경계는 KST 자정 기준 N분 단위로 자른다.** `bar_start`의 `minutes`는 1440의 약수만 허용한다. 장 시작 09:00이 모든 약수 경계에 맞는다.
- **로그 파일 날짜는 KST로 나눈다.** 표준 `TimedRotatingFileHandler`는 시스템 로컬 시각을 쓰므로 서버가 UTC면 09:00 KST에 파일이 바뀐다. 그래서 레코드 시각의 KST 날짜로 파일을 고르는 핸들러를 직접 만들었다.
- **비밀값은 모두 Optional.** Phase 0에서는 모의 계좌 정보가 없을 수 있다. 실제로 쓰는 쪽(02 이후 클라이언트)에서 None이면 바로 에러를 낸다.
- **`load_settings(env_file=None)`이면 `.env`를 읽지 않는다.** 테스트는 모두 이 경로나 임시 env 파일을 쓴다. 테스트가 실제 `.env`를 건드리지 않게 하려는 것이다.
- **`timezone`이 Asia/Seoul이 아니면 설정 로딩을 실패시킨다.** 값을 바꿔도 코드가 따라가지 않으므로 잘못된 설정이 조용히 통과하지 않게 했다.
- **ruff 규칙에 `DTZ`를 켰다.** naive datetime 생성(`datetime.now()` 등)을 린트 단계에서 잡는다.
- **hook은 실패할 때 exit 2로 결과를 돌려준다.** 그래야 Claude가 실패 내용을 보고 고칠 수 있다.
- **`.env` 거부 규칙에 `.env.*`는 넣지 않았다.** `.env.example`까지 막히기 때문이다. 대신 `.gitignore`는 `.env.*`를 막고 `.env.example`만 허용한다.

## 미확인 사항

- KIS 도메인(`config/base.yaml`의 `kis.real`, `kis.paper`)은 문서 기준 값이다. 02에서 실제 호출로 확인해야 한다.
- KIS 분봉 응답의 시각이 봉 시작인지 끝인지 확인하지 않았다. 04 백필 때 실제 응답을 `tests/fixtures/`에 저장하고 확인한다.
- `.claude/settings.json`의 Bash 거부 규칙은 패턴 일치라서 모든 우회(`python -c`로 읽기 등)를 막지 못한다. `Read` 거부 규칙과 CLAUDE.md 규칙 6에 기대는 부분이 남아 있다.
- 이 세션은 클라우드 컨테이너에서 진행했다. 컨테이너에서 KIS 서버에 접속할 수 있는지, `.env`를 어디에 둘지는 정하지 않았다.
- GitHub push가 403으로 실패했다(Claude GitHub App 권한 문제). 권한을 고치기 전까지 커밋은 로컬에만 있다.

## 다음에 할 일

- 02 KIS 시세 전용 클라이언트. 실전 키 필요, 로컬 PC에서 진행하는 쪽을 권장
- 05·06(매일 수집, 실시간 수집)은 상시 켜져 있는 로컬 PC나 서버에서 돌려야 한다
