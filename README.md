# DoneYet
DoneYet? - A self-hosted daily check-in bot for Discord.

현재는 Discord 로그인, `/test`, SQLite 데이터 계층과 `/check create` 단일 설정 패널가 구현되어 있습니다.
Python 3.10 이상을 사용합니다.

## 설정

1. 프로젝트 루트의 `.env`에 `DISCORD_TOKEN=실제_봇_토큰`을 설정합니다.
   새 환경에서는 `.env.example`을 `.env`로 복사한 뒤 값을 입력합니다.
2. Discord Developer Portal에서 앱의 봇을 만들고, OAuth2 URL Generator에서
   `bot`, `applications.commands` 범위를 선택해 서버에 초대합니다.
   이 단계에서는 관리자 권한이나 privileged intents가 필요하지 않습니다.

`.env`는 Git에서 제외됩니다. 토큰이나 서버 ID를 Python 코드에 넣지 않습니다.
이미 설정된 환경 변수 `DISCORD_TOKEN`은 `.env` 값보다 우선합니다.
개발 서버에 명령어를 빠르게 반영하려면 `.env`에 선택적으로 `DISCORD_GUILD_ID`를
설정합니다. 설정 방법과 sync 로그는 아래를 참고하세요.

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

### `/check create`가 보이지 않을 때: sync 로그와 개발 서버 설정

`bot.py`는 생성자에서 `/test`와 `CheckCommands` 그룹을 tree에 추가하고,
그 후 로그인 과정의 `setup_hook()`에서 sync합니다. `/check create`는
그룹 클래스의 `@app_commands.command`로 등록되며 별도의 Cog 로딩은 없습니다.
로컬 payload에는 `/check`와 그 하위 `create`가 포함됩니다.

기존 코드는 전역 sync만 수행하고 반환 결과를 기록하지 않았습니다.
따라서 화면에 `/test`만 보인다는 정보로는 전역 반영 지연, 이전 코드 실행,
다른 Application 확인 등을 구분할 수 없습니다. 코드에서 등록 순서 문제는
발견되지 않았으며, 실제 원인은 실행 시 Discord 응답 로그로 확인해야 합니다.

재시작 시 아래 형태의 로그가 출력됩니다.

```text
DoneYet? startup: ...\doneyet\bot.py | Python: ... | application_id=...
DoneYet? syncing [global]: /check create, /test
Synced 2 application commands [global]:
- /test (id=...)
- /check (id=...)
DoneYet? logged in as ...
```

`syncing`은 로컬 tree, `synced`와 `registered`는 Discord API가 반환한 결과입니다.
`/check create`는 최상위 `/check`의 하위 명령어이므로 최상위 개수는 총 2개입니다.
sync 예외는 대상과 Application ID를 포함해 기록하고 다시 발생시킵니다.
반환된 명령어 목록이 요청한 목록과 달라도 시작을 중단합니다.
Guilds intent는 명령어 등록을 대신하지 않으며, sync는 재연결의 `on_ready()`에서 반복하지 않습니다.

빠른 개발 테스트를 위해 `.env`에 다음 줄을 추가할 수 있습니다. 실제 서버 ID를
값으로 입력하고 봇을 재시작하세요. 토큰은 기존 값을 유지합니다.

```dotenv
DISCORD_GUILD_ID=여기에_개발_서버_ID
```

Discord 개발자 모드를 켠 후 테스트할 서버를 우클릭해 서버 ID를 복사합니다.
값은 숫자여야 하며, 비워두면 기존처럼 전역 sync만 합니다. 이 설정도 이미 정의된
환경 변수가 `.env`보다 우선합니다. 실제 ID는 코드나 `.env.example`에 넣지 않습니다.

설정하면 전역 sync 후 `copy_global_to(guild=...)`로 `/test`와 `/check`를 개발 서버의
로컬 tree에 복사하고 `sync(guild=...)`를 실행합니다. 복사 없이 guild sync만 호출하면
빈 guild tree를 보낼 수 있으므로 복사를 먼저 수행합니다.
이는 [discord.py 공식 개발 예제](https://github.com/Rapptz/discord.py/blob/master/examples/app_commands/basic.py)의 방식입니다.

```text
DoneYet? syncing [guild:...] : ...
Synced 2 application commands [guild:...]:
```

서버 sync 실패 시 대상 ID, 봇의 해당 서버 설치 여부, 애플리케이션 명령어 사용 설정을 확인합니다.
성공 로그가 있는데도 보이지 않으면 해당 서버에서 `/check create` 전체를 검색하고,
로그의 Application ID가 보고 있는 DoneYet? 앱과 일치하는지 확인하세요.
새 startup 로그 자체가 없으면 실행 중인 이전 프로세스를 종료하고 이 프로젝트의 `main.py`를 실행합니다.
Guild ID 설정을 지워도 Discord에 이미 등록된 guild 명령어를 자동 삭제하지는 않습니다.

## 코드 구조

- `main.py`: 설정을 읽고 DB 초기화 후 봇 실행
- `doneyet/config.py`: `.env` 및 토큰 검증
- `doneyet/bot.py`: Discord 클라이언트와 슬래시 명령어
- `doneyet/check_commands.py`: `/check create` 등록 및 생성 권한 정책
- `doneyet/check_browser.py`: `/check list`, `/check info`, `/check delete`의 페이지·선택·확인 화면
- `doneyet/check_ui.py`: 생성 View·Modal, 설정 요약, Confirm·Cancel·timeout 처리
- `doneyet/database.py`: SQLite 스키마, 연결 관리, 초기화, aware datetime 직렬화
- `doneyet/models.py`: Check 입력 및 조회 결과 데이터 모델
- `doneyet/repository.py`: Check 입력 검증, 트랜잭션 저장, 서버별 조회
- `tests/test_repository.py`: Check 저장·조회, 서버 구분, 입력 검증 및 저장 실패 테스트
- `tests/test_database.py`: 임시 DB로 중복 제약, 외래키, 재초기화, rollback, datetime 검증
- `tests/test_check_ui.py`: Discord 응답 모의 객체와 임시 DB를 이용한 UI 흐름·저장 테스트
- `tests/test_check_browser.py`: 서버별 조회, 페이지 제한, 삭제 확인 및 rollback 검증
- `tests/test_command_sync.py`: 그룹 payload, sync 순서·응답 로그, 개발 Guild 설정 테스트
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
IANA 시간대 이름은 repository에서 검증합니다. 날짜 유효성과 직접 입력하는 timestamp의
형식 검증은 향후 데이터 입력 계층에서 수행해야 합니다. 현재 SQL은 이 문자열들을 강제 검증하지 않습니다.

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
`requirements.txt`에 `tzdata`를 추가했습니다. Reminder는 같은 날짜의 Check 시각 이후여야 합니다. 서로 다른 회차 간 간격은 제한하지 않습니다.

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

Repository는 동기 함수입니다. Discord async command에서 호출할 때는
`await asyncio.to_thread(repository.create_check, data)`처럼 실행합니다.
`/check create`는 아래 Step 3 UI를 통해 연결되며 `/test`는 기존대로 동작합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

기존 DB 테스트와 함께 공부·영양제 예시의 저장 및 재조회, 서버별 조회 범위,
잘못된 입력 거부, 저장 도중 실패 시 전체 rollback을 임시 DB에서 검증합니다.

## `/check create` 단일 설정 패널

`/check create`를 실행하면 실행자에게만 보이는 하나의 패널에 이름, 채널, 인증 방식,
요일, 참여자, 하루 횟수, 시간대, 각 회차의 현재 시간이 모두 표시됩니다.
단계 번호와 Next/Back은 없으며 원하는 순서로 설정합니다.

- 채널, 인증 방식, 요일, 참여자는 패널의 선택 메뉴에서 바로 수정합니다.
- **기본 설정**: 이름과 하루 횟수를 Modal에서 입력합니다.
- **회차 설정**: 회차 번호와 체크·리마인더 시각을 Modal에서 입력합니다.
  같은 번호를 다시 입력하면 해당 회차의 시간을 수정합니다.
- 수정 결과는 같은 메인 패널에 즉시 반영됩니다.
- **✅ 생성**: 모든 필수 설정을 검증한 뒤 repository로 저장합니다.
  누락된 항목은 함께 안내하며, 생성 전에는 DB에 기록하지 않습니다.
- **❌ 취소**: 저장하지 않고 종료합니다.

이름 최대 100자, 참여자 1~25명, 하루 1~25회, 시간대는 `Asia/Seoul`입니다.
모든 참여자가 같은 요일과 회차별 시간을 공유합니다. 하루 횟수를 줄이면 초과 회차의
초안이 제거되고, 늘리면 추가 회차의 시간 입력이 필요합니다.

현재 서버 멤버 누구나 생성할 수 있습니다. 생성 권한 정책은
`check_commands.py`의 `can_create_check()`에 분리되어 있습니다.
View와 Modal 모두 실행자·서버를 검사하며 다른 사용자는 ephemeral 안내를 받습니다.
5분 동안 조작하지 않으면 초안이 만료됩니다. 봇 재시작 시에도 미저장 초안은 사라집니다.
오래된 Modal 제출, 중복 생성 클릭, 저장 중 추가 조작을 차단합니다.
저장 실패 시 입력을 유지하고 기존 transaction/rollback으로 부분 저장을 방지합니다.
저장 완료 후 Discord 응답만 실패한 경우에도 중복 저장하지 않습니다.

### 시간 검증

기존 검증은 `HH:MM` 형식과 00:00~23:59 범위만 확인하여,
`14:00 → 13:00`도 통과했습니다. 이제 공통 함수
`repository.validate_schedule_input()`에서 **reminder_time > check_time**도 검사합니다.
동일 시각이나 다음 날로 넘어가는 Reminder는 v1에서 허용하지 않습니다.

| Check → Reminder | 결과 |
| --- | --- |
| 09:00 → 22:00 | 허용 |
| 14:00 → 13:00 | 거부 |
| 14:00 → 14:00 | 거부 |
| 22:00 → 23:30 | 허용 |
| 23:00 → 00:30 | 거부 |

회차 입력 직후 공통 검증을 호출하며 잘못된 값은 패널 상태에 반영하지 않습니다.
기존 값은 유지되고 ephemeral 오류가 표시됩니다. 회차 설정 버튼을 다시 눌러 수정합니다.
최종 생성에서도 `validate_check_input()`이 같은 시간 검증을 호출합니다.
repository 직접 호출 역시 DB 연결·INSERT 전에 검증하므로 UI를 우회해도 차단됩니다.
기존 DB row를 삭제·수정하거나 DB 스키마를 변경하지 않습니다.

### Discord에서 직접 테스트

실행 중인 봇을 `Ctrl+C`로 종료한 뒤 프로젝트 폴더에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py
```

1. `/test`가 기존대로 응답하는지 확인합니다.
2. `/check create` 실행 시 전체 설정과 네 선택 메뉴, 기본 설정·회차 설정·생성·취소 버튼이 보이는지 확인합니다.
3. 아무것도 입력하지 않고 생성을 눌러 누락 항목 안내를 확인합니다.
4. 요일·참여자부터 선택하는 등 순서를 바꾸어 설정하고, 같은 패널이 갱신되는지 확인합니다.
5. 기본 설정에서 이름과 하루 2회를 입력하고 채널·인증 방식을 선택합니다.
6. 회차 설정에서 1회차 `14:00 / 13:00`, `14:00 / 14:00`, `23:00 / 00:30`을 각각 입력합니다.
   오류가 나오고 기존 패널 값이 유지되는지 확인합니다.
7. 1회차 `09:00 / 22:00`, 2회차 `22:00 / 23:30`을 입력한 뒤 생성합니다.
   `DoneYet? Check Created`와 Check ID, 저장한 설정을 확인합니다.
8. 별도 생성 패널에서 취소 또는 5분 대기로 저장 없이 종료되는지 확인합니다.

### 자동 테스트

전체 54개: DB 5개, repository 6개, 생성 UI 21개, sync·설정 9개, 조회·삭제 13개입니다.
기존 검증 범위는 유지하고 Wizard 단계 이동 관련 테스트는 단일 패널 수정·회차 변경으로 갱신했습니다.
임시 DB와 Discord 모의 응답을 사용하며 운영 DB를 변경하지 않습니다.
추가 검증은 다섯 시간 조합, repository 직접 호출 시 미저장, 기존 잘못된 row 보존,
전체 설정 표시, 순서 없는 수정, 누락 항목 안내, 잘못된 입력 시 상태 유지,
회차 번호별 Modal 입력, 최종 생성 시 repository 호출입니다.

Scheduler, 자동 Check-in, Verification, Thread, Reminder 실행, Leaderboard,
Monthly Report 및 `/check edit`는 구현하지 않습니다.

## Check 조회·삭제 (Step 4)

- `/check list`: 현재 서버의 Check 이름, 채널, 인증 방식, 요일, 하루 횟수,
  참여자 수, Enabled를 한 페이지에 5개씩 표시합니다. 이전·다음 버튼으로 이동합니다.
- `/check info`: 현재 페이지의 선택 메뉴에서 Check를 고르면 참여자 목록과
  회차별 Sequence·Check Time·Reminder Time을 포함한 상세를 보여줍니다.
  상세가 길면 여러 페이지로 나눕니다. ID를 직접 입력할 필요가 없습니다.
- `/check delete`: 선택 → 삭제 대상 상세 확인 → Confirm 또는 Cancel 순서입니다.
  Confirm 전에는 DB를 변경하지 않습니다.

모든 화면은 실행자에게만 표시되며, 같은 서버의 실행자만 조작할 수 있습니다.
5분 timeout과 취소는 삭제하지 않고 종료합니다. 현재 생성과 마찬가지로 서버 멤버에게
열려 있으며 별도 관리자 권한 정책은 추가하지 않았습니다.
빈 목록, 이미 삭제된 대상, 저장소 오류를 안내합니다. 목록은 명령 실행 시점의
목록이며 새로 생성된 Check를 보려면 명령어를 다시 실행합니다.

조회·삭제는 모두 repository에 `guild_id`를 전달합니다. 선택한 ID를 신뢰하지 않고
현재 서버의 Check인지 다시 조회합니다. command 및 UI에는 SQL을 작성하지 않습니다.
동기 DB 함수는 `asyncio.to_thread()`로 호출합니다.

삭제는 기존 NO ACTION 외래키에 맞춰 하나의 트랜잭션에서
`verifications → daily_checkins → check_members → check_days → check_schedules → checks`
순서로 처리합니다. 해당 Check의 관련 DB 기록도 영구 삭제합니다.
중간 실패 시 모두 rollback되며 다른 Check는 유지됩니다. SQLite 스키마는 변경하지 않습니다.
Confirm 시 확인 화면의 설정과 DB의 설정을 비교하여 오래된 화면으로 변경된 대상이나
재사용된 ID의 새 Check를 삭제하지 못하게 합니다. Discord 메시지·채널·Thread는 삭제하지 않습니다.

### 직접 확인

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py
```

1. 봇을 재시작하고 `/test`, 기존 `/check create`를 확인합니다.
2. `/check list`에서 생성한 Check의 요약을 확인합니다. 6개 이상이면 다음 페이지도 확인합니다.
3. `/check info`에서 이름으로 선택해 참여자와 회차별 시간을 확인합니다.
4. `/check delete`에서 테스트용 Check를 선택하고 Cancel을 누른 뒤 목록에 남아 있는지 확인합니다.
5. 다시 선택해 Confirm을 누릅니다. 해당 Check만 목록에서 사라지는지 확인합니다.
6. Check가 없는 서버에서는 빈 목록 안내를 확인합니다.

추가 테스트는 세 명령어 진입, 현재 서버 제한, ID 조작 차단, 목록·상세 페이지,
Confirm 전 미삭제, 취소·timeout, 중복 Confirm, 관련 기록 삭제, 같은/다른 서버의 다른 Check 보존,
실패 시 rollback·재시도, 이미 삭제된 대상과 ID 재사용을 검증합니다.
실제 DB와 Discord에 영향을 주지 않는 임시 DB·모의 interaction 테스트입니다.

참고: [discord.py 명령어 및 UI API](https://discordpy.readthedocs.io/en/stable/interactions/api.html),
[python-dotenv 설정](https://pypi.org/project/python-dotenv/).
