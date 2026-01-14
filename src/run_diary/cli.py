import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import click

KM_PER_MI = 1.60934

MONTH_NAMES = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}


@dataclass
class Run:
    run_date: date
    distance_km: float
    duration_sec: int
    note: str | None


def get_today() -> date:
    override = os.getenv("RUN_TODAY")
    if override:
        return datetime.strptime(override, "%Y-%m-%d").date()
    return date.today()


def get_db_path() -> str:
    return os.getenv("RUN_DB", "runs.db")


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            distance_km REAL NOT NULL,
            duration_sec INTEGER NOT NULL,
            note TEXT
        )
        """
    )
    return conn


def get_distance_unit() -> str:
    raw = os.getenv("RUN_UNIT", "km").strip().lower()
    if raw in {"km", "mi"}:
        return raw
    raise click.ClickException("Неизвестная единица расстояния. Используйте km или mi.")


def convert_km_to_unit(distance_km: float, unit: str) -> float:
    if unit == "mi":
        return distance_km / KM_PER_MI
    return distance_km


def parse_distance(raw: str, default_unit: str) -> float:
    value = raw.strip().lower()
    unit = default_unit
    if value.endswith("km"):
        value = value[:-2]
        unit = "km"
    elif value.endswith("mi"):
        value = value[:-2]
        unit = "mi"
    elif value.endswith("m"):
        value = value[:-1]
        unit = "m"

    distance = float(value)
    if unit == "km":
        return distance
    if unit == "mi":
        return distance * KM_PER_MI
    if unit == "m":
        return distance / 1000
    raise click.BadParameter("Неизвестная единица расстояния")


def parse_duration(raw: str) -> int:
    parts = raw.split(":")
    if len(parts) != 2:
        raise click.BadParameter("Ожидается формат ММ:СС")
    minutes = int(parts[0])
    seconds = int(parts[1])
    if seconds >= 60:
        raise click.BadParameter("Секунды должны быть меньше 60")
    return minutes * 60 + seconds


def format_distance_value(distance_km: float, unit: str) -> str:
    return f"{convert_km_to_unit(distance_km, unit):.1f}"


def format_distance(distance_km: float, unit: str, *, trim_trailing_zero: bool = False) -> str:
    formatted = format_distance_value(distance_km, unit)
    if trim_trailing_zero and formatted.endswith(".0"):
        formatted = formatted[:-2]
    suffix = "ми" if unit == "mi" else "км"
    return f"{formatted}{suffix}"


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def format_pace(seconds_per_km: float, unit: str) -> str:
    pace_seconds = seconds_per_km * KM_PER_MI if unit == "mi" else seconds_per_km
    rounded = int(round(pace_seconds))
    minutes = rounded // 60
    seconds = rounded % 60
    suffix = "ми" if unit == "mi" else "км"
    return f"{minutes}:{seconds:02d}/{suffix}"


def format_duration(total_seconds: int) -> str:
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def week_end(value: date) -> date:
    return week_start(value) + timedelta(days=6)


def fetch_runs(conn: sqlite3.Connection, start: date, end: date) -> list[Run]:
    cursor = conn.execute(
        """
        SELECT run_date, distance_km, duration_sec, note
        FROM runs
        WHERE run_date BETWEEN ? AND ?
        ORDER BY run_date ASC, id ASC
        """,
        (start.isoformat(), end.isoformat()),
    )
    rows = cursor.fetchall()
    runs = []
    for run_date, distance_km, duration_sec, note in rows:
        runs.append(
            Run(
                run_date=datetime.strptime(run_date, "%Y-%m-%d").date(),
                distance_km=distance_km,
                duration_sec=duration_sec,
                note=note,
            )
        )
    return runs


def summarize(runs: list[Run]):
    count = len(runs)
    total_km = sum(run.distance_km for run in runs)
    total_seconds = sum(run.duration_sec for run in runs)
    return count, total_km, total_seconds


@click.group()
def cli():
    """Беговой дневник."""


@cli.command("add")
@click.argument("distance")
@click.argument("duration")
@click.option("--note", help="Короткая заметка о пробежке")
def add_run(distance: str, duration: str, note: str | None):
    run_date = get_today()
    unit = get_distance_unit()
    distance_km = parse_distance(distance, unit)
    duration_sec = parse_duration(duration)

    conn = connect_db()
    conn.execute(
        "INSERT INTO runs (run_date, distance_km, duration_sec, note) VALUES (?, ?, ?, ?)",
        (run_date.isoformat(), distance_km, duration_sec, note),
    )
    conn.commit()
    conn.close()

    click.echo(
        f"Записано: {format_distance(distance_km, unit, trim_trailing_zero=True)} за {duration}"
    )
    if note:
        click.echo(f"Заметка: {note}")


@cli.command("week")
def week_summary():
    today = get_today()
    start = week_start(today)
    end = week_end(today)
    unit = get_distance_unit()

    conn = connect_db()
    runs = fetch_runs(conn, start, end)
    conn.close()

    count, total_km, total_seconds = summarize(runs)
    if count == 0:
        click.echo("На этой неделе нет пробежек")
        return

    avg_pace = total_seconds / total_km
    click.echo(
        "На этой неделе: "
        f"{count} пробежки, {format_distance(total_km, unit)}, "
        f"средний темп {format_pace(avg_pace, unit)}"
    )


@cli.command("month")
def month_summary():
    today = get_today()
    start = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    end = next_month - timedelta(days=1)
    unit = get_distance_unit()

    conn = connect_db()
    runs = fetch_runs(conn, start, end)
    conn.close()

    count, total_km, total_seconds = summarize(runs)
    month_name = MONTH_NAMES[today.month]
    if count == 0:
        click.echo(f"За {month_name} {today.year}: нет пробежек")
        return

    avg_pace = total_seconds / total_km
    click.echo(
        f"За {month_name} {today.year}: "
        f"{count} пробежки, {format_distance(total_km, unit)}, "
        f"средний темп {format_pace(avg_pace, unit)}"
    )


@cli.command("best")
@click.argument("distance")
def best_time(distance: str):
    unit = get_distance_unit()
    target_km = parse_distance(distance, unit)
    conn = connect_db()
    cursor = conn.execute(
        """
        SELECT run_date, duration_sec
        FROM runs
        WHERE ABS(distance_km - ?) < 0.0001
        ORDER BY duration_sec ASC, run_date ASC
        LIMIT 1
        """,
        (target_km,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        click.echo(f"Нет пробежек на {format_distance(target_km, unit, trim_trailing_zero=True)}")
        return

    run_date = datetime.strptime(row[0], "%Y-%m-%d").date()
    duration_sec = row[1]
    click.echo(
        f"Рекорд на {format_distance(target_km, unit, trim_trailing_zero=True)}: "
        f"{format_duration(duration_sec)} "
        f"(был {format_date(run_date)})"
    )


@cli.command("progress")
def progress():
    conn = connect_db()
    cursor = conn.execute(
        "SELECT run_date, distance_km, duration_sec, note FROM runs ORDER BY run_date ASC, id ASC"
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        click.echo("Нет пробежек для прогресса")
        return

    grouped: dict[date, list[Run]] = {}
    for run_date, distance_km, duration_sec, note in rows:
        run_day = datetime.strptime(run_date, "%Y-%m-%d").date()
        start = week_start(run_day)
        grouped.setdefault(start, []).append(
            Run(run_date=run_day, distance_km=distance_km, duration_sec=duration_sec, note=note)
        )

    unit = get_distance_unit()
    header_unit = "Ми" if unit == "mi" else "Км"
    lines = [f"Неделя | Пробежки | {header_unit} | Средний темп"]
    for start in sorted(grouped.keys()):
        count, total_km, total_seconds = summarize(grouped[start])
        avg_pace = total_seconds / total_km
        total_value = format_distance_value(total_km, unit)
        lines.append(
            f"{start.isoformat()} | {count} | {total_value} | {format_pace(avg_pace, unit)}"
        )

    click.echo("\n".join(lines))


@cli.command("compare")
@click.option("--weeks", default=4, show_default=True, type=int)
def compare_weeks(weeks: int):
    if weeks <= 0:
        raise click.BadParameter("Число недель должно быть больше нуля")

    today = get_today()
    current_start = week_start(today)
    last_start = current_start - timedelta(days=(weeks - 1) * 7)
    last_end = week_end(today)

    previous_end = last_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=weeks * 7 - 1)

    conn = connect_db()
    last_runs = fetch_runs(conn, last_start, last_end)
    previous_runs = fetch_runs(conn, previous_start, previous_end)
    conn.close()

    unit = get_distance_unit()
    last_count, last_km, last_seconds = summarize(last_runs)
    prev_count, prev_km, prev_seconds = summarize(previous_runs)

    lines = [f"Сравнение за {weeks} недели:"]
    if last_count == 0:
        lines.append("Последние недели: нет пробежек")
    else:
        last_pace = last_seconds / last_km
        lines.append(
            f"Последние {weeks} недели: {last_count} пробежки, {format_distance(last_km, unit)}, "
            f"средний темп {format_pace(last_pace, unit)}"
        )

    if prev_count == 0:
        lines.append("Предыдущие недели: нет пробежек")
    else:
        prev_pace = prev_seconds / prev_km
        lines.append(
            f"Предыдущие {weeks} недели: {prev_count} пробежки, {format_distance(prev_km, unit)}, "
            f"средний темп {format_pace(prev_pace, unit)}"
        )

    diff = last_km - prev_km
    sign = "+" if diff >= 0 else "-"
    diff_value = format_distance_value(abs(diff), unit)
    unit_suffix = "ми" if unit == "mi" else "км"
    lines.append(f"Разница по километражу: {sign}{diff_value}{unit_suffix}")
    click.echo("\n".join(lines))
