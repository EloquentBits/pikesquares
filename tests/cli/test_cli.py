# import shlex
import traceback

import pytest
import structlog
from typer.testing import CliRunner  # type: ignore

from pikesquares.cli.cli import app
from pikesquares.conf import ensure_system_path

runner = CliRunner(
    mix_stderr=False,
)

logger = structlog.getLogger()


"""
PIKESQUARES_VERSION="0.0.40.dev0"
PIKESQUARES_UWSGI_BIN="/home/pk/dev/eqb/scie-pikesquares/uwsgi/uwsgi"
PIKESQUARES_UV_BIN="/home/pk/.local/bin/uv"
PIKESQUARES_CADDY_BIN="/home/pk/.local/bin/caddy"
PIKESQUARES_PYTHON_VIRTUAL_ENV="/home/pk/dev/eqb/pikesquares/.venv"
PIKESQUARES_PROCESS_COMPOSE_BIN="/home/pk/.local/bin/process-compose"
PIKESQUARES_ENABLE_TUNTAP_ROUTER="false"
PIKESQUARES_SENTRY_DSN="http://7e27f7171f894edb9405f5ed9cd308bb@localhost:8000/1"
PIKESQUARES_DNSMASQ_BIN="/home/pk/.local/bin/dnsmasq"
PIKESQUARES_SQLITE_PLUGIN="/home/pk/dev/eqb/scie-pikesquares/uwsgi/sqlite3_plugin.so"
"""


# @pytest.mark.asyncio
def test_app():
    # i result = runner.invoke(app, ["Camila", "--city", "Berlin"])
    # assert result.exit_code == 0
    # assert "Hello Camila" in result.stdout
    # assert "Let's have a coffee in Berlin" in result.stdout

    result = runner.invoke(
        app,
        [
            "--help",
        ],
    )
    assert result.exit_code == 0


# @pytest.mark.asyncio
def test_up(conf):
    context = {}
    result = runner.invoke(app, ["up"], obj=context)

    if result.exception:
        traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)

    output = result.stdout.rstrip()
    logger.debug(output)

    # errors = result.stderr.rstrip()
    # logger.debug(errors)

    assert result.exit_code == 0


def test_ensure_system_paths(conf):

    new_path = conf.data_dir
    # owner_name
    # owner_groupname
    # owner_uid
    # owner_gid

    ensure_system_path(new_path)


"""
def test_typer_yaml_with_list():
    runner = CliRunner()
    test_args = ['src/yaml_configs/config.yml', '--env', 'rest']
    result = runner.invoke(app, test_args)
    assert result.exit_code == 0
    # Use result.stdout to access the command's output
    output = result.stdout.rstrip()
    expected_output = "{'url': 'https://example.com/', 'port': 3001}"
    assert expected_output in output


test_cases = [
    (
        "src/yaml_configs/config.yml",  # Valid path without optional args
        "{'url': 'https://example.com/', 'port': 3001}",
    ),
    (
        "src/yaml_configs/config.yml --env 'dev'",  # Valid path witho optional args
        "{'url': 'https://dev.com/', 'port': 3010}",
    ),
    (
        "--env 'prod' 'src/yaml_configs/config.yml'",  # Different order
        "{'url': 'https://prod.com/', 'port': 2007}",
    ),
    (
        "src/config.yml --env 'prod'",  # Path not exist
        "`configpath` must be a valid file path. Provided path: `src/config.yml` does not exist.",
    ),
    (
        " ",  # Null or None value passed
        "Missing argument",
    ),
    (
        "",  # No argument passed
        "Missing argument",
    ),
    (
        "'src/yaml_configs/config.yml' -env 'dev'",  # Invalid flag
        "No such option",
    ),
    (
        "src/yaml_configs==config.yml --env 'dev'",  # Invalid ascii character passsed
        "`configpath` must be a valid file path. Provided path: `src/yaml_configs==config.yml` does not exist.",
    ),
    (
        "path/to/nonexistent/file.yml --env 'dev'",  # Nonexistent file
        "`configpath` must be a valid file path. Provided path: `path/to/nonexistent/file.yml` does not exist.",
    ),
]


# Testing typer_yaml_reader()
@pytest.mark.parametrize("command, expected_output", test_cases)
def test_typer_yaml_reader(command, expected_output):
    result = runner.invoke(app, shlex.split(command))
    assert expected_output in result.stdout


class TestClass:
    def test_one(self):
        x = "this"
        assert "h" in x

    def test_two(self):
        x = "hello"
        assert hasattr(x, "check")
"""
