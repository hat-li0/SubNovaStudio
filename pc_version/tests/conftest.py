from pathlib import Path
from typing import Optional
import pytest

import app.core.config as config_mod
from app.core.config import AppSettings
from app.core.database import DatabaseManager

_ORIG_SAVE = AppSettings.save_to_file
_ORIG_LOAD_FUNC = AppSettings.__dict__["load_from_file"].__func__
_ORIG_DB_INIT = DatabaseManager.__init__


@pytest.fixture(autouse=True)
def _isolate_runtime_state(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
):
    """Isolate config.json and subtitler.db per test so pytest never mutates user files."""
    iso_dir = tmp_path_factory.mktemp("subnova_iso")
    test_cfg = iso_dir / "config.json"
    test_db = iso_dir / "subtitler.db"
    created_dbs: list[DatabaseManager] = []
    orig_cfg_path = config_mod.CONFIG_FILE_PATH
    orig_db_path = config_mod.DEFAULT_DB_PATH

    monkeypatch.setattr(config_mod, "CONFIG_FILE_PATH", test_cfg)
    monkeypatch.setattr(config_mod, "DEFAULT_DB_PATH", str(test_db))
    monkeypatch.setattr(config_mod, "_settings_instance", None)

    def _is_default_cfg(path: Optional[str | Path]) -> bool:
        return path is None or Path(path) in (Path("config.json"), orig_cfg_path, test_cfg)

    def _is_default_db(candidate: Optional[str]) -> bool:
        return str(candidate) in ("subtitler.db", orig_db_path)

    def _isolated_save(self: AppSettings, path: Optional[str | Path] = None) -> None:
        target = test_cfg if _is_default_cfg(path) else path
        return _ORIG_SAVE(self, target)

    def _isolated_load(cls, path: Optional[str | Path] = None) -> AppSettings:
        target = test_cfg if _is_default_cfg(path) else path
        cfg = _ORIG_LOAD_FUNC(cls, target)
        if _is_default_db(cfg.db_path):
            cfg.db_path = str(test_db)
        return cfg

    def _isolated_db_init(self: DatabaseManager, db_path: Optional[str] = None) -> None:
        if db_path is None:
            settings = config_mod.get_settings()
            candidate = settings.db_path
            db_path = str(test_db) if _is_default_db(candidate) else candidate
        elif _is_default_db(str(db_path)):
            db_path = str(test_db)
        _ORIG_DB_INIT(self, db_path=db_path)
        created_dbs.append(self)

    monkeypatch.setattr(AppSettings, "save_to_file", _isolated_save)
    monkeypatch.setattr(AppSettings, "load_from_file", classmethod(_isolated_load))
    monkeypatch.setattr(DatabaseManager, "__init__", _isolated_db_init)

    yield

    monkeypatch.setattr(config_mod, "_settings_instance", None)
    for db in created_dbs:
        try:
            db.close()
        except Exception:
            pass
