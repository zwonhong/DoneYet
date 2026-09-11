# DoneYet? — Codex Implementation Prompts

이 문서는 DoneYet? v1 구현을 단계별로 진행하기 위한 Codex 프롬프트 모음이다.

중요 원칙:

모든 단계에서 다음 원칙을 지킨다.

- 작업 전 `SPEC.md`와 현재 프로젝트 구조를 먼저 확인한다.
- 이미 구현된 model / repository / database 기능을 우선 재사용한다.
- 동일한 validation 또는 DB 접근 로직을 command 코드에 중복 구현하지 않는다.
- 현재 통과하고 있는 테스트를 깨뜨리지 않는다.
- 이번 단계에서 요구하지 않은 다음 단계 기능을 미리 구현하지 않는다.
- 개인 Discord Server ID, User ID, Bot Token을 하드코딩하지 않는다.
- `.env`의 실제 값을 출력하거나 Git에 포함하지 않는다.
- Windows와 Raspberry Pi OS에서 모두 실행 가능한 구조를 유지한다.
- 불필요한 대규모 refactoring이나 과도한 abstraction을 하지 않는다.
- 작업 완료 후 전체 unittest를 실행하고 기존 기능이 유지되는지 확인한다.


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

# Step 3 — `/check create` Discord UI

현재 DoneYet?에는 다음 기능이 이미 구현되어 있다.

- Discord bot 실행
- `/test`
- SQLite 초기화
- Check 데이터 모델
- Check repository
- Check + active days + participants + sessions 일괄 저장
- 저장 실패 시 transaction rollback
- 서버별 Check 저장/조회
- repository 관련 unittest

현재 구현과 `SPEC.md`를 먼저 확인한 뒤,
Discord에서 실제 Check를 생성할 수 있는 `/check create` 기능을 구현해줘.

## 생성할 설정

사용자는 다음 항목을 설정할 수 있어야 한다.

- Check 이름
- Discord Channel
- Participants
- Verification Mode
  - button
  - photo
  - either
- Active Weekdays
- Daily Sessions
- 각 Session의:
  - Check Time
  - Reminder Time

v1에서는 모든 participant가 같은 schedule을 공유한다.

참여자별 개별 schedule은 구현하지 않는다.


## Discord UX

Discord Slash Command 한 번에 모든 값을 억지로 입력시키지 말고,
필요하면 다음 Discord UI를 조합하여 단계형 설정 UI를 구현한다.

- View
- Button
- Select
- ChannelSelect
- UserSelect
- Modal

사용 흐름은 최대한 단순하게 구성한다.

예:

/check create
↓
기본 설정
↓
요일 선택
↓
참여자 선택
↓
Session 설정
↓
설정 요약
↓
Confirm / Cancel


## 요구사항

1. 모든 설정이 완료되기 전에는 DB에 저장하지 않는다.
2. 최종 Confirm 시 기존 repository 저장 기능을 사용한다.
3. Cancel할 수 있어야 한다.
4. UI는 명령어를 실행한 사용자만 조작할 수 있어야 한다.
5. 다른 사용자가 조작하면 ephemeral 안내를 보낸다.
6. timeout을 처리한다.
7. Verification Mode는 선택 UI를 사용한다.
8. Active Weekdays는 복수 선택 가능해야 한다.
9. Participants는 복수 사용자 선택 가능해야 한다.
10. Session 수에 맞춰 각 회차의 시간을 입력받는다.
11. 기존 model/repository validation을 최대한 재사용한다.
12. 잘못된 입력은 ephemeral 메시지로 알려준다.
13. 저장 실패 시 부분 데이터가 남지 않아야 한다.
14. 생성 성공 후 Embed로 최종 설정을 보여준다.

예:

DoneYet? Check Created

이름: 영양제
채널: #영양제
인증 방식: Button
요일: 매일
참여자: 3명
하루 체크: 2회

1회차
09:00 → Reminder 12:00

2회차
21:00 → Reminder 23:00


## 권한

누가 Check를 생성할 수 있는지 현재 SPEC에 명확한 정책이 없다면,
이번 단계에서는 임의로 강한 Discord 권한을 요구하지 말고
현재 구조에 가장 단순한 정책을 사용한다.

향후 관리자 권한 정책을 추가할 수 있도록 command 로직을 분리한다.


## 이번 단계에서 구현하지 말 것

- Scheduler
- 실제 Check-in 메시지 자동 생성
- Verification
- Photo Detection
- Verification Thread
- Reminder
- Leaderboard
- Monthly Report


## 작업 완료 후

다음을 알려줘.

- 생성/수정 파일
- Discord UI 흐름
- repository와 command가 연결되는 방식
- Discord에서 직접 테스트하는 순서
- 추가된 unittest
- 전체 테스트 결과


---

# Step 4 — Check 조회 / 삭제

현재 코드와 `SPEC.md`를 확인하고
Discord에서 생성된 Check를 조회하고 삭제할 수 있도록 구현해줘.

이번 작업 범위:

- `/check list`
- `/check info`
- `/check delete`


## `/check list`

현재 Discord Guild에 등록된 Check만 보여준다.

표시:

- Check 이름
- Channel
- Verification Mode
- Active Weekdays
- Daily Sessions
- Participant 수
- Enabled 여부

Check가 없다면 적절한 안내 메시지를 표시한다.

Check가 많아 Discord 메시지 길이 제한을 넘을 가능성도 고려한다.


## `/check info`

특정 Check를 선택하여 상세 설정을 보여준다.

표시:

- Name
- Channel
- Verification Mode
- Active Weekdays
- Participants
- Daily Sessions
- 각 Session의:
  - Sequence
  - Check Time
  - Reminder Time
- Enabled


가능하면 Check ID를 직접 입력시키기보다
현재 Guild의 Check를 Discord 선택 UI로 선택할 수 있게 한다.


## `/check delete`

특정 Check를 삭제한다.

실수 방지를 위해:

삭제 대상 표시
→ Confirm / Cancel

흐름을 사용한다.

Confirm 전에는 DB를 변경하지 않는다.

삭제 후 관련 데이터 처리 방식은
현재 Foreign Key 및 repository 구조를 확인하여 구현한다.

다른 Check 데이터에는 영향을 주면 안 된다.


## 중요

- 현재 Guild의 Check만 접근 가능
- 다른 Guild의 Check를 ID 조작 등으로 조회/삭제할 수 없어야 함
- DB 접근 로직은 repository에 둔다.
- command에서 SQL을 직접 작성하지 않는다.


## 아직 구현하지 말 것

- `/check edit`
- Scheduler
- Verification
- Reminder
- Leaderboard


## 완료 후

- 직접 테스트 방법
- 추가 테스트
- 전체 unittest 결과

를 알려줘.


---

# Step 5 — Participant 관리

`SPEC.md`와 현재 구현을 기준으로
Check 생성 후 participant를 관리할 수 있도록 구현해줘.

명령:

- `/check member add`
- `/check member remove`


## Add

사용 흐름:

Check 선택
→ Discord User 선택
→ 추가

조건:

- 현재 Guild의 Check만 선택 가능
- 이미 participant라면 중복 추가하지 않는다.
- Bot 계정 추가를 허용할 필요가 없다면 차단한다.
- 성공 시 ephemeral 또는 적절한 확인 메시지를 표시한다.


## Remove

사용 흐름:

Check 선택
→ 현재 Participant 선택
→ 제거

조건:

- participant가 아닌 사용자를 제거할 수 없음
- 다른 Check에는 영향 없음


## 데이터 구조

현재 `check_members` 구조와 repository를 먼저 확인한다.

향후 leaderboard에서 다음 문제가 발생한다.

- 월 중간 participant 추가
- 월 중간 participant 제거
- 과거 leaderboard 계산

따라서 participant 제거 시 row를 단순 삭제하면
과거 참여 이력이 사라지는 문제가 있는지 검토해줘.

현재 schema로 이력을 보존할 수 없다면,
이번 단계에서 최소한의 participant history 구조를 도입해도 된다.

예:

- joined_at
- left_at
- active

단, 필요 이상의 구조 변경은 하지 않는다.


## 재사용 가능한 기능

향후 verification에서 사용할 수 있도록 다음과 같은
재사용 가능한 participant 확인 기능을 제공한다.

예:

is_check_member(check_id, user_id)


## v1에서 구현하지 않는 것

- Role 기반 참여
- Self Join
- Self Leave
- 사용자별 Schedule


## 완료 후

participant 추가/삭제 및
과거 participation history가 어떻게 유지되는지 설명해줘.


---

# Step 6 — Button Verification

현재 코드와 `SPEC.md`를 기준으로
Button Verification 기능을 구현해줘.

아직 실제 Scheduler는 구현하지 않는다.

이번 단계에서는 Button 인증 자체를 테스트할 수 있도록
개발용 Check-in 생성 방법을 제공해도 된다.


## 대상 Mode

- button
- either


Photo mode에서는 Button을 제공하지 않는다.


## Check-in UI

예:

💊 영양제 — 1/2

2026-09-11 · 1회차

[ ✅ 완료 ]


## Button 클릭

Button을 클릭하면:

1. 해당 Check 확인
2. 해당 Schedule 확인
3. 클릭한 사용자가 participant인지 확인
4. 해당 날짜에 실제 참여 상태였는지 확인
5. 이미 verification이 존재하는지 확인
6. 없으면 verification 생성
7. 있으면 중복 생성하지 않음


Unique 기준:

check_id + schedule_id + user_id + date


verification_method:

button


## 사용자 응답

성공:

인증 완료! ✅

이미 인증:

이미 이번 회차를 완료했어요. ✅

비참여자:

이 Check의 참여자가 아닙니다.


가능하면 ephemeral로 응답한다.


## Persistent View

Raspberry Pi에서 bot이 재시작될 수 있으므로
Discord.py Persistent View를 고려한다.

기존 Check-in 메시지의 Button이
bot restart 이후에도 동작할 수 있도록:

- stable custom_id
- persistent View

구조를 사용하는 것이 적절한지 검토하고 구현한다.


## 중요

- 같은 Button 여러 번 클릭 → DB 1회
- DB Unique Constraint를 최종 방어선으로 사용
- Either mode에서 Button 후 Photo를 해도 최종 인증은 1회여야 함
- 날짜/session/check를 interaction payload만 믿지 말고 DB와 일관성을 확인


## 아직 구현하지 말 것

- Scheduler
- Photo Verification
- Reminder
- Leaderboard


## 완료 후

실제 Discord에서 Button 인증을 테스트할 수 있는 절차를 제공해줘.


---

# Step 7 — Daily Scheduler

`SPEC.md`와 현재 구현을 기준으로
실제 Check-in Scheduler를 구현해줘.

## 실행 조건

Check가 다음 조건을 만족할 때 해당 Session의 Check-in을 생성한다.

- enabled
- 현재 날짜가 Active Weekday
- 현재 시간이 해당 Session의 check_time에 도달
- 해당 날짜 + Session Check-in이 아직 생성되지 않음


## Check-in 저장

`daily_checkins`에 저장한다.

Unique:

check_id + schedule_id + date


Check-in 메시지 생성 성공 후 필요한 Discord ID를 저장한다.

예:

- message_id
- thread_id


## Verification Mode

button:
- Button 포함

either:
- Button 포함
- Thread는 다음 단계에서 추가

photo:
- 현재 단계에서는 기본 Check-in 메시지만 생성
- Thread는 다음 단계


## Scheduler 요구사항

- timezone-aware
- Check timezone 사용
- 기본값 Asia/Seoul
- OS local timezone에 의존하지 않음
- busy waiting 사용하지 않음
- Raspberry Pi에서 장기 실행 가능한 방식
- 같은 task가 여러 번 평가되어도 중복 생성되지 않음
- 한 Check에서 오류가 발생해도 전체 scheduler가 죽지 않음


## Restart Safety

DB를 기준으로 이미 생성된 Check-in을 확인한다.

예:

09:00 Check-in 생성
09:30 bot restart

→ 09:00 Check-in을 다시 생성하지 않음


Startup 시 놓친 Check-in을 복구하는 정책은
현재 단계에서는 단순하고 명확하게 정의한다.

너무 오래 지난 Check-in을 무조건 뒤늦게 생성하지 않도록 한다.


## 테스트

실제 시간을 오래 기다리지 않고 테스트할 수 있도록
scheduler의 핵심 판단 로직은 Discord 코드와 분리한다.

다음 테스트를 작성한다.

- Active weekday
- Inactive weekday
- Check time 도달
- 중복 Check-in
- restart 후 중복 방지
- timezone


---

# Step 8 — Photo / Either Verification Thread

`SPEC.md`를 기준으로 Photo Verification을 구현해줘.

대상:

- photo
- either


## Thread 생성

Daily Check-in 생성 시 Public Thread를 생성한다.

Thread 이름:

YYYY-MM-DD · N회차 인증

예:

2026-09-11 · 1회차 인증


생성된 `thread_id`를 `daily_checkins`에 저장한다.


## Photo 인증 조건

Thread에 올라온 메시지가 다음 조건을 모두 만족해야 한다.

1. DoneYet?이 관리하는 Verification Thread
2. 해당 Check participant가 작성
3. 해당 날짜에 실제 participant 상태
4. Attachment가 최소 1개 존재
5. Attachment가 image
6. 아직 해당 Session verification이 없음


성공 시:

verification_method = photo


## 처리하지 않는 것

- 일반 텍스트
- 다른 Thread의 사진
- 비참여자 사진
- Bot 메시지
- Webhook 메시지
- 이미지가 아닌 일반 파일


## Either

Button 또는 Photo 중 먼저 성공한 방식만
해당 회차 인증으로 기록한다.

Button → Photo:
추가 record 없음

Photo → Button:
추가 record 없음


## 이미지 내용

이미지 내용 자체는 분석하지 않는다.

AI Image Verification은 v1 범위가 아니다.

이미 인증된 사진을 사용자가 나중에 삭제해도
DB verification은 유지한다.


## 테스트

- 정상 사진
- 비참여자 사진
- 텍스트
- 일반 파일
- 중복 사진
- Either button → photo
- Either photo → button


---

# Step 9 — Reminder + Thread 종료

현재 Schedule과 Verification 데이터를 기반으로
Reminder와 Daily Thread 종료를 구현해줘.


## Reminder

각 Session의 `reminder_time`에
아직 인증하지 않은 participant만 조회한다.

예:

🔔 아직 2회차 체크를 완료하지 않았어요.

@UserA @UserC


이미 인증한 사용자는 제외한다.

모든 participant가 인증했다면
Reminder 메시지를 보내지 않는다.


## Reminder 중복 방지

동일 Check + Date + Session Reminder는
최대 한 번만 전송한다.

bot restart 이후에도 중복 전송하면 안 된다.

필요하면 DB에:

- reminder_sent_at

또는 별도 상태를 저장한다.


## Thread 종료

해당 날짜가 종료되면
Photo / Either Verification Thread를:

1. Lock
2. Archive

한다.


Button-only Check에는 Thread가 없다.


## 지난 Thread 인증

날짜가 종료된 Thread에서 사진을 올리더라도
새 Verification으로 인정하지 않는다.


## Error Handling

특정 Thread 삭제, Discord permission 오류 등의 문제가 있어도
Scheduler 전체가 종료되지 않도록 한다.


## 테스트

- 미인증자만 Reminder
- 전원 인증 시 Reminder 없음
- Reminder 중복 방지
- Restart 후 중복 방지
- Thread lock
- Thread archive


---

# Step 10 — Monthly Leaderboard

`SPEC.md`를 기준으로 월간 Leaderboard를 구현해줘.

명령:

/check leaderboard


## 입력

- Check
- 연도 / 월

연도와 월을 지정하지 않으면 현재 월을 사용한다.


## 계산

Leaderboard는 단순 인증 횟수가 아니라:

Completed / Scheduled

기준으로 계산한다.


예:

🏆 2026년 9월 — 영양제

1. User A — 58 / 60 (96.7%)
2. User B — 55 / 60 (91.7%)
3. User C — 49 / 60 (81.7%)


## Scheduled 계산

반드시 고려:

- 해당 월의 실제 날짜
- Active Weekdays
- Daily Sessions
- Participant joined_at
- Participant left_at 또는 participation history
- Check/Schedule history가 존재한다면 해당 기간


월 중간에 참여한 사용자의 가입 이전 일정은
분모에 포함하지 않는다.

월 중간에 탈퇴한 사용자의 탈퇴 이후 일정도
분모에 포함하지 않는다.


## 정렬

1. Completion Rate
2. Completed Count
3. 안정적인 tie-break


## 중요

과거 Leaderboard가 현재 Check 설정 변경 때문에
바뀌어서는 안 되는지 현재 데이터 모델을 검토한다.

현재 구조가 historical schedule 계산에 부족하다면
문제를 설명하고 최소한의 변경으로 보완한다.


## 아직 구현하지 말 것

- Streak
- Weekly Leaderboard
- 개인 통계


---

# Step 11 — Monthly Automatic Report

현재 Leaderboard 계산 로직을 재사용하여
지난달 결과를 자동 게시하는 기능을 구현해줘.

새 달이 시작된 이후
지난달 결과를 해당 Check Channel에 게시한다.


예:

🏆 2026년 9월 DoneYet? 결과

💊 영양제

1. User A — 58 / 60 (96.7%)
2. User B — 55 / 60 (91.7%)
3. User C — 49 / 60 (81.7%)

다음 달도 DoneYet?


## 요구사항

- Leaderboard 계산 로직 재사용
- timezone-aware
- 동일 Check + Month Report 최대 1회
- restart 후 중복 게시 방지
- 게시 실패가 다른 Scheduler 작업에 영향 주지 않음


실제 한 달을 기다리지 않고 테스트할 수 있도록
Report 생성 로직과 자동 실행 로직을 분리한다.


---

# Step 12 — `/check edit`

현재 DoneYet? 구현과 `SPEC.md`를 기준으로
Check 설정 수정 기능을 구현해줘.

명령:

/check edit


수정 가능:

- Name
- Channel
- Verification Mode
- Active Weekdays
- Session
  - 추가
  - 제거
  - Check Time 변경
  - Reminder Time 변경
- Enabled


## 매우 중요

과거 데이터는 보존한다.

다음 기록이 깨지면 안 된다.

- daily_checkins
- verifications
- 과거 leaderboard


이미 과거에 사용된 schedule row를
단순 DELETE 후 재생성해서 historical reference를 깨뜨리지 않는다.

현재 schema를 검토해서 필요하다면:

- active
- valid_from
- valid_until
- soft delete

등 최소한의 history 구조를 사용한다.


설정 변경은 가능한 한
미래 일정부터 적용되도록 설계한다.


## Discord UX

Check 선택
→ 수정할 항목 선택
→ 새 값 입력
→ 변경 내용 확인
→ Confirm


한 번에 모든 설정을 다시 입력하게 만들 필요는 없다.


---

# Step 13 — Restart / Recovery 강화

전체 코드를 검토하고 Restart Safety를 강화해줘.

확인:

- Check-in 중복
- Thread 중복
- Verification 중복
- Reminder 중복
- Monthly Report 중복
- Persistent Button
- Startup 시 놓친 일정


## 시나리오

09:00 Check-in 예정
08:50 Bot 종료
09:20 Bot 시작

이 상황에서 어떻게 복구할지
명확한 Recovery Policy를 정의한다.


권장:

- 당일의 최근 놓친 Check-in은 복구
- 이미 지나치게 오래된 Session은 무조건 생성하지 않음
- Reminder도 일관된 정책 적용
- DB Unique Constraint를 최종 방어선으로 사용


모든 scheduled operation을 가능한 한 idempotent하게 만든다.


다음 상황을 테스트한다.

1. Check Time 전 restart
2. Check Time 직후 restart
3. Reminder 전 restart
4. Reminder 후 restart
5. 자정 직전 restart
6. 자정 직후 restart


---

# Step 14 — Error Handling / Logging

Raspberry Pi에서 장기간 운영할 수 있도록
전체 Error Handling과 Logging을 정리해줘.


## Logging

Python `logging`을 사용한다.

로그 대상:

- Startup
- Discord Login
- DB Initialization
- Check-in 생성
- Verification
- Reminder
- Thread 생성/종료
- Monthly Report
- Command Error
- Discord API Error
- SQLite Error
- Scheduler Error


## Security

절대 로그에 출력하지 않는다.

- Discord Token
- Client Secret
- `.env` 내용


## 안정성

한 Check 또는 한 Thread에서 발생한 예외 때문에
전체 Scheduler가 종료되지 않도록 한다.

예외를 무조건 무시하지 말고
원인을 추적할 수 있는 로그를 남긴다.

개발/운영 로그 레벨을 쉽게 설정할 수 있도록 한다.


---

# Step 15 — Test Suite 정리

현재 DoneYet?의 핵심 Business Logic을 검토하고
Discord API 없이 테스트 가능한 부분의 unittest를 보강해줘.

현재 프로젝트가 `unittest`를 사용하고 있으므로
특별한 이유가 없다면 pytest로 전환하지 말고 기존 방식을 유지한다.


우선 테스트:

- Time Validation
- Weekday 판단
- Schedule 판단
- Participant 상태
- Verification 중복
- Check-in 중복
- Reminder 대상 계산
- Scheduled Count
- Leaderboard
- Restart Recovery
- Timezone
- Repository Transaction


Discord API를 과도하게 mock하기보다
Business Logic을 Discord Command/Event 코드에서 분리하여
테스트하는 것을 우선한다.

테스트를 위해 전체 Architecture를 갈아엎지 않는다.


---

# Step 16 — Raspberry Pi Deployment

현재 프로젝트를 Raspberry Pi OS Lite에서
24시간 self-hosting할 수 있도록 준비해줘.

환경:

Raspberry Pi
→ Raspberry Pi OS Lite
→ Python
→ SQLite
→ systemd


Docker는 사용하지 않는다.


## 문서화

다음을 포함한다.

1. Repository clone
2. Python venv 생성
3. requirements 설치
4. `.env` 생성
5. DB 초기화
6. Bot 수동 실행
7. systemd service 등록
8. Boot 자동 시작
9. Crash 자동 재시작
10. Status 확인
11. Logs 확인
12. Restart
13. Stop
14. Git pull을 이용한 업데이트


필요하면:

deploy/doneyet.service.example

을 추가한다.


실제 다음 값은 하드코딩하지 않는다.

- Linux username
- 실제 home path
- Bot Token


일반 Linux에서도 경로만 수정하여 사용할 수 있도록 한다.


---

# Step 17 — Final v1 Review

DoneYet? 전체 구현을 `SPEC.md` 기준으로 최종 검토해줘.

새 기능을 추가하는 단계가 아니다.


## Functional

확인:

- `/test`
- `/check create`
- `/check list`
- `/check info`
- `/check delete`
- `/check edit`
- participant add/remove
- Active Weekdays
- Multiple Daily Sessions
- Button Verification
- Photo Verification
- Either Verification
- Reminder
- Thread Lifecycle
- Leaderboard
- Monthly Report


## Data Integrity

확인:

- Foreign Keys
- Unique Constraints
- Transactions
- Participant History
- Schedule History
- Historical Leaderboard
- Restart Safety


## Discord

확인:

- 최소 권한
- 비참여자 처리
- Persistent Button
- Public Thread
- Ephemeral Response
- Guild Isolation


## Security

확인:

- Token hardcoding 없음
- Secret logging 없음
- `.env` Git 제외
- 개인 Guild/User ID hardcoding 없음


## Deployment

확인:

- Windows
- Raspberry Pi OS / Linux
- SQLite
- systemd


## Code Quality

확인:

- 중복 코드
- Dead Code
- 지나친 Abstraction
- 지나친 파일 분리
- Error Handling
- Type Hints
- README / SPEC와 실제 동작 일치


발견한 문제를:

- Critical
- Important
- Nice to Have

로 구분한다.

Critical / Important만 수정한다.

SPEC에 없는 신규 기능은 임의로 추가하지 않는다.

마지막으로:

1. DoneYet? v1이 실제 사용 가능한 상태인지
2. 알려진 제한사항
3. Raspberry Pi 배포 전에 사람이 직접 확인해야 할 항목

을 정리해줘.