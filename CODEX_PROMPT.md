# DoneYet? — Codex Implementation Prompts

이 문서는 DoneYet? v1 구현을 단계별로 진행하기 위한 Codex 프롬프트 모음이다.

중요 원칙:

- 항상 프로젝트의 `SPEC.md`를 기준으로 구현한다.
- 한 단계에서 다음 단계 기능을 미리 구현하지 않는다.
- 기존 기능을 깨뜨리지 않는다.
- 각 단계 완료 후 직접 실행 및 Discord 테스트를 진행한다.
- 테스트 완료 후 Git commit을 남긴다.
- 개인 Discord Server ID, User ID, Bot Token 등을 하드코딩하지 않는다.
- `.env`의 실제 값은 절대 출력하거나 Git에 포함하지 않는다.
- Windows 개발 환경과 Raspberry Pi OS 환경 모두에서 동작할 수 있도록 작성한다.


---

# Step 1 — SQLite 기반 데이터 계층 구현

현재 프로젝트의 `SPEC.md`를 기준으로 DoneYet? v1의 데이터 계층을 구현해줘.

현재 상태:

- Python + discord.py
- python-dotenv 사용
- `.env` / `.env.example` 구성 완료
- `/test` slash command 정상 동작
- Windows에서 개발 중
- 추후 Raspberry Pi OS Lite에서 운영 예정

이번 작업 범위:

1. SQLite 초기화 코드 작성
2. 다음 테이블 생성
   - checks
   - check_days
   - check_schedules
   - check_members
   - daily_checkins
   - verifications
3. `SPEC.md`의 Unique Constraint 반영
4. DB 파일은 `data/doneyet.db`에 생성
5. `data/*.db`가 Git에 포함되지 않도록 `.gitignore` 확인 및 필요하면 수정
6. 봇 시작 시 DB가 없으면 자동 생성
7. DB 초기화 로직은 Discord command 코드와 분리
8. Foreign Key 사용
9. SQLite foreign_keys pragma 활성화
10. datetime은 추후 timezone-aware 처리가 가능하도록 구조 설계

구현하지 말 것:

- `/check create`
- scheduler
- verification
- thread
- reminder
- leaderboard

기존 `/test` 기능은 그대로 유지할 것.

구현 전에 현재 프로젝트 구조와 `SPEC.md`를 먼저 확인하고,
현재 구조에 맞는 최소한의 변경만 해줘.

작업 후 다음 내용을 설명해줘.

- 생성한 파일
- 수정한 파일
- 각 파일의 역할
- 실제 생성되는 DB schema
- Unique Constraint
- 실행 테스트 방법


---

# Step 2 — Check 생성 기능 구현

`SPEC.md`와 현재 구현 상태를 확인한 뒤 `/check create` 기능을 구현해줘.

이번 단계에서는 "Check 생성 및 DB 저장"만 구현한다.

Check 생성 시 필요한 설정:

- name
- channel
- participants
- verification_mode
  - button
  - photo
  - either
- active weekdays
- 하루 session 수
- 각 session의 check_time
- 각 session의 reminder_time

v1 규칙:

- 하나의 Check에 참여하는 모든 사용자는 동일한 schedule을 공유한다.
- 참여자별 개별 schedule은 구현하지 않는다.
- active weekday는 사용자가 선택한다.
- session 개수만큼 check_schedules row를 생성한다.
- `check_schedules`의 개수가 해당 Check의 하루 체크 횟수를 의미한다.

Discord UX는 Slash Command + Discord UI를 적절히 조합해도 된다.

한 번의 slash command에 모든 값을 억지로 넣지 말고,
Discord의 Modal / Select Menu / User Select 등을 활용해
사용하기 쉬운 흐름으로 구현해줘.

입력 검증:

- 이름이 비어 있으면 안 됨
- session이 최소 1개 필요
- active weekday가 최소 1개 필요
- reminder_time은 해당 session의 check_time보다 이후여야 함
- 잘못된 HH:MM 입력 방지
- verification mode 검증
- 중복 participant 방지

Check 생성이 끝나면 Embed로 설정 요약을 보여줘.

예:

DoneYet? Check created

이름: 영양제
채널: #영양제
인증 방식: Button
요일: 매일
참여자: 3명

Session 1
Check: 09:00
Reminder: 22:00

중요:

- DB 저장은 transaction으로 처리
- 저장 중 오류 발생 시 부분 데이터가 남지 않도록 rollback
- Discord ID는 문자열 또는 SQLite INTEGER 범위를 고려하여 안전하게 저장
- 개인 Server ID 등을 하드코딩하지 않음

아직 구현하지 말 것:

- 실제 scheduled message 전송
- verification
- photo detection
- reminder
- leaderboard

작업 후:

- 수정/생성 파일
- Discord에서 테스트하는 방법
- DB에서 저장 결과 확인 방법

을 설명해줘.


---

# Step 3 — Check 조회 및 관리 기능 구현

`SPEC.md`와 현재 코드를 확인하고 Check 조회 기능을 구현해줘.

이번 작업 범위:

1. `/check list`
2. `/check info`
3. `/check delete`

`/check list`

현재 Discord 서버에 등록된 Check 목록을 보여준다.

표시 정보:

- Check 이름
- 연결된 channel
- verification mode
- active weekdays
- daily session 수
- 참여자 수

Check가 없으면 적절한 안내 메시지를 보여준다.


`/check info`

특정 Check의 상세 설정을 보여준다.

표시 정보:

- name
- channel
- verification mode
- active weekdays
- participants
- 각 session의 sequence
- check_time
- reminder_time
- enabled 여부


`/check delete`

특정 Check를 삭제한다.

요구사항:

- 실수 방지를 위해 확인 UI를 제공
- 삭제를 확정해야 실제 DB에서 삭제
- foreign key cascade 또는 명시적 cleanup으로 관련 데이터 처리
- 다른 Check에는 영향을 주면 안 됨

아직 구현하지 말 것:

- scheduler
- verification
- reminder
- leaderboard

기존 기능을 깨뜨리지 않을 것.

작업 후 Discord에서 각각 테스트하는 절차를 알려줘.


---

# Step 4 — 참여자 관리 기능 구현

`SPEC.md`를 기준으로 Check 참여자 관리 기능을 구현해줘.

이번 작업 범위:

- `/check member add`
- `/check member remove`

요구사항:

`/check member add`

- Check 선택
- Discord 사용자 선택
- 이미 참여 중이면 중복 추가하지 않음
- 성공 시 확인 메시지


`/check member remove`

- Check 선택
- 현재 참여자 중 사용자 선택
- 참여자가 아니면 오류 안내
- 성공 시 확인 메시지

v1에서는:

- 개별 Discord User 기반으로만 참여자를 관리한다.
- Role 기반 참여는 구현하지 않는다.
- Self Join / Self Leave도 구현하지 않는다.
- 참여자별 개별 Schedule은 구현하지 않는다.

중요:

- 채널 접근 권한과 Check 참여 여부는 독립적이다.
- 해당 채널을 볼 수 있어도 Check participant가 아니면 인증 대상이 아니다.

추후 verification 기능에서 사용할 수 있도록
`is_check_member(check_id, user_id)` 형태의 재사용 가능한 로직을 구성해줘.

작업 후 테스트 절차를 알려줘.


---

# Step 5 — Button Verification 구현

현재 코드와 `SPEC.md`를 기준으로 Button 인증 기능을 구현해줘.

이번 단계에서는 scheduler 없이,
개발자가 테스트용으로 Check-in 메시지를 생성할 수 있는 형태도 허용한다.

목표:

Button verification 동작 자체를 먼저 완성한다.

Check-in 메시지는 다음 정보를 포함한다.

- Check 이름
- 날짜
- session sequence
- 참여자
- ✅ 완료 Button

Button 클릭 시:

1. 클릭한 사용자가 해당 Check participant인지 확인
2. participant가 아니면 ephemeral 메시지로 안내
3. 해당 날짜 + schedule + user에 이미 verification이 존재하는지 확인
4. 없으면 verification 생성
5. 있으면 중복 생성하지 않음
6. 성공 시 ephemeral 완료 메시지 출력

Verification 저장 기준:

Unique:

check_id + schedule_id + user_id + date

verification_method:

button

요구사항:

- 같은 버튼을 여러 번 눌러도 DB에는 1회만 기록
- Either mode에서도 button 인증 가능하도록 재사용 가능한 구조
- Photo-only mode에서는 button을 제공하지 않도록 설계
- Bot restart 후에도 이미 생성된 check-in button interaction이 가능한 방향을 고려
  - discord.py persistent view 사용 가능 여부 검토
  - 구현 가능하면 persistent custom_id 기반으로 작성

아직 구현하지 말 것:

- 실제 시간 scheduler
- photo verification
- reminder
- leaderboard

테스트를 쉽게 할 수 있는 방법을 함께 제공해줘.


---

# Step 6 — Daily Scheduler 구현

현재 `SPEC.md`와 구현된 DB 구조를 기준으로 Daily Scheduler를 구현해줘.

목표:

각 Check의 active weekday와 session schedule을 읽어서
지정된 시각에 Check-in 메시지를 자동 생성한다.

조건:

- Check가 enabled 상태여야 함
- 오늘 요일이 active day여야 함
- 해당 session의 check_time이 되었을 때 실행
- 해당 날짜와 schedule의 Daily Check-in이 이미 존재하면 다시 생성하지 않음

DB:

`daily_checkins`

Unique:

check_id + schedule_id + date

Scheduler 요구사항:

- timezone-aware
- Check timezone 사용
- 기본값 Asia/Seoul
- 서버 OS의 local timezone에 의존하지 않음
- 봇 재시작에 안전해야 함
- loop가 같은 작업을 두 번 호출해도 DB 기준으로 중복 생성되지 않아야 함
- Raspberry Pi에서 장기 실행 가능한 단순하고 안정적인 방식 사용
- busy wait 사용하지 않음

Check-in message 생성 후:

- message_id 저장
- 필요한 경우 thread_id는 이후 단계에서 저장

Button / Either mode:

- 기존 Button Verification UI 포함

Photo mode:

- 아직 thread 생성은 다음 단계에서 구현해도 됨

봇 시작 시 scheduler가 자동 시작되도록 구성하되
기존 `/test` 및 다른 commands가 정상 동작해야 한다.

작업 후 다음 상황을 테스트하는 방법을 알려줘.

1. 정상 시간 실행
2. 같은 날짜 중복 생성 방지
3. 봇 재시작 후 중복 생성 방지
4. active weekday가 아닌 날 실행되지 않는지


---

# Step 7 — Photo Verification + Daily Thread 구현

`SPEC.md`를 기준으로 Photo Verification을 구현해줘.

대상 verification mode:

- photo
- either

Daily Check-in이 생성될 때 Public Thread도 생성한다.

Thread 이름:

YYYY-MM-DD · N회차 인증

예:

2026-09-11 · 1회차 인증

생성된 thread_id는 `daily_checkins`에 저장한다.

Thread 내 메시지를 감지하여 인증을 처리한다.

Photo verification 조건:

1. 메시지가 DoneYet?이 관리하는 verification thread 안에 있어야 함
2. 작성자가 해당 Check의 participant여야 함
3. attachment가 최소 1개 있어야 함
4. attachment가 image인지 확인
5. 해당 날짜 + schedule + user verification이 없어야 함

verification_method:

photo

텍스트만 있는 메시지는 인증으로 처리하지 않는다.

Either mode:

- Button 또는 Photo 중 먼저 성공한 인증을 1회로 기록
- 이후 다른 방법으로 인증해도 새로운 record를 생성하지 않음

중요:

- 실제 이미지 내용을 AI로 분석하지 않는다.
- 사진이 삭제되더라도 이미 DB에 저장된 verification은 유지한다.
- SQLite가 Source of Truth이다.
- bot 메시지나 다른 webhook 메시지는 인증 대상으로 처리하지 않는다.

작업 후 다음 테스트 방법을 설명해줘.

- participant 사진 업로드
- non-participant 사진 업로드
- 텍스트만 업로드
- 같은 사람 중복 사진
- Either mode button → photo
- Either mode photo → button


---

# Step 8 — Reminder + Thread 종료 처리

`SPEC.md`를 기준으로 Reminder와 Daily Thread 종료 기능을 구현해줘.

## Reminder

각 session의 reminder_time이 되면
해당 날짜 / 해당 session의 미인증 participant를 조회한다.

인증하지 않은 사람만 mention한다.

예:

🔔 아직 2회차 체크를 완료하지 않았어요.

@UserA @UserC

조건:

- 완료한 사용자는 mention하지 않음
- 모든 참여자가 완료했다면 reminder를 보내지 않음
- 같은 reminder가 여러 번 전송되지 않아야 함
- bot restart 후에도 중복 reminder를 전송하지 않아야 함

이를 위해 필요한 경우 DB에 reminder_sent_at 또는 별도 상태 필드를 추가해도 된다.
Schema 변경이 필요하면 migration 또는 기존 개발 DB에 안전한 처리 방식을 고려한다.


## Thread Close

날짜가 종료되면 해당 날짜의 Photo / Either verification thread를:

1. Lock
2. Archive

한다.

조건:

- 이미 archived / locked 상태면 다시 처리하지 않아도 됨
- Button-only Check에는 thread가 없음
- thread 처리 실패가 scheduler 전체를 중단시키지 않도록 예외 처리

지난 날짜 thread에서는 인증을 인정하지 않는다.

작업 후:

- reminder 중복 방지
- restart 후 reminder
- thread lock
- thread archive

테스트 절차를 설명해줘.


---

# Step 9 — Leaderboard 구현

`SPEC.md`를 기준으로 월간 leaderboard를 구현해줘.

Command:

`/check leaderboard`

사용자가 선택할 값:

- Check
- 대상 연도/월
  - 기본값은 현재 월

집계 기준:

완료한 verification 수 / 예정된 verification 수

예:

🏆 2026년 9월 — 영양제

1. User A — 58 / 60 (96.7%)
2. User B — 55 / 60 (91.7%)
3. User C — 49 / 60 (81.7%)

예정 횟수 계산 시:

- Check active weekdays
- 해당 월의 실제 달력
- 하루 session 수
- participant의 참여 기간

을 고려해줘.

중요:

참여자가 월 중간에 추가된 경우
가입 전 날짜까지 예정 횟수에 포함시키지 않아야 한다.

이를 위해 `check_members.joined_at`을 활용한다.

참여자가 제거된 경우까지 정확히 처리하려면
현재 schema만으로 부족한지 검토하고,
필요하다면 history를 보존할 수 있는 최소 schema 변경을 제안하고 구현해줘.

단순히 현재 check_members에 있는 사용자만 계산하면
과거 leaderboard가 틀어질 수 있으므로 이 문제를 반드시 고려해줘.

정렬:

1. completion rate
2. completed count
3. 안정적인 tie-break

Embed 형태로 보여줘.

아직 streak 기능은 구현하지 않는다.

작업 후 계산 예시와 테스트 방법을 설명해줘.


---

# Step 10 — Monthly Automatic Report 구현

`SPEC.md`를 기준으로 Monthly Automatic Report 기능을 구현해줘.

목표:

월이 끝난 후 각 Check의 지난달 leaderboard를
해당 Check channel에 자동 게시한다.

예:

🏆 2026년 9월 DoneYet? 결과

💊 영양제

1. User A — 58 / 60 (96.7%)
2. User B — 55 / 60 (91.7%)
3. User C — 49 / 60 (81.7%)

다음 달도 DoneYet?

요구사항:

- leaderboard 계산 로직을 재사용
- 동일 월 report가 중복 게시되지 않도록 DB 상태 저장
- bot restart에도 안전
- timezone 기준으로 월 변경 판단
- report 게시 실패가 다른 Check scheduler를 중단시키지 않도록 처리

가능하면 월 마지막 날 자정 직전보다
새 달이 시작된 이후 지난달 데이터를 확정해서 게시하는 구조로 구현해줘.

작업 후 테스트를 위해
실제 한 달을 기다리지 않고 강제로 report 함수를 실행할 수 있는 방법도 제공해줘.


---

# Step 11 — Check Edit 기능 구현

현재 구현된 DoneYet? 기능과 `SPEC.md`를 기준으로
`/check edit` 기능을 구현해줘.

수정 가능한 항목:

- name
- channel
- verification mode
- active weekdays
- sessions
  - session 추가
  - session 삭제
  - check_time 수정
  - reminder_time 수정
- enabled

주의:

과거 verification 및 daily_checkins 기록은 보존해야 한다.

Schedule을 수정할 때 이미 과거에 사용된 `schedule_id`를
무분별하게 삭제하여 historical record가 깨지지 않도록 설계해줘.

필요하다면:

- schedule active flag
- effective date
- soft delete

등의 방식을 검토해
과거 데이터와 현재 설정을 모두 안정적으로 유지해줘.

단순히 기존 row를 삭제하고 새로 만드는 방식 때문에
과거 leaderboard가 잘못되지 않도록 특히 주의해줘.

작업 전에 현재 schema를 검토하고
필요한 schema 변경이 있으면 이유를 먼저 설명한 뒤 구현해줘.

Discord UI는 가능한 한 간단하게 구성해줘.


---

# Step 12 — Restart Safety / Recovery 강화

DoneYet?의 현재 전체 구현을 검토하고
restart safety와 recovery 처리를 강화해줘.

`SPEC.md`의 Restart Safety 원칙을 따른다.

확인할 항목:

- Check-in 중복 생성
- Thread 중복 생성
- Verification 중복 생성
- Reminder 중복 전송
- Monthly Report 중복 전송
- Bot startup 시 놓친 task 처리

예:

09:00 check-in 예정
08:50 bot 종료
09:20 bot 재시작

이 경우 오늘의 09:00 check-in을 어떻게 처리할지
일관된 recovery policy를 정해서 구현해줘.

권장:

- 오늘 발생했어야 하는 작업 중 아직 처리되지 않은 작업은 startup 시 복구
- 지나치게 오래 지난 작업까지 뒤늦게 보내지는 않도록 합리적인 기준 설정

DB Unique Constraint를 최종 방어선으로 사용하고,
scheduler 코드 자체도 idempotent하게 작성해줘.

SQLite transaction 및 concurrency도 검토해줘.

작업 후 아래 시나리오별 결과를 설명해줘.

1. check_time 전에 restart
2. check_time 직후 restart
3. reminder 전 restart
4. reminder 후 restart
5. 자정 직전/직후 restart


---

# Step 13 — Error Handling / Logging 정리

현재 프로젝트 전체를 검토하고 운영용 error handling과 logging을 정리해줘.

목표:

Raspberry Pi에서 DoneYet?을 장기간 실행할 수 있는 수준으로 만든다.

요구사항:

- Python logging 사용
- print 위주의 debug 출력 정리
- startup 로그
- Discord login 완료 로그
- DB initialization 로그
- scheduler 주요 이벤트 로그
- command error 로그
- thread creation 실패 로그
- SQLite 오류 로그
- Discord API 오류 로그

Secret 정보는 로그에 출력하지 않는다.

특히 다음 값 출력 금지:

- Discord token
- Client secret
- `.env` 전체 내용

예외 하나 때문에 scheduler loop 전체가 죽지 않도록 처리한다.

단, 예외를 무조건 삼키지 말고
문제 추적이 가능하도록 traceback 또는 적절한 exception 로그를 남긴다.

개발 중 사용할 로그 레벨과
운영 시 사용할 로그 레벨도 쉽게 설정할 수 있도록 구성해줘.


---

# Step 14 — Test 구조 정리

현재 DoneYet? 코드에서
Discord API 없이 테스트 가능한 핵심 로직을 분리하고 테스트를 작성해줘.

우선 테스트 대상:

- weekday 판단
- schedule 판단
- HH:MM validation
- verification unique 처리
- 예정 횟수 계산
- leaderboard 계산
- participant validation
- restart recovery 판단

pytest를 사용해도 된다.

Discord API 자체를 복잡하게 mock하는 테스트보다
비즈니스 로직을 Discord 코드에서 분리하여
순수 함수 또는 service 단위 테스트를 만드는 것을 우선한다.

테스트 실행:

pytest

한 번에 모든 architecture를 갈아엎지 말고,
현재 구조에서 필요한 범위만 refactor해줘.

기존 실제 Discord 동작이 깨지지 않도록 한다.

작업 후:

- 테스트 목록
- 각 테스트 목적
- 실행 명령어

를 설명해줘.


---

# Step 15 — Raspberry Pi Deployment 준비

현재 DoneYet? 프로젝트를 Raspberry Pi OS Lite에서
24시간 실행할 수 있도록 deployment 구성을 준비해줘.

대상:

- Raspberry Pi
- Raspberry Pi OS Lite
- Python
- SQLite
- systemd
- GitHub clone 기반 설치

이번 단계에서는 Docker를 사용하지 않는다.

준비할 내용:

1. Python virtual environment 설치 방법
2. requirements 설치
3. `.env` 생성 방법
4. DB directory 권한
5. bot 수동 실행 방법
6. systemd service 파일 예제
7. 부팅 시 자동 시작
8. crash 시 자동 재시작
9. service status 확인
10. logs 확인
11. service restart / stop 방법
12. GitHub에서 새 버전 pull 후 업데이트하는 방법

Repository에 포함하면 좋은 경우:

- `deploy/doneyet.service.example`
- deployment 관련 README 문서

단:

- 실제 username
- 실제 home directory
- 실제 token

등을 하드코딩하지 않는다.

Raspberry Pi뿐 아니라 일반 Linux에서도 수정해서 사용할 수 있는 형태로 작성해줘.


---

# Step 16 — Final v1 Review

DoneYet? v1 전체 코드를 `SPEC.md` 기준으로 최종 검토해줘.

새로운 기능을 추가하는 단계가 아니다.

다음 항목을 집중적으로 확인해줘.

## Functional

- Check 생성
- Check 조회
- Check 수정
- Check 삭제
- participant 관리
- active weekday
- multiple daily sessions
- Button Verification
- Photo Verification
- Either Verification
- Reminder
- Thread lifecycle
- Leaderboard
- Monthly Report


## Data Integrity

- Foreign Keys
- Unique Constraints
- historical data
- participant history
- schedule history
- restart safety


## Discord

- 최소 권한
- participant 아닌 사용자 처리
- persistent button
- thread 처리
- ephemeral response


## Security

- token hardcoding 없음
- secret logging 없음
- `.env` gitignore 확인
- 개인 Server ID/User ID hardcoding 없음


## Deployment

- Windows 실행
- Linux 실행
- Raspberry Pi 실행
- systemd


## Code Quality

- 지나친 파일 분리 여부
- 중복 코드
- dead code
- 지나친 abstraction
- error handling
- typing
- comments
- README와 실제 구현 일치 여부

문제가 있다면 우선순위를:

- Critical
- Important
- Nice to have

로 나눠서 설명하고,
Critical / Important 항목만 수정해줘.

SPEC에 없는 신규 기능은 추가하지 말 것.

마지막으로 DoneYet? v1이 실제 사용 가능한 상태인지 평가하고,
남아 있는 제한사항을 정리해줘.