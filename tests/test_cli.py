import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest_bdd import given, parsers, scenarios, then, when

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from run_diary.cli import cli


scenarios("../features")


@dataclass
class CliContext:
    db_path: str
    today: str | None = None
    last_output: str = ""
    last_exit_code: int = 0


@pytest.fixture
def cli_context(tmp_path):
    return CliContext(db_path=str(tmp_path / "runs.db"))


def run_command(context: CliContext, command: str):
    args = shlex.split(command)
    if args and args[0] == "run":
        args = args[1:]

    env = os.environ.copy()
    env["RUN_DB"] = context.db_path
    if context.today:
        env["RUN_TODAY"] = context.today

    result = CliRunner().invoke(cli, args, env=env)
    context.last_output = result.output.strip()
    context.last_exit_code = result.exit_code


@given(parsers.parse('сегодня "{date}"'))
def today_is(cli_context, date):
    cli_context.today = date


@given(parsers.parse('я добавил пробежку {distance}km за {time}'))
def add_run(cli_context, distance, time):
    run_command(cli_context, f"run add {distance}km {time}")


@when(parsers.parse('я выполняю "{command}"'))
def run_cli_command(cli_context, command):
    run_command(cli_context, command)


@then(parsers.parse('вывод содержит "{text}"'))
def output_contains(cli_context, text):
    assert text in cli_context.last_output


@then(parsers.parse('вывод равен "{text}"'))
def output_equals(cli_context, text):
    assert cli_context.last_output == text


@then("вывод равен:")
def output_equals_block(cli_context, docstring):
    assert cli_context.last_output == docstring.strip()
