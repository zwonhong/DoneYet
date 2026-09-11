# DoneYet
DoneYet? - A self-hosted daily check-in bot for Discord.

현재는 Discord 로그인, `/test` 슬래시 명령어, SQLite 초기화와 Check 데이터 모델·저장·조회가 구현되어 있습니다.
Python 3.10 이상을 사용합니다.

## 설정

1. 프로젝트 루트의 `.env`에 `DISCORD_TOKEN=실제_봇_토큰`을 설정합니다.
   새 환경에서는 `.env.example`을 `.env`로 복사한 뒤 값을 입력합니다.
2. Discord Developer Portal에서 앱의 봇을 만들고, OAuth2 URL Generator에서
   `bot`, `applications.commands` 범위를 선택해 서버에 초대합니다.
   이 단계에서는 관리자 권한이나 privileged intents가 필요하지 않습니다.

`.env`는 Git에서 제외됩니다. 토큰이나 서버 ID를 Python 코드에 넣지 않습니다.
이미 설정된 환경 변수 `DISCORD_TOKEN`은 `.env` 값보다 우선합니다.

## Windows (PowerShell)

프로젝트 폴더에서 실행합니다. 가상 환경 활성화 없이도 실행할 수 있습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Raspberry Pi OS Lite

Python 3.10 이상이 설치된 환경에서 같은 소스 코드를 사용합니다.
Windows의 `.venv`를 복사하지 말고 Pi에서 새로 만듭니다.

```bash
sudo apt update
sudo apt install -y python3 python3-venv
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

## 동작 확인

로그인 완료 시 콘솔에 `DoneYet? logged in as 봇이름`이 출력됩니다.
서버에서 `/test`를 실행하면 `DoneYet? is running! ✅`라고 응답합니다.
명령어는 시작 시 전역으로 등록되므로 서버 ID가 필요하지 않으며,
Discord에 반영되기까지 시간이 걸릴 수 있습니다. 종료는 `Ctrl+C`입니다.

## 코드 구조

- `main.py`: 설정을 읽고 DB 초기화 후 봇 실행
- `doneyet/config.py`: `.env` 및 토큰 검증
- `doneyet/bot.py`: Discord 클라이언트와 슬래시 명령어
- `doneyet/database.py`: SQLite 스키마, 연결 관리, 초기화, aware datetime 직렬화
- `doneyet/models.py`: Check 입력 및 조회 결과 데이터 모델
- `doneyet/repository.py`: Check 입력 검증, 트랜잭션 저장, 서버별 조회
- `tests/test_repository.py`: Check 저장·조회, 서버 구분, 입력 검증 및 저장 실패 테스트
- `tests/test_database.py`: 임시 DB로 중복 제약, 외래키, 재초기화, rollback, datetime 검증
- `requirements.txt`: 실행 의존성

scheduler, check-in 및 인증 처리 기능은 아직 포함하지 않습니다.

## SQLite 데이터 계층 (Step 1)

봇 시작 시 토큰 설정 검증 후 `data/doneyet.db`와 누락된 테이블을 자동 생성합니다.
경로는 프로젝트 위치 기준이므로 실행 디렉터리와 무관합니다. 재초기화는 기존
데이터를 유지합니다. 기존 테이블의 구조를 변경하는 migration은 아직 제공하지 않습니다.
DB 연결은 Python 표준 라이브러리 `sqlite3`를 사용합니다.
DB 및 journal/WAL/SHM 파일은 `.gitignore`로 제외합니다.

실제 DDL은 `doneyet/database.py`의 `SCHEMA`에 있습니다.
아래에서 `?`는 NULL 허용이며 그 외 일반 필드는 NOT NULL입니다.
`id`는 INTEGER PRIMARY KEY입니다.

| 테이블 | 컬럼과 SQLite 타입 |
| --- | --- |
| checks | id INTEGER, guild_id INTEGER, channel_id INTEGER, name TEXT, verification_mode TEXT, timezone TEXT, enabled INTEGER, created_at TEXT |
| check_days | check_id INTEGER, weekday INTEGER |
| check_schedules | id INTEGER, check_id INTEGER, sequence INTEGER, check_time TEXT, reminder_time TEXT |
| check_members | check_id INTEGER, user_id INTEGER, joined_at TEXT |
| daily_checkins | id INTEGER, check_id INTEGER, schedule_id INTEGER, date TEXT, message_id INTEGER, thread_id INTEGER?, created_at TEXT, closed_at TEXT? |
| verifications | id INTEGER, check_id INTEGER, schedule_id INTEGER, user_id INTEGER, date TEXT, verification_method TEXT, verified_at TEXT |

중복 방지 제약:

- 명세: `daily_checkins UNIQUE(check_id, schedule_id, date)`
- 명세: `verifications UNIQUE(check_id, schedule_id, user_id, date)`
- `check_days PRIMARY KEY(check_id, weekday)`
- `check_members PRIMARY KEY(check_id, user_id)`
- `check_schedules UNIQUE(check_id, sequence)`
- `check_schedules UNIQUE(check_id, id)`: 복합 외래키의 참조 대상

모든 자식 테이블의 `check_id`는 `checks.id`를 참조합니다.
`daily_checkins(check_id, schedule_id)`는 `check_schedules(check_id, id)`를 참조하여
서로 다른 Check의 schedule 연결을 차단합니다.
`verifications(check_id, schedule_id, date)`는 해당 `daily_checkins`를 참조합니다.
참여자 탈퇴 후에도 과거 인증을 보존할 수 있도록 `verifications.user_id`는
현재 참여자 목록의 외래키로 묶지 않습니다. 가입 여부 검증은 향후 인증 처리 단계의 역할입니다.
삭제 동작은 기본 NO ACTION이며 자동 cascade 삭제는 없습니다.

연결은 `connect_database()`를 사용합니다. 매 연결에 `PRAGMA foreign_keys = ON`을
적용하고 정상 종료 시 commit, 예외 시 rollback, 마지막에 close합니다.
외부 도구가 직접 여는 연결에도 별도로 foreign_keys 설정이 필요합니다.

값 규칙:

- `verification_mode`: `button`, `photo`, `either`
- `verification_method`: `button`, `photo`
- `weekday`: 0(월요일)~6(일요일), `sequence`: 1 이상
- `enabled`: 0 또는 1, 기본값 1
- `timezone`: IANA 시간대 이름, 기본값 `Asia/Seoul`
- `check_time`, `reminder_time`: Check 현지 시각 `HH:MM` (00:00~23:59)
- `date`: Check 현지 날짜 `YYYY-MM-DD`
- `created_at`, `joined_at`, `verified_at`: 기본값 UTC 현재 시각, ISO 8601 TEXT
- `closed_at`: 미종료 시 NULL, 종료 시 같은 UTC ISO 8601 형식

명시적으로 datetime을 저장할 때는 `serialize_datetime()`을 사용합니다.
시간대 없는 datetime을 거부하고 UTC 오프셋을 포함한 문자열로 변환합니다.
읽을 때 `datetime.fromisoformat()`으로 aware datetime을 복원할 수 있습니다.
날짜 유효성, IANA 시간대 이름 및 직접 입력하는 timestamp의 형식 검증은
향후 데이터 입력 계층에서 수행해야 합니다. 현재 SQL은 이 문자열들을 강제 검증하지 않습니다.

### 실행 테스트

Discord 토큰이나 접속 없이 DB를 생성하고 테스트할 수 있습니다.
테스트 데이터는 임시 디렉터리에만 생성됩니다.

```powershell
.\.venv\Scripts\python.exe -m doneyet.database
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Raspberry Pi에서는 위 명령의 Python 경로를 `.venv/bin/python`으로 바꿉니다.
실제 DB 스키마 확인:

```powershell
@'
from doneyet.database import connect_database
with connect_database() as db:
    for row in db.execute("SELECT sql FROM sqlite_master WHERE type = 'table'"):
        print(row[0], end=";\n\n")
'@ | .\.venv\Scripts\python.exe -
```

## Check 모델과 저장·조회 (Step 2)

`CheckInput`에 기본 설정, 참여자 ID, 요일, `ScheduleInput` 목록을 전달합니다.
`CheckRepository.create_check()`는 네 테이블에 한 트랜잭션으로 저장하고 `Check`를 반환합니다.
저장 중 실패하면 해당 Check의 변경 전체가 취소됩니다. 같은 입력을 다시 생성하면
별도 Check가 만들어집니다. 스키마 변경이나 자동 샘플 데이터 삽입은 없습니다.

- `create_check(data) -> Check`: 생성 및 저장 결과 반환
- `get_check(guild_id, check_id) -> Check | None`: 해당 서버의 Check 조회
- `list_checks(guild_id) -> list[Check]`: 해당 서버의 Check 목록 (ID 순서, 비활성 포함)

반환 모델에는 참여자와 가입 시각, 요일, 회차별 ID와 시각이 포함됩니다.
`daily_sessions`는 회차 개수이며, 회차 번호는 입력 목록 순서대로 1부터 부여합니다.
요일은 0(월)~6(일) 오름차순, 참여자는 user_id 순서로 조회합니다.
`created_at`과 `joined_at`은 timezone-aware datetime으로 복원됩니다.

이름, 인증 방식, ID, 요일, 참여자 중복, 최소 한 명의 참여자·한 요일·한 회차,
`HH:MM` 시각, IANA 시간대를 저장 전에 검증합니다. Windows의 시간대 데이터 제공을 위해
`requirements.txt`에 `tzdata`를 추가했습니다. 시간 순서나 회차 간 간격은 아직 제한하지 않습니다.

DB 초기화 후 저장·조회 코드는 다음 형태로 사용합니다. ID 변수는 호출자가 전달합니다.

```python
from doneyet.database import initialize_database
from doneyet.models import CheckInput, ScheduleInput, VerificationMode
from doneyet.repository import CheckRepository

initialize_database()
repository = CheckRepository()
check = repository.create_check(CheckInput(
    guild_id=guild_id,
    channel_id=channel_id,
    name="공부",
    verification_mode=VerificationMode.EITHER,
    member_ids=tuple(member_ids),
    weekdays=(0, 1, 2, 3, 4),
    schedules=(ScheduleInput("09:00", "12:00"), ScheduleInput("21:00", "23:30")),
))
saved = repository.get_check(guild_id, check.id)
checks = repository.list_checks(guild_id)
```

Repository는 동기 함수입니다. 추후 Discord async command에서 호출할 때는
`await asyncio.to_thread(repository.create_check, data)`처럼 실행합니다.
현재 `/check create`나 scheduler는 연결하지 않았으며 `/test`는 기존대로 동작합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

기존 DB 테스트와 함께 공부·영양제 예시의 저장 및 재조회, 서버별 조회 범위,
잘못된 입력 거부, 저장 도중 실패 시 전체 rollback을 임시 DB에서 검증합니다.

참고: [discord.py 명령어 API](https://discordpy.readthedocs.io/en/stable/interactions/api.html),
[python-dotenv 설정](https://pypi.org/project/python-dotenv/).
