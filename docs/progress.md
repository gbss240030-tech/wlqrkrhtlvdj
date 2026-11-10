# 진행 기록

## 현재 단계

Phase 0 — 01 저장소 뼈대 **완료**. 02 KIS 시세 전용 클라이언트 **진행 중(중단)**: 설정만 확장했고 클라이언트 코드는 아직 없음.

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
- `tests/test_common.py`: 32개 테스트

완료 기준 확인: `uv run pytest` 32 passed, `uv run ruff check` 통과, 설정 객체 print 시 `SecretStr('**********')`로 가려짐(테스트 `test_secrets_masked_everywhere`로 고정).

### 2026-11-10 · 02 KIS 클라이언트 (중단)

- 공식 저장소 `koreainvestment/open-trading-api`(examples_llm)에서 아래 내용을 확인했다. `docs/kis_api_notes.md`는 아직 쓰지 않았다.
  - 토큰: `POST /oauth2/tokenP`, body `grant_type=client_credentials, appkey, appsecret`. 응답 `access_token, token_type, expires_in, access_token_token_expired`. 유효 1일, 6시간 안에 다시 요청하면 같은 토큰, 발급은 1분에 1회
  - 현재가: `GET /uapi/domestic-stock/v1/quotations/inquire-price`, tr_id `FHKST01010100`
  - 일봉: `GET .../inquire-daily-itemchartprice`, tr_id `FHKST03010100`, 한 번에 최대 100건
  - 당일 분봉: `GET .../inquire-time-itemchartprice`, tr_id `FHKST03010200`, 한 번에 최대 30건, 전일 분봉 미제공
  - 일별 분봉: `GET .../inquire-time-dailychartprice`, tr_id `FHKST03010230`, 한 번에 최대 120건, 최대 1년 보관(문서 기준). 모의투자 Postman 샘플에는 이 API가 없다 → 모의 지원 여부 미확인
  - 성공 판정은 본문 `rt_cd == "0"`, 실패 시 `msg_cd`, `msg1`. 연속 조회는 응답 헤더 `tr_cont`가 `M`/`F`이면 다음 요청에 `tr_cont: N`
  - 호출 간격은 공식 예제 기준 실전 0.05초, 모의 0.5초. 초당 한도 초과 코드는 `EGW00201`
- `config/base.yaml`과 `common/config.py`에 KIS 호출 한도, 타임아웃, 재시도, 토큰 갱신 여유, 최대 페이지 수, 분봉 시각 기준(`minute_bar_label`), 분봉 거래대금 누적 여부(`minute_value_cumulative`)를 추가했다.
- **중단 이유**: 이 클라우드 컨테이너에서는 KIS 서버 연결이 끊긴다(connection reset). 실제 응답을 받을 수 없어 fixture 저장, 과거 분봉 범위 확인을 할 수 없다. 사용자와 상의해 02는 로컬 PC의 Claude Code에서 이어 가기로 했다.

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

- 분봉 `stck_cntg_hour`가 봉 시작 시각인지 끝 시각인지. 장중에 당일 분봉을 조회해 맨 앞 행(진행 중인 봉)의 시각을 보면 판별된다
- 분봉 `acml_tr_pbmn`이 당일 누적인지 그 분의 거래대금인지. 필드 이름은 "누적"
- 당일 분봉 맨 앞 행의 `cntg_vol`은 첫 체결 전까지 이전 분봉 값이 들어간다(공식 문서). 진행 중인 봉은 버려야 한다
- 토큰 만료 시 오는 `msg_cd` 값
- 일별 분봉 API가 모의투자에서 되는지

- KIS 도메인(`config/base.yaml`의 `kis.real`, `kis.paper`)은 문서 기준 값이다. 02에서 실제 호출로 확인해야 한다.
- KIS 분봉 응답의 시각이 봉 시작인지 끝인지 확인하지 않았다. 04 백필 때 실제 응답을 `tests/fixtures/`에 저장하고 확인한다.
- `.claude/settings.json`의 Bash 거부 규칙은 패턴 일치라서 모든 우회(`python -c`로 읽기 등)를 막지 못한다. `Read` 거부 규칙과 CLAUDE.md 규칙 6에 기대는 부분이 남아 있다.
- 이 세션은 클라우드 컨테이너에서 진행했다. 컨테이너에서 KIS 서버에 접속할 수 있는지, `.env`를 어디에 둘지는 정하지 않았다.

## 다음에 할 일

- **02를 로컬 PC의 Claude Code에서 이어서 한다.** 남은 일: `docs/kis_api_notes.md`, `broker/kis_client.py`(토큰 캐시, 레이트 리미터, rt_cd 판정, tenacity 재시도, 연속 조회), 원본 JSON과 파서 분리, 실제 응답 fixture 저장, live 마커 테스트, `scripts/try_kis.py`, 과거 분봉 조회 범위 실측

- 05·06(매일 수집, 실시간 수집)은 상시 켜져 있는 로컬 PC나 서버에서 돌려야 한다
