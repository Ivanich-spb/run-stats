import os
import sqlite3
import sys
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
    if "," in value and "." in value:
        raise click.BadParameter("Некорректная дистанция. Используйте точку или запятую.")
    if value.count(",") > 1 or value.count(".") > 1:
        raise click.BadParameter("Некорректная дистанция. Пример: 5.2km или 800m.")
    if "," in value:
        value = value.replace(",", ".")
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
        distance_km = distance
    elif unit == "mi":
        distance_km = distance * KM_PER_MI
    elif unit == "m":
        distance_km = distance / 1000
    else:
        raise click.BadParameter("Неизвестная единица расстояния")

    if distance_km <= 0:
        raise click.BadParameter("Дистанция должна быть больше нуля")
    return distance_km


def parse_duration(raw: str) -> int:
    parts = raw.split(":")
    if len(parts) != 2:
        raise click.BadParameter("Ожидается формат ММ:СС")
    minutes = int(parts[0])
    seconds = int(parts[1])
    if minutes < 0 or seconds < 0:
        raise click.BadParameter("Длительность должна быть больше нуля")
    if seconds >= 60:
        raise click.BadParameter("Секунды должны быть меньше 60")
    total = minutes * 60 + seconds
    if total <= 0:
        raise click.BadParameter("Длительность должна быть больше нуля")
    return total


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


def get_style_settings() -> tuple[bool, bool]:
    ctx = click.get_current_context(silent=True)
    if ctx and isinstance(ctx.obj, dict):
        return bool(ctx.obj.get("style")), bool(ctx.obj.get("color"))
    return False, False


def with_emoji(text: str, emoji: str) -> str:
    style_enabled, _ = get_style_settings()
    if style_enabled:
        return f"{emoji} {text}"
    return text


def style_text(text: str, *, fg: str | None = None, bold: bool = False) -> str:
    _, color_enabled = get_style_settings()
    if color_enabled:
        return click.style(text, fg=fg, bold=bold)
    return text


def style_metric(text: str, *, fg: str = "green") -> str:
    return style_text(text, fg=fg, bold=True)


def render_table(headers: list[str], rows: list[list[str]], align_right: set[int]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def pad(value: str, width: int, right: bool) -> str:
        return value.rjust(width) if right else value.ljust(width)

    header_cells = [
        pad(header, widths[i], i in align_right) for i, header in enumerate(headers)
    ]
    header_line = style_text(" | ".join(header_cells), bold=True)

    lines = [header_line]
    for row in rows:
        cells = [pad(row[i], widths[i], i in align_right) for i in range(len(headers))]
        lines.append(" | ".join(cells))
    return "\n".join(lines)


@click.group()
@click.option("--no-style", is_flag=True, help="Отключить стили и эмодзи")
@click.option("--no-color", is_flag=True, help="Отключить цвет")
@click.pass_context
def cli(ctx, no_style: bool, no_color: bool):
    """Беговой дневник."""
    style_enabled = sys.stdout.isatty() and not no_style
    color_enabled = style_enabled and not no_color
    ctx.obj = {"style": style_enabled, "color": color_enabled}


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

    summary = f"Записано: {format_distance(distance_km, unit, trim_trailing_zero=True)} за {duration}"
    click.echo(with_emoji(summary, "✅"))
    if note:
        click.echo(with_emoji(f"Заметка: {note}", "📝"))


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
    count_text = style_metric(str(count), fg="cyan")
    distance_text = style_metric(format_distance(total_km, unit), fg="green")
    pace_text = style_metric(format_pace(avg_pace, unit), fg="yellow")
    label = with_emoji("На этой неделе:", "📅")
    click.echo(f"{label} {count_text} пробежки, {distance_text}, средний темп {pace_text}")


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
    count_text = style_metric(str(count), fg="cyan")
    distance_text = style_metric(format_distance(total_km, unit), fg="green")
    pace_text = style_metric(format_pace(avg_pace, unit), fg="yellow")
    label = with_emoji(f"За {month_name} {today.year}:", "🗓️")
    click.echo(f"{label} {count_text} пробежки, {distance_text}, средний темп {pace_text}")


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
    distance_text = style_metric(format_distance(target_km, unit, trim_trailing_zero=True))
    duration_text = style_metric(format_duration(duration_sec), fg="yellow")
    line = (
        f"Рекорд на {distance_text}: {duration_text} "
        f"(был {format_date(run_date)})"
    )
    click.echo(with_emoji(line, "🏆"))


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
    headers = ["Неделя", "Пробежки", header_unit, "Средний темп"]
    rows: list[list[str]] = []
    for start in sorted(grouped.keys()):
        count, total_km, total_seconds = summarize(grouped[start])
        avg_pace = total_seconds / total_km
        total_value = format_distance_value(total_km, unit)
        rows.append([start.isoformat(), str(count), total_value, format_pace(avg_pace, unit)])

    table = render_table(headers, rows, align_right={1, 2, 3})
    click.echo(table)


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

    title = with_emoji(f"Сравнение за {weeks} недели:", "⚖️")
    lines = [title]
    if last_count == 0:
        last_line = "Последние недели: нет пробежек, средний темп недоступен"
    else:
        last_pace = last_seconds / last_km
        last_line = (
            f"Последние {weeks} недели: {last_count} пробежки, "
            f"{format_distance(last_km, unit)}, средний темп {format_pace(last_pace, unit)}"
        )
        last_row = [
            f"Последние {weeks} недели",
            str(last_count),
            format_distance_value(last_km, unit),
            format_pace(last_pace, unit),
        ]

    if prev_count == 0:
        prev_line = "Предыдущие недели: нет пробежек, средний темп недоступен"
    else:
        prev_pace = prev_seconds / prev_km
        prev_line = (
            f"Предыдущие {weeks} недели: {prev_count} пробежки, "
            f"{format_distance(prev_km, unit)}, средний темп {format_pace(prev_pace, unit)}"
        )
        prev_row = [
            f"Предыдущие {weeks} недели",
            str(prev_count),
            format_distance_value(prev_km, unit),
            format_pace(prev_pace, unit),
        ]

    if last_count > 0 and prev_count > 0:
        headers = ["Период", "Пробежки", "Км" if unit == "km" else "Ми", "Средний темп"]
        table = render_table(headers, [last_row, prev_row], align_right={1, 2, 3})
        lines.append(table)
    else:
        lines.append(last_line)
        lines.append(prev_line)

    diff = last_km - prev_km
    sign = "+" if diff >= 0 else "-"
    diff_value = format_distance_value(abs(diff), unit)
    unit_suffix = "ми" if unit == "mi" else "км"
    lines.append(f"Разница по километражу: {sign}{diff_value}{unit_suffix}")
    click.echo("\n".join(lines))
