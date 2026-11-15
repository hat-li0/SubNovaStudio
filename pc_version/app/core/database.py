import sqlite3
import threading
import shutil
from datetime import datetime
from typing import Any, List, Optional, Tuple, Dict, Set
from pathlib import Path
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class DatabaseManager:
    """SQLite DatabaseManager class for subtitler app with thread-local pooling and indexing."""

    _SALVAGE_TABLES = (
        "anime",
        "anime_sources",
        "characters",
        "character_aliases",
        "glossary",
        "translation_memory",
        "settings",
        "api_cache",
    )
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            settings = get_settings()
            db_path = settings.db_path
        self._is_memory = str(db_path) == ":memory:"
        self.db_path = ":memory:" if self._is_memory else Path(db_path)
        if not self._is_memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._memory_conn: Optional[sqlite3.Connection] = None
        self._local = threading.local()
        self._all_conns: Set[sqlite3.Connection] = set()
        self._lock = threading.RLock()
        self._recovering = False
        if self._is_memory:
            self._memory_conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row
        else:
            self._verify_and_recover_corruption(force=False)
        self._init_schema()

    @staticmethod
    def _is_corruption_error(exc: Exception) -> bool:
        if not isinstance(exc, sqlite3.DatabaseError):
            return False
        msg = str(exc).lower()
        return any(k in msg for k in (
            "malformed", "not a database", "corrupt",
            "file is encrypted", "disk image is malformed"
        ))

    def _verify_and_recover_corruption(self, force: bool = False) -> bool:
        """
        Verifies SQLite file integrity and automatically quarantines damaged files while
        salvaging all readable rows into a clean rebuilt database.
        """
        if self._is_memory or not isinstance(self.db_path, Path):
            return False
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            return False

        if not force:
            is_healthy = False
            check_conn = None
            try:
                check_conn = sqlite3.connect(str(self.db_path), timeout=2.0, isolation_level=None)
                rows = check_conn.execute("PRAGMA integrity_check").fetchall()
                is_healthy = bool(rows) and all(str(r[0]).lower() == "ok" for r in rows)
            except Exception as e:
                logger.warning(f"Database integrity check failed for {self.db_path}: {e}")
                if not self._is_corruption_error(e):
                    # Locked, busy, or permission errors are NOT corruption: do not quarantine
                    return False
                is_healthy = False
            finally:
                if check_conn is not None:
                    try:
                        check_conn.close()
                    except Exception:
                        pass
            if is_healthy:
                return False

        with self._lock:
            if self._recovering:
                return False
            self._recovering = True
            try:
                self.close()

                salvaged: Dict[str, Tuple[List[str], List[Tuple[Any, ...]]]] = {}
                salvage_conn = None
                try:
                    salvage_conn = sqlite3.connect(str(self.db_path), timeout=2.0)
                    for tbl in self._SALVAGE_TABLES:
                        try:
                            cur = salvage_conn.execute(f"SELECT * FROM {tbl}")
                            cols = [d[0] for d in (cur.description or [])]
                            rows_list: List[Tuple[Any, ...]] = []
                            while True:
                                try:
                                    row = cur.fetchone()
                                    if row is None:
                                        break
                                    rows_list.append(tuple(row))
                                except sqlite3.DatabaseError:
                                    break
                            if cols and rows_list:
                                salvaged[tbl] = (cols, rows_list)
                        except Exception:
                            continue
                except Exception as salvage_err:
                    logger.warning(f"Partial salvage error for {self.db_path}: {salvage_err}")
                finally:
                    if salvage_conn is not None:
                        try:
                            salvage_conn.close()
                        except Exception:
                            pass

                ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                backup_path = Path(f"{self.db_path}.corrupt.{ts}.bak")
                try:
                    shutil.move(str(self.db_path), str(backup_path))
                except Exception as mv_err:
                    logger.error(f"Could not move corrupt DB {self.db_path}: {mv_err}")
                    try:
                        self.db_path.unlink(missing_ok=True)
                    except Exception:
                        return False

                for suffix in ("-wal", "-shm"):
                    sidecar = Path(f"{self.db_path}{suffix}")
                    if sidecar.exists():
                        try:
                            shutil.move(str(sidecar), f"{sidecar}.corrupt.{ts}.bak")
                        except Exception:
                            try:
                                sidecar.unlink(missing_ok=True)
                            except Exception:
                                pass

                self._init_schema()

                if salvaged:
                    conn = self.get_connection()
                    try:
                        conn.execute("PRAGMA foreign_keys=OFF;")
                        for tbl, (cols, rows_list) in salvaged.items():
                            col_sql = ", ".join(cols)
                            placeholders = ", ".join("?" for _ in cols)
                            sql = f"INSERT OR IGNORE INTO {tbl} ({col_sql}) VALUES ({placeholders})"
                            try:
                                conn.executemany(sql, rows_list)
                            except Exception as ins_err:
                                logger.warning(f"Salvage skip on {tbl}: {ins_err}")
                        conn.execute("PRAGMA foreign_keys=ON;")
                    except Exception as restore_err:
                        logger.warning(f"Failed restoring salvaged rows: {restore_err}")

                restored_count = sum(len(v[1]) for v in salvaged.values())
                logger.warning(
                    f"Quarantined corrupt database to {backup_path.name} and rebuilt clean DB "
                    f"(salvaged {restored_count} rows across {len(salvaged)} tables)."
                )
                return True
            finally:
                self._recovering = False

    def get_connection(self) -> sqlite3.Connection:
        """Returns a configured connection to the database (reusing per-thread instance with robust fallback)."""
        if self._is_memory and self._memory_conn is not None:
            return self._memory_conn

        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                # Test connection is alive
                conn.execute("SELECT 1")
                return conn
            except Exception:
                conn = None

        db_file = str(self.db_path)
        try:
            conn = sqlite3.connect(db_file, timeout=10.0, isolation_level=None, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Try WAL mode, but fallback safely to DELETE if filesystem does not permit shared memory (shm/wal)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
            except Exception:
                try:
                    conn.execute("PRAGMA journal_mode=DELETE;")
                except Exception:
                    pass
            conn.execute("PRAGMA foreign_keys=ON;")
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as open_err:
            logger.warning(f"Failed opening database at {db_file}: {open_err}. Attempting fallback connection...")
            # If the database file could not be opened (e.g. read-only, locked, or protected directory),
            # try fallback to a local safe user_data location or memory
            from app.core.resources import get_app_data_dir
            fallback_dir = get_app_data_dir()
            fallback_db = fallback_dir / "subtitler.db"
            if str(fallback_db) != db_file:
                try:
                    fallback_db.parent.mkdir(parents=True, exist_ok=True)
                    conn = sqlite3.connect(str(fallback_db), timeout=10.0, isolation_level=None, check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    conn.execute("PRAGMA foreign_keys=ON;")
                    self.db_path = fallback_db
                except Exception:
                    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    self._is_memory = True
                    self._memory_conn = conn
            else:
                conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                self._is_memory = True
                self._memory_conn = conn

        self._local.conn = conn
        with self._lock:
            self._all_conns.add(conn)
        return conn

    def close(self) -> None:
        """Closes all open database connections cleanly."""
        with self._lock:
            for conn in list(self._all_conns):
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_conns.clear()
        if hasattr(self._local, "conn"):
            self._local.conn = None
        if self._memory_conn:
            try:
                self._memory_conn.close()
            except Exception:
                pass
            self._memory_conn = None

    def _init_schema(self) -> None:
        """Initialize database schema."""
        queries = [
            '''
            CREATE TABLE IF NOT EXISTS anime (
                id INTEGER PRIMARY KEY,
                title_romaji TEXT,
                title_english TEXT,
                title_native TEXT,
                title_user TEXT,
                episodes INTEGER,
                format TEXT,
                status TEXT,
                cover_image_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS anime_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER,
                source_name TEXT,
                source_id TEXT,
                source_url TEXT,
                FOREIGN KEY (anime_id) REFERENCES anime(id) ON DELETE CASCADE
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER,
                canonical_name TEXT,
                first_name TEXT,
                last_name TEXT,
                native_name TEXT,
                arabic_name TEXT,
                gender TEXT,
                gender_source TEXT,
                gender_confidence REAL,
                role TEXT,
                age TEXT,
                description TEXT,
                voice_actor TEXT,
                speech_style TEXT,
                translation_notes TEXT,
                is_user_override INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (anime_id) REFERENCES anime(id) ON DELETE CASCADE
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS character_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER,
                alias TEXT,
                alias_type TEXT,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS glossary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER,
                source_term TEXT,
                target_term TEXT,
                is_exact_match INTEGER DEFAULT 1,
                is_case_sensitive INTEGER DEFAULT 0,
                notes TEXT,
                FOREIGN KEY (anime_id) REFERENCES anime(id) ON DELETE CASCADE
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS translation_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_hash TEXT,
                source_text TEXT,
                translated_text TEXT,
                source_lang TEXT,
                target_lang TEXT,
                anime_id INTEGER,
                character_id INTEGER,
                speaker TEXT DEFAULT '',
                speaker_gender TEXT DEFAULT '',
                provider TEXT,
                model TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT,
                source TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                ttl_seconds INTEGER
            )
            ''',
            'CREATE INDEX IF NOT EXISTS idx_tm_lookup ON translation_memory(source_hash, source_lang, target_lang);',
            'CREATE INDEX IF NOT EXISTS idx_characters_anime ON characters(anime_id);',
            'CREATE INDEX IF NOT EXISTS idx_glossary_anime ON glossary(anime_id);',
            'CREATE INDEX IF NOT EXISTS idx_anime_sources_anime ON anime_sources(anime_id);',
            'CREATE INDEX IF NOT EXISTS idx_character_aliases_char ON character_aliases(character_id);'
        ]
        
        try:
            with self.get_connection() as conn:
                for query in queries:
                    conn.execute(query)
                # Idempotent column migrations for existing databases
                existing_tm_cols = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(translation_memory)").fetchall()
                }
                if "speaker" not in existing_tm_cols:
                    conn.execute("ALTER TABLE translation_memory ADD COLUMN speaker TEXT DEFAULT ''")
                if "speaker_gender" not in existing_tm_cols:
                    conn.execute("ALTER TABLE translation_memory ADD COLUMN speaker_gender TEXT DEFAULT ''")
                logger.info("Database schema initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            if not self._is_memory:
                logger.warning("Attempting emergency fallback to in-memory SQLite schema...")
                try:
                    self._is_memory = True
                    self._memory_conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
                    self._memory_conn.row_factory = sqlite3.Row
                    for query in queries:
                        self._memory_conn.execute(query)
                    return
                except Exception as mem_err:
                    logger.critical(f"In-memory fallback also failed: {mem_err}")
            raise

    def execute(self, sql: str, params: Tuple = ()) -> sqlite3.Cursor:
        """Execute a single query and return the cursor."""
        try:
            with self.get_connection() as conn:
                return conn.execute(sql, params)
        except sqlite3.DatabaseError as e:
            if not self._is_memory and self._is_corruption_error(e):
                if self._verify_and_recover_corruption(force=True):
                    with self.get_connection() as conn:
                        return conn.execute(sql, params)
            raise

    def fetch_one(self, sql: str, params: Tuple = ()) -> Optional[sqlite3.Row]:
        """Fetch a single row."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(sql, params)
                return cursor.fetchone()
        except sqlite3.DatabaseError as e:
            if not self._is_memory and self._is_corruption_error(e):
                if self._verify_and_recover_corruption(force=True):
                    with self.get_connection() as conn:
                        cursor = conn.execute(sql, params)
                        return cursor.fetchone()
            raise

    def fetch_all(self, sql: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Fetch all rows."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(sql, params)
                return cursor.fetchall()
        except sqlite3.DatabaseError as e:
            if not self._is_memory and self._is_corruption_error(e):
                if self._verify_and_recover_corruption(force=True):
                    with self.get_connection() as conn:
                        cursor = conn.execute(sql, params)
                        return cursor.fetchall()
            raise
            
    def clear_translation_memory(self) -> None:
        """Clears all stored translation memory entries."""
        try:
            self.execute("DELETE FROM translation_memory")
            logger.info("Translation memory cleared.")
        except Exception as e:
            logger.error(f"Failed to clear translation memory: {e}")

    def clear_cache(self) -> None:
        """Clears both api_cache and translation_memory tables."""
        try:
            self.execute("DELETE FROM api_cache")
            self.execute("DELETE FROM translation_memory")
            logger.info("API cache and translation memory cleared.")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    def get_cache(self, cache_key: str) -> Optional[Any]:
        """Fetch cached data if available and not expired."""
        import json
        from datetime import datetime, timezone
        try:
            row = self.fetch_one(
                "SELECT data, created_at, ttl_seconds FROM api_cache WHERE cache_key = ?",
                (cache_key,)
            )
            if not row:
                return None
                
            # Check TTL expiry
            ttl = row["ttl_seconds"]
            created = row["created_at"]
            if ttl is not None and created is not None:
                try:
                    # Parse 'YYYY-MM-DD HH:MM:SS' into UTC datetime
                    created_str = str(created).replace(" ", "T")
                    created_dt = datetime.fromisoformat(created_str).replace(tzinfo=timezone.utc)
                    now_dt = datetime.now(timezone.utc)
                    age_seconds = (now_dt - created_dt).total_seconds()
                    if age_seconds > ttl:
                        self.execute("DELETE FROM api_cache WHERE cache_key = ?", (cache_key,))
                        return None
                except Exception as ex:
                    logger.debug(f"TTL parse exception: {ex}")

            data_str = row["data"]
            try:
                return json.loads(data_str)
            except Exception:
                return data_str
        except Exception as e:
            logger.error(f"Failed to get cache for {cache_key}: {e}")
            return None

    def set_cache(self, cache_key: str, data: Any, source: str = "", ttl_seconds: int = 86400 * 7) -> None:
        """Store data in api_cache table."""
        import json
        try:
            data_str = json.dumps(data) if not isinstance(data, str) else data
            self.execute(
                """
                INSERT OR REPLACE INTO api_cache (cache_key, data, source, created_at, ttl_seconds)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (cache_key, data_str, source, ttl_seconds)
            )
        except Exception as e:
            logger.error(f"Failed to set cache for {cache_key}: {e}")
