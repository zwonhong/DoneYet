"""Discord-independent Check data models."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class VerificationMode(str, Enum):
    BUTTON = "button"
    PHOTO = "photo"
    EITHER = "either"


@dataclass(frozen=True)
class ScheduleInput:
    check_time: str
    reminder_time: str


@dataclass(frozen=True)
class CheckInput:
    guild_id: int
    channel_id: int
    name: str
    verification_mode: VerificationMode
    member_ids: tuple[int, ...]
    weekdays: tuple[int, ...]
    schedules: tuple[ScheduleInput, ...]
    timezone: str = "Asia/Seoul"
    enabled: bool = True


@dataclass(frozen=True)
class CheckSchedule:
    id: int
    sequence: int
    check_time: str
    reminder_time: str


@dataclass(frozen=True)
class CheckMember:
    user_id: int
    joined_at: datetime


@dataclass(frozen=True)
class Check:
    id: int
    guild_id: int
    channel_id: int
    name: str
    verification_mode: VerificationMode
    timezone: str
    enabled: bool
    created_at: datetime
    weekdays: tuple[int, ...]
    members: tuple[CheckMember, ...]
    schedules: tuple[CheckSchedule, ...]

    @property
    def daily_sessions(self) -> int:
        return len(self.schedules)
