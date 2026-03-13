from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable
from uuid import uuid4


STATUS_UNKNOWN = "Non renseigne"
STATUS_AVAILABLE = "Disponible"
STATUS_MAYBE = "Peut-etre"
STATUS_UNAVAILABLE = "Indisponible"
STATUS_OPTIONS = [
    STATUS_UNKNOWN,
    STATUS_AVAILABLE,
    STATUS_MAYBE,
    STATUS_UNAVAILABLE,
]

DEFAULT_TITLE = "Agenda equipe"
DEFAULT_TIMEZONE = "Europe/Paris"
DEFAULT_DAYS = 14
DEFAULT_START_HOUR = 8
DEFAULT_END_HOUR = 18
SLOT_DURATION_HOURS = 2
DEFAULT_PARTICIPANTS = [
    "Personne 1",
    "Personne 2",
    "Personne 3",
    "Personne 4",
]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "availability" / "planner.sqlite3"


@dataclass(frozen=True)
class Schedule:
    schedule_id: str
    title: str
    timezone: str
    start_date: date
    days: int
    start_hour: int
    end_hour: int
    participants: list[str]
    created_at: datetime


@dataclass(frozen=True)
class AvailabilityEntry:
    schedule_id: str
    participant_name: str
    slot_start: datetime
    status: str
    updated_at: datetime


def ensure_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schedules (
                schedule_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                timezone TEXT NOT NULL,
                start_date TEXT NOT NULL,
                days INTEGER NOT NULL,
                start_hour INTEGER NOT NULL,
                end_hour INTEGER NOT NULL,
                participants_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS availability (
                schedule_id TEXT NOT NULL,
                participant_name TEXT NOT NULL,
                slot_start TEXT NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (schedule_id, participant_name, slot_start),
                FOREIGN KEY (schedule_id) REFERENCES schedules (schedule_id) ON DELETE CASCADE
            )
            """
        )


def normalize_participants(participants: Iterable[str]) -> list[str]:
    cleaned = [participant.strip() for participant in participants if participant.strip()]
    if len(cleaned) != 4:
        raise ValueError("Exactly four participant names are required.")

    if len(set(cleaned)) != 4:
        raise ValueError("Participant names must be unique.")

    return cleaned


def generate_schedule_dates(start_date: date, days: int) -> list[date]:
    if days <= 0:
        raise ValueError("days must be greater than zero.")

    schedule_dates: list[date] = []
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        if current_date.weekday() < 5:
            schedule_dates.append(current_date)
    return schedule_dates


def generate_slot_starts(start_date: date, days: int, start_hour: int, end_hour: int) -> list[datetime]:
    if start_hour < 0 or end_hour > 22 or end_hour < start_hour:
        raise ValueError("Invalid hour range.")

    slot_starts: list[datetime] = []
    for current_date in generate_schedule_dates(start_date, days):
        for hour in range(start_hour, end_hour + 1, SLOT_DURATION_HOURS):
            slot_starts.append(datetime.combine(current_date, time(hour=hour)))
    return slot_starts


def create_schedule(
    title: str,
    participants: Iterable[str],
    timezone: str = DEFAULT_TIMEZONE,
    start_date: date | None = None,
    days: int = DEFAULT_DAYS,
    start_hour: int = DEFAULT_START_HOUR,
    end_hour: int = DEFAULT_END_HOUR,
) -> str:
    ensure_database()

    effective_start_date = start_date or date.today()
    participant_list = normalize_participants(participants)
    slot_starts = generate_slot_starts(effective_start_date, days, start_hour, end_hour)
    schedule_id = uuid4().hex[:12]
    created_at = datetime.utcnow().replace(microsecond=0)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            INSERT INTO schedules (
                schedule_id,
                title,
                timezone,
                start_date,
                days,
                start_hour,
                end_hour,
                participants_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule_id,
                title.strip() or DEFAULT_TITLE,
                timezone.strip() or DEFAULT_TIMEZONE,
                effective_start_date.isoformat(),
                days,
                start_hour,
                end_hour,
                json.dumps(participant_list),
                created_at.isoformat(),
            ),
        )
        rows = [
            (
                schedule_id,
                participant,
                slot_start.isoformat(),
                STATUS_UNKNOWN,
                created_at.isoformat(),
            )
            for participant in participant_list
            for slot_start in slot_starts
        ]
        connection.executemany(
            """
            INSERT INTO availability (
                schedule_id,
                participant_name,
                slot_start,
                status,
                updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

    return schedule_id


def get_schedule(schedule_id: str) -> Schedule | None:
    ensure_database()

    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute(
            """
            SELECT
                schedule_id,
                title,
                timezone,
                start_date,
                days,
                start_hour,
                end_hour,
                participants_json,
                created_at
            FROM schedules
            WHERE schedule_id = ?
            """,
            (schedule_id,),
        ).fetchone()

    if row is None:
        return None

    return Schedule(
        schedule_id=row[0],
        title=row[1],
        timezone=row[2],
        start_date=date.fromisoformat(row[3]),
        days=row[4],
        start_hour=row[5],
        end_hour=row[6],
        participants=json.loads(row[7]),
        created_at=datetime.fromisoformat(row[8]),
    )


def get_availability_entries(schedule_id: str) -> list[AvailabilityEntry]:
    ensure_database()

    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute(
            """
            SELECT
                schedule_id,
                participant_name,
                slot_start,
                status,
                updated_at
            FROM availability
            WHERE schedule_id = ?
            ORDER BY slot_start, participant_name
            """,
            (schedule_id,),
        ).fetchall()

    return [
        AvailabilityEntry(
            schedule_id=row[0],
            participant_name=row[1],
            slot_start=datetime.fromisoformat(row[2]),
            status=row[3],
            updated_at=datetime.fromisoformat(row[4]),
        )
        for row in rows
    ]


def save_participant_entries(
    schedule: Schedule,
    participant_name: str,
    slot_statuses: dict[datetime, str],
) -> None:
    ensure_database()

    if participant_name not in schedule.participants:
        raise ValueError("Unknown participant.")

    allowed_slots = set(generate_slot_starts(schedule.start_date, schedule.days, schedule.start_hour, schedule.end_hour))
    if set(slot_statuses) != allowed_slots:
        raise ValueError("The provided slots do not match the schedule configuration.")

    invalid_statuses = {status for status in slot_statuses.values() if status not in STATUS_OPTIONS}
    if invalid_statuses:
        raise ValueError("Unsupported availability status provided.")

    updated_at = datetime.utcnow().replace(microsecond=0).isoformat()
    rows = [
        (
            schedule.schedule_id,
            participant_name,
            slot_start.isoformat(),
            slot_statuses[slot_start],
            updated_at,
        )
        for slot_start in sorted(slot_statuses)
    ]

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executemany(
            """
            INSERT INTO availability (
                schedule_id,
                participant_name,
                slot_start,
                status,
                updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(schedule_id, participant_name, slot_start)
            DO UPDATE SET
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            rows,
        )
