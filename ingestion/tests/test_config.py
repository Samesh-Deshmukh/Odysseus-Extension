from pathlib import Path

import pytest

from ingestion.config import Config, load_config


def test_load_config_reads_toml_and_env(tmp_path, monkeypatch):
    toml = tmp_path / "ingestion.toml"
    toml.write_text(
        'roots = ["/home/samesh/Storage/sames/Documents/A folder"]\n'
        'ignore_globs = ["**/.git/**", "**/node_modules/**"]\n'
        'extensions = [".md"]\n'
        'db_path = "staging.db"\n'
        'chunk_size = 1000\n'
        'chunk_overlap = 200\n'
        'odysseus_url = "http://localhost:7000"\n'
    )
    monkeypatch.setenv("ODYSSEUS_USER", "sam")
    monkeypatch.setenv("ODYSSEUS_PASSWORD", "secret")

    cfg = load_config(toml)

    assert isinstance(cfg, Config)
    assert cfg.roots == [Path("/home/samesh/Storage/sames/Documents/A folder")]
    assert "**/node_modules/**" in cfg.ignore_globs
    assert cfg.extensions == {".md"}
    assert cfg.chunk_size == 1000
    assert cfg.odysseus_url == "http://localhost:7000"
    assert cfg.odysseus_user == "sam"
    assert cfg.odysseus_password == "secret"


def test_env_url_overrides_toml(tmp_path, monkeypatch):
    toml = tmp_path / "ingestion.toml"
    toml.write_text('odysseus_url = "http://localhost:7000"\n')
    monkeypatch.setenv("ODYSSEUS_URL", "http://brain.lan:7000")
    monkeypatch.setenv("ODYSSEUS_USER", "sam")
    monkeypatch.setenv("ODYSSEUS_PASSWORD", "secret")

    cfg = load_config(toml)

    assert cfg.odysseus_url == "http://brain.lan:7000"


def test_missing_config_path_raises(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_USER", "sam")
    monkeypatch.setenv("ODYSSEUS_PASSWORD", "secret")

    with pytest.raises(FileNotFoundError):
        load_config(Path("/no/such/ingestion.toml"))
