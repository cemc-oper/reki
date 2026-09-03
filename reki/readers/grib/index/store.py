"""SQLite schema v2, validation and atomic publication for GRIB metadata."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Iterable

import eccodes

from reki.diagnostics import record_io_event
from ..eccodes._scan import iter_headers
from .._header_metadata import parameter_names_from_message, time_metadata_from_message
from .lock import target_lock

INDEX_SCHEMA_VERSION = 2
SCHEMA_ID = "reki-grib-index/2"
QUERY_RULES_VERSION = "1"
METADATA_KEYS_VERSION = "3"
APPLICATION_ID = 0x524B4931


class IndexBuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceFingerprint:
    path: str
    st_dev: int
    st_ino: int
    size: int
    mtime_ns: int
    schema_version: int = INDEX_SCHEMA_VERSION


def fingerprint_file(path) -> SourceFingerprint:
    resolved = Path(path).resolve()
    stat = resolved.stat()
    return SourceFingerprint(str(resolved), stat.st_dev, stat.st_ino, stat.st_size,
                             stat.st_mtime_ns)


def default_index_dir():
    root = os.environ.get("REKI_INDEX_DIR")
    if root:
        return Path(root)
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "reki" / "indexes"


def index_path_for(path, index_dir=None) -> Path:
    fingerprint = fingerprint_file(path)
    digest = hashlib.sha256((SCHEMA_ID + "\0" + fingerprint.path).encode()).hexdigest()
    root = Path(index_dir) if index_dir is not None else default_index_dir()
    return root / (digest + ".sqlite")


_SCHEMA = """
CREATE TABLE index_meta (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), schema_version INTEGER NOT NULL, source_path TEXT NOT NULL, st_dev INTEGER NOT NULL, st_ino INTEGER NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, grib_editions_json TEXT NOT NULL, eccodes_version TEXT NOT NULL, builder_version TEXT NOT NULL, query_rules_version TEXT NOT NULL, metadata_keys_version TEXT NOT NULL, field_count INTEGER NOT NULL);
CREATE TABLE fields (ordinal INTEGER PRIMARY KEY, offset INTEGER NOT NULL, message_length INTEGER, edition INTEGER NOT NULL, discipline INTEGER, parameter_category INTEGER, parameter_number INTEGER, short_name TEXT, level_type TEXT, level_real REAL, level_text TEXT, first_level_type INTEGER, first_level REAL, second_level REAL, start_time_ns INTEGER, step_ns INTEGER, valid_time_ns INTEGER, step_type TEXT, time_range_ns INTEGER, member INTEGER, ni INTEGER, nj INTEGER, shape_json TEXT, dtype TEXT, grid_type TEXT, grid_digest TEXT, extra_metadata_json TEXT NOT NULL);
CREATE INDEX fields_query_v1 ON fields (short_name, discipline, parameter_category, parameter_number, level_type, level_real, step_type, member);
"""


def _get(message, key, default=None):
    try:
        return eccodes.codes_get(message, key)
    except (eccodes.KeyValueNotFoundError, eccodes.WrongTypeError):
        return default


def _row(header):
    message = header.handle
    ni, nj = _get(message, "Ni"), _get(message, "Nj")
    level = _get(message, "level")
    time_metadata = time_metadata_from_message(message)
    parameter_names = parameter_names_from_message(message)

    def nanoseconds(key):
        value = time_metadata[key]
        return None if value is None else value.value

    return (header.ordinal, header.offset, header.message_length, _get(message, "edition", 2),
            _get(message, "discipline"), _get(message, "parameterCategory"),
            _get(message, "parameterNumber"), _get(message, "shortName"),
            _get(message, "typeOfLevel"), float(level) if isinstance(level, (int, float)) else None,
            None if isinstance(level, (int, float)) else str(level) if level is not None else None,
            _get(message, "typeOfFirstFixedSurface"), None, None,
            nanoseconds("start_time"), nanoseconds("step"), nanoseconds("valid_time"),
            _get(message, "stepType"), nanoseconds("time_range"), _get(message, "number"), ni, nj,
            json.dumps([nj, ni]) if ni is not None and nj is not None else None, "float64",
            _get(message, "gridType"), None, json.dumps(parameter_names))


class IndexStore:
    """Build/open a v2 index.  Reader wiring deliberately belongs to T3-04."""
    def __init__(self, source_path, *, index_dir=None, lock_timeout=30.0):
        self.source_path = Path(source_path)
        self.index_dir = Path(index_dir) if index_dir is not None else default_index_dir()
        self.lock_timeout = lock_timeout

    @property
    def path(self):
        fingerprint = fingerprint_file(self.source_path)
        digest = hashlib.sha256((SCHEMA_ID + "\0" + fingerprint.path).encode()).hexdigest()
        return self.index_dir / f"{digest}.sqlite"

    def open_valid(self):
        path = self.path
        if not path.exists():
            record_io_event("index_miss_count", reason="absent")
            return None
        connection = None
        try:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            self._validate(connection, fingerprint_file(self.source_path))
        except sqlite3.DatabaseError:
            if connection is not None:
                connection.close()
            record_io_event("index_miss_count", reason="corrupt")
            return None
        except IndexBuildError as error:
            if connection is not None:
                connection.close()
            record_io_event("index_miss_count", reason=str(error))
            return None
        record_io_event("index_hit_count")
        return connection

    def build(self, *, refresh=False):
        try:
            self.index_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise IndexBuildError("unwritable") from error
        lock_path = self.path.with_suffix(".lock")
        try:
            with target_lock(lock_path, self.lock_timeout):
                valid = self.open_valid()
                if valid is not None and not refresh:
                    return valid
                if valid is not None:
                    valid.close()
                for attempt in range(2):
                    try:
                        return self._build_locked(refresh)
                    except IndexBuildError as error:
                        if str(error) != "source_changed" or attempt:
                            raise
        except TimeoutError as error:
            raise IndexBuildError("lock_timeout") from error

    def _build_locked(self, refresh):
        before = fingerprint_file(self.source_path)
        fd, name = tempfile.mkstemp(prefix=self.path.stem + ".", suffix=".tmp", dir=self.index_dir)
        os.close(fd)
        temporary = Path(name)
        try:
            connection = sqlite3.connect(temporary)
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version={INDEX_SCHEMA_VERSION}")
            connection.executescript(_SCHEMA)
            rows, editions = [], set()
            for header in iter_headers(before.path, headers_only=True):
                rows.append(_row(header)); editions.add(rows[-1][3])
            after = fingerprint_file(self.source_path)
            if before != after:
                raise IndexBuildError("source_changed")
            connection.executemany("INSERT INTO fields VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            connection.execute("INSERT INTO index_meta VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (1, INDEX_SCHEMA_VERSION, before.path, before.st_dev, before.st_ino, before.size, before.mtime_ns, json.dumps(sorted(editions)), str(eccodes.codes_get_api_version()), "reki", QUERY_RULES_VERSION, METADATA_KEYS_VERSION, len(rows)))
            connection.commit()
            self._validate(connection, before)
            connection.close()
            os.replace(temporary, self.path)
            record_io_event("index_rebuild_count" if refresh else "index_build_count")
            return self.open_valid()
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _validate(self, connection, fingerprint):
        if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            raise IndexBuildError("schema")
        row = connection.execute("SELECT schema_version, source_path, st_dev, st_ino, size, mtime_ns, eccodes_version, query_rules_version, metadata_keys_version, field_count FROM index_meta WHERE singleton=1").fetchone()
        if (row is None or row[0] != INDEX_SCHEMA_VERSION
                or row[7] != QUERY_RULES_VERSION or row[8] != METADATA_KEYS_VERSION):
            raise IndexBuildError("schema")
        if tuple(row[1:6]) != (fingerprint.path, fingerprint.st_dev, fingerprint.st_ino, fingerprint.size, fingerprint.mtime_ns):
            raise IndexBuildError("stale")
        if int(str(row[6]).split(".")[0]) != int(str(eccodes.codes_get_api_version()).split(".")[0]):
            raise IndexBuildError("decoder")
        if connection.execute("SELECT count(*) FROM fields").fetchone()[0] != row[9]:
            raise IndexBuildError("corrupt")
        return True
