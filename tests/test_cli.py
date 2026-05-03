import pytest
from insta_loader.cli import parse_args, Config


def test_parse_args_username():
    config = parse_args(["natgeo", "--highlight", "Travel"])
    assert config.username == "natgeo"


def test_parse_args_highlight_flag():
    config = parse_args(["natgeo", "--highlight", "Travel"])
    assert config.highlight == "Travel"


def test_parse_args_output_dir_flag():
    config = parse_args(["natgeo", "--highlight", "Travel", "--output-dir", "/tmp/out"])
    assert config.output_dir == "/tmp/out"


def test_parse_args_output_dir_defaults_to_none():
    config = parse_args(["natgeo", "--highlight", "Travel"])
    assert config.output_dir is None


def test_parse_args_highlight_defaults_to_none_after_confirmation(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    config = parse_args(["natgeo"])
    assert config.highlight is None


def test_parse_args_no_highlight_y_continues(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    config = parse_args(["natgeo"])
    assert config.username == "natgeo"


def test_parse_args_no_highlight_n_exits_0(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    with pytest.raises(SystemExit) as exc:
        parse_args(["natgeo"])
    assert exc.value.code == 0


def test_parse_args_no_highlight_empty_input_exits_0(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    with pytest.raises(SystemExit) as exc:
        parse_args(["natgeo"])
    assert exc.value.code == 0


def test_parse_args_returns_config_instance():
    config = parse_args(["natgeo", "--highlight", "Travel"])
    assert isinstance(config, Config)
