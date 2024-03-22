from typer.testing import CliRunner # type: ignore

from pikesquares.cli.cli import app

runner = CliRunner()


def test_app():
    #result = runner.invoke(app, ["Camila", "--city", "Berlin"])
    #assert result.exit_code == 0
    #assert "Hello Camila" in result.stdout
    #assert "Let's have a coffee in Berlin" in result.stdout

    result = runner.invoke(app, ["--version", ])
    assert result.exit_code == 0


class TestClass:
    def test_one(self):
        x = "this"
        assert "h" in x

    def test_two(self):
        x = "hello"
        assert hasattr(x, "check")
