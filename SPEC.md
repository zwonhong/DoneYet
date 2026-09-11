# DoneYet? — Functional Specification

> A self-hosted recurring check-in bot for Discord.

## 1. Overview

DoneYet?은 Discord 서버에서 반복적인 활동을 체크하고 기록하는
self-hosted check-in bot이다.

특정 활동에 종속되지 않으며, 하나의 Discord 서버에서
여러 개의 Check를 독립적으로 운영할 수 있다.

예:

- 영양제 복용
- 운동
- 공부
- 독서
- 물 마시기
- 과제 수행
- 기타 반복 활동

각 Check는 서로 다른 설정을 가질 수 있다.

- Discord 채널
- 참여자
- 인증 방식
- 체크하는 요일
- 하루 체크 횟수
- 각 회차의 체크 시간
- 각 회차의 리마인드 시간

예:

영양제
- 매일
- 하루 1회
- 09:00 체크
- 22:00 리마인드

운동
- 월 / 수 / 금
- 하루 1회
- 20:00 체크
- 23:00 리마인드

공부
- 평일
- 하루 2회
- 09:00 / 21:00 체크


---

# 2. Core Concept

DoneYet?의 기본 관리 단위는 `Check`이다.

하나의 Check는 하나의 반복 활동을 의미한다.

예:

Check: 영양제

- Channel: #영양제
- Members: User A, User B, User C
- Verification Mode: Button
- Active Days: Every Day
- Daily Sessions: 1
- Session 1:
  - Check Time: 09:00
  - Reminder Time: 22:00

Check: 공부

- Channel: #공부
- Members: User A, User D
- Verification Mode: Either
- Active Days: Monday ~ Friday
- Daily Sessions: 2
- Session 1:
  - Check Time: 09:00
  - Reminder Time: 12:00
- Session 2:
  - Check Time: 21:00
  - Reminder Time: 23:30


---

# 3. Channel and Check Relationship

기본적으로 하나의 Check는 하나의 Discord 채널에 연결된다.

예:

#영양제
→ 영양제 Check

#운동
→ 운동 Check

#공부
→ 공부 Check

Discord 채널의 공개 여부와 DoneYet?의 Check 참여 여부는 서로 별개이다.

예:

#영양제 채널
- 서버 전체 공개
- 실제 Check 참여자:
  - User A
  - User B
  - User C

다른 서버 멤버도 채널을 볼 수 있지만,
Check 기록 및 리더보드에는 포함되지 않는다.


---

# 4. Check Creation

Check는 Discord Slash Command를 통해 생성한다.

기본 명령어:

/check create

Check 생성 시 다음 정보를 설정한다.

Required:

- Check 이름
- 사용할 Discord 채널
- 참여자
- 인증 방식
- 체크하는 요일
- 하루 체크 횟수
- 각 회차의 체크 시간
- 각 회차의 리마인드 시간


예:

/check create

Name:
영양제

Channel:
#영양제

Members:
@UserA @UserB @UserC

Verification:
Button

Active Days:
Every Day

Daily Sessions:
1

Session 1:
- Check Time: 09:00
- Reminder Time: 22:00


---

# 5. Participants

각 Check는 독립적인 참여자 목록을 가진다.

참여자는 Discord User ID를 기준으로 저장한다.

예:

영양제 Check
- User A
- User B
- User C

운동 Check
- User A
- User D

같은 사용자가 여러 Check에 동시에 참여할 수 있다.


## Participant Management

Check 생성 이후에도 참여자를 추가하거나 제거할 수 있어야 한다.

예상 명령어:

/check member add
/check member remove


v1에서는 개별 사용자 지정 방식을 사용한다.

향후 다음 기능을 검토할 수 있다.

- Discord Role 기반 참여
- Self Join
- Self Leave
- 참여자별 개별 일정

참여자별 일정 기능은 v1 범위에 포함하지 않는다.


---

# 6. Schedule Model

각 Check는 공통 스케줄을 가진다.

해당 Check의 모든 참여자는 동일한 스케줄을 공유한다.

스케줄은 다음 요소로 구성된다.

- Active Days
- Daily Sessions
- Session별 Check Time
- Session별 Reminder Time


## Active Days

사용자는 Check가 실행될 요일을 선택할 수 있다.

예:

Every Day

Monday ~ Friday

Monday / Wednesday / Friday

Saturday / Sunday


요일은 내부적으로 개별 weekday 값 또는 bitmask 형태로 저장할 수 있다.


## Daily Sessions

하루에 Check가 몇 번 발생하는지 설정할 수 있다.

예:

1회

2회

3회


각 회차는 독립적인 Check-in으로 취급한다.

예:

영양제
Daily Sessions = 2

Session 1
09:00

Session 2
21:00


이 경우 같은 날짜라도 2개의 인증이 필요하다.


---

# 7. Verification Modes

각 Check는 생성 시 인증 방식을 선택한다.

지원 방식:

1. Button
2. Photo
3. Either


---

# 8. Button Verification

Button 방식에서는 Daily Check-in 메시지에
인증 버튼을 표시한다.

예:

💊 영양제 — 1/2

오늘 1회차 영양제를 드셨나요?

[ ✅ 완료 ]


참여자가 버튼을 누르면
해당 날짜, 해당 회차의 인증을 완료한다.

같은 회차에서 여러 번 버튼을 눌러도
인증 기록은 1회만 저장한다.


---

# 9. Photo Verification

Photo 방식에서는 Daily Check-in 메시지가 생성될 때
해당 날짜와 회차의 인증용 Public Thread를 생성한다.

예:

🏃 운동 — 2026-09-11

└─ 🧵 2026-09-11 · 1회차 인증
    ├─ User A: [image]
    └─ User B: [image]


참여자가 해당 Thread에 이미지 파일을 업로드하면
해당 회차 인증을 완료한다.

이미지가 없는 일반 텍스트 메시지는 인증으로 처리하지 않는다.


---

# 10. Either Verification

Either 방식에서는 Button과 Photo 인증을 모두 제공한다.

사용자는 둘 중 하나로 인증할 수 있다.

같은 날짜와 같은 회차에서:

- 버튼 인증
- 사진 인증

둘 다 수행하더라도 인증 기록은 1회만 저장한다.


---

# 11. Daily Check-in Generation

각 Check는 Active Days에 해당하는 날짜에만 실행된다.

각 Session의 `check_time`이 되면
DoneYet?이 해당 Check의 채널에 Daily Check-in 메시지를 보낸다.

예:

## 💊 영양제 — 1/2

오늘 1회차 영양제 드셨나요?

참여자:
@UserA @UserB @UserC

[ ✅ 완료 ]


2회차:

## 💊 영양제 — 2/2

오늘 2회차 영양제 드셨나요?

참여자:
@UserA @UserB @UserC

[ ✅ 완료 ]


하루 2회 Check라면 각각 별도의 Check-in 메시지가 생성된다.


---

# 12. Daily Verification Thread

Photo 또는 Either 인증 방식에서만 생성한다.

Thread 이름 예:

2026-09-11 · 1회차 인증

2026-09-11 · 2회차 인증


Thread type:

Public Thread


Public Thread는 서버 전체 공개를 의미하지 않는다.

부모 채널이 비공개라면
그 채널에 접근 가능한 사용자만 Thread에 접근할 수 있다.


---

# 13. Thread Lifecycle

각 인증 Thread는 해당 회차의 인증 공간이다.

예:

2026-09-11 · 1회차 인증
→ Open


날짜가 종료되면:

→ Locked
→ Archived


지난 날짜의 Thread에는
새로운 인증을 제출할 수 없다.


Thread는 사용자에게 보여주는 인증 공간일 뿐이며,
실제 인증 기록의 Source of Truth는 SQLite Database이다.


---

# 14. Reminder

각 Session에는 `reminder_time`이 존재한다.

Reminder 시간이 되면
DoneYet?은 해당 날짜와 해당 Session의 인증 기록을 조회한다.

인증하지 않은 참여자만 추출하여 멘션한다.

예:

🔔 아직 1회차 체크를 완료하지 않았어요.

@UserB @UserC


이미 해당 회차를 인증한 사용자는 제외한다.

모든 참여자가 인증했다면 Reminder를 보내지 않는다.


---

# 15. Verification Rules

인증은 다음 단위로 구분한다.

- Check
- Date
- Session
- User


한 사용자는 하나의 Session에 대해
최대 1개의 인증 기록만 가진다.

Unique Constraint:

check_id + schedule_id + user_id + date


예:

영양제
2026-09-11

Session 1
User A → Complete

Session 2
User A → Complete


이 경우 하루 총 2회 완료이다.


---

# 16. Schedule Sessions

각 Check의 하루 회차는 별도 Schedule로 관리한다.

예:

영양제

Schedule 1
- Sequence: 1
- Check Time: 09:00
- Reminder Time: 12:00

Schedule 2
- Sequence: 2
- Check Time: 21:00
- Reminder Time: 23:00


이 구조를 사용함으로써
하루 1회 / 2회 / 3회 등의 Check를 동일한 방식으로 처리한다.


---

# 17. Leaderboard

DoneYet?은 Check별 월간 인증 기록을 집계한다.

예상 명령어:

/check leaderboard


단순 인증 일수보다
예정된 인증 횟수 대비 실제 완료 횟수를 기준으로 집계한다.

예:

🏆 2026년 9월 — 영양제

1. User A — 58 / 60 (96.7%)
2. User B — 55 / 60 (91.7%)
3. User C — 49 / 60 (81.7%)


Active Days와 Daily Sessions를 기반으로
해당 월의 전체 예정 횟수를 계산한다.


---

# 18. Monthly Automatic Report

매월 마지막 날 또는 다음 달 첫날
지난달 Check 결과를 자동 게시할 수 있도록 설계한다.

예:

🏆 2026년 9월 DoneYet? 결과

💊 영양제

1. User A — 58 / 60
2. User B — 55 / 60
3. User C — 49 / 60

다음 달도 DoneYet?


자동 게시 시점은 추후 설정 가능하도록 설계한다.


---

# 19. Database

v1에서는 SQLite를 사용한다.

외부 Database Server는 사용하지 않는다.


## checks

Check 기본 설정 저장.

Fields:

- id
- guild_id
- channel_id
- name
- verification_mode
- timezone
- enabled
- created_at


## check_days

Check가 실행되는 요일 저장.

Fields:

- check_id
- weekday


예:

0 = Monday
1 = Tuesday
2 = Wednesday
3 = Thursday
4 = Friday
5 = Saturday
6 = Sunday


또는 weekday bitmask를 사용할 수 있다.


## check_schedules

하루 Check Session 저장.

Fields:

- id
- check_id
- sequence
- check_time
- reminder_time


예:

영양제

id 1
sequence 1
09:00
12:00

id 2
sequence 2
21:00
23:00


## check_members

Check 참여자 저장.

Fields:

- check_id
- user_id
- joined_at


## daily_checkins

생성된 Daily Check-in 메시지 저장.

Fields:

- id
- check_id
- schedule_id
- date
- message_id
- thread_id
- created_at
- closed_at


Unique Constraint:

check_id + schedule_id + date


## verifications

사용자 인증 기록 저장.

Fields:

- id
- check_id
- schedule_id
- user_id
- date
- verification_method
- verified_at


Unique Constraint:

check_id + schedule_id + user_id + date


---

# 20. Timezone

시간 계산은 시스템 로컬 시간에 직접 의존하지 않는다.

Guild 또는 Check 단위 timezone을 사용한다.

기본값:

Asia/Seoul


timezone-aware datetime을 사용하여
다른 지역에서도 정상 동작하도록 설계한다.


---

# 21. Persistence

DoneYet?은 장기간 실행되는 self-hosted bot이다.

봇이 재시작되어도 다음 정보는 유지되어야 한다.

- Check 설정
- Active Days
- Schedule
- 참여자
- Check-in 기록
- 인증 기록
- Leaderboard 데이터


SQLite Database를 Source of Truth로 사용한다.


---

# 22. Restart Safety

봇 재시작으로 인해 다음 작업이 중복 실행되어서는 안 된다.

- Daily Check-in 생성
- Verification Thread 생성
- Reminder 전송
- Verification 생성


예:

09:00
Session 1 Check-in 생성

09:30
Raspberry Pi 재부팅

09:31
DoneYet? 재실행

→ 09:00 Session 1 Check-in을 다시 생성하지 않는다.


Database 상태를 확인하고 이어서 실행한다.


---

# 23. Discord Permissions

DoneYet?은 Administrator 권한을 요구하지 않는다.

Required Bot Permissions:

- View Channels
- Send Messages
- Create Public Threads
- Send Messages in Threads
- Manage Threads
- Embed Links
- Read Message History
- Use Application Commands


Not Required:

- Administrator
- Manage Server
- Manage Roles
- Manage Members
- Manage Messages
- Mention Everyone
- Create Private Threads


Gateway Intents:

- Presence Intent: OFF
- Server Members Intent: ON
- Message Content Intent: ON


---

# 24. Self-hosting

DoneYet?은 중앙 서버에서 제공하는 hosted bot이 아니다.

GitHub Repository에는 Source Code만 배포한다.

각 사용자는 자신의:

- Discord Application
- Discord Bot
- Bot Token
- Discord Server
- Hosting Environment

를 사용하여 직접 실행한다.


지원 대상:

- Windows
- Linux
- Raspberry Pi OS


---

# 25. Environment Variables

실제 비밀 정보는 `.env`에서 관리한다.

Example:

DISCORD_TOKEN=your_bot_token_here


`.env`는 Git Repository에 포함하지 않는다.

Repository에는 `.env.example`만 포함한다.


---

# 26. Security

다음 값은 Source Code에 하드코딩하지 않는다.

- Discord Bot Token
- Client Secret
- 개인 Server ID
- 개인 User ID


Bot Token은 `.env`로만 제공한다.

DoneYet?은 최소 권한 원칙을 따른다.


---

# 27. v1 Commands

초기 명령어 구조:

/test

/check create
/check list
/check info
/check edit
/check delete

/check member add
/check member remove

/check leaderboard


구체적인 Discord UI는 구현 과정에서
Modal, Select Menu, User Select 등을 활용하여 조정할 수 있다.


---

# 28. v1 Development Order

1. Discord 연결 및 `/test`
2. SQLite 초기화
3. Check 데이터 모델
4. Active Days 설정
5. Multi-session Schedule
6. Check 생성 / 조회 / 삭제
7. 참여자 관리
8. Button Verification
9. Daily Scheduler
10. Photo Verification
11. Verification Thread 생성
12. Thread Lock / Archive
13. Reminder
14. Monthly Leaderboard
15. Monthly Automatic Report
16. Restart Safety
17. Error Handling
18. Raspberry Pi Deployment


---

# 29. Non-goals for v1

v1에서는 다음 기능을 구현하지 않는다.

- 참여자별 개별 일정
- Web Dashboard
- Mobile App
- Cloud Database
- Central DoneYet? Server
- AI Image Verification
- Image Contents Analysis
- Cross-server Shared Leaderboard
- Paid Hosting
- Discord Account Authentication Website


사진 인증은 이미지가 업로드되었다는 사실만 확인한다.

이미지의 실제 내용을 AI로 분석하지 않는다.


---

# 30. Future Considerations

향후 필요성을 검토할 기능:

- 참여자별 개별 일정
- Discord Role 기반 참여
- Self Join / Self Leave
- 특정 날짜 예외 처리
- 휴일 제외
- Streak 계산
- 주간 리더보드
- 사용자별 통계
- Check별 커스텀 메시지
- Check별 커스텀 이모지
- Timezone별 사용자 일정
- Web Dashboard


참여자별 개별 일정은
v1 이후 실제 사용성을 보고 추가 여부를 결정한다.


---

# 31. Deployment Target

개발 환경:

Windows + VS Code


최종 운영 환경:

Raspberry Pi
→ Raspberry Pi OS Lite
→ Python
→ DoneYet? process
→ SQLite


최종적으로 Raspberry Pi 부팅 시
DoneYet?이 자동 실행되어야 한다.

프로세스가 비정상 종료될 경우
자동 재시작할 수 있도록 구성한다.

운영은 systemd 기반으로 설정한다.


---

# 32. Project Principles

DoneYet?은 다음 원칙을 따른다.

1. Self-hosted first
2. Minimal Discord permissions
3. No hardcoded personal configuration
4. Multiple independent Checks per server
5. Each Check has its own schedule
6. Channel visibility and Check participation are separate
7. All participants in a Check share the same schedule in v1
8. Support configurable active weekdays
9. Support configurable daily session count
10. Support independent time and reminder per session
11. SQLite is the Source of Truth
12. Restart-safe scheduling
13. Simple Discord-native UX