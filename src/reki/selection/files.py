"""I05 file ordering and snapshot utilities for native adapters, without caches."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from string import Formatter
import os
from stat import S_ISREG

from cedarkit_query import QueryError, SourceError, expand_queries
from cedarkit_query.normalize import duration_seconds


def discover_paths(configuration, queries=()):
    """Terminal-only path discovery; never called by construction/sel/explain.

    Literal paths remain literal and ordered. Directory patterns are root-relative,
    deduplicated and lexically sorted. Local templates use registered I04 layouts;
    explicit missing files remain paths for the adapter to classify by its scope.
    Omitted local leads discover actual files within the explicit origin layout.
    """
    source = configuration.source
    kind = source["kind"]
    if kind == "file" and "path" in source:
        paths = source["path"]
        paths = paths if isinstance(paths, tuple) else (paths,)
    elif kind == "file":
        directory = Path(source["directory"])
        patterns = source["glob"]
        patterns = patterns if isinstance(patterns, tuple) else (patterns,)
        found = set()
        try:
            for pattern in patterns:
                if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
                    raise QueryError(
                        "invalid_config",
                        "/source/glob",
                        "glob must stay within directory",
                    )
                for path in directory.glob(pattern):
                    if path.is_file():
                        found.add(os.path.abspath(path))
        except PermissionError as exc:
            raise SourceError(
                "permission_denied", "/source/directory", "cannot discover files"
            ) from exc
        except OSError as exc:
            raise SourceError(
                "io_error", "/source/directory", "file discovery failed"
            ) from exc
        paths = sorted(found)
    elif kind == "local":
        rows = expand_queries(
            list(queries),
            max_expansion=configuration.execution_defaults["max_expansion"],
            member_roles=configuration.member_roles,
            cemc=configuration.cemc_member_roles,
        )
        root = Path(source["root"]).resolve()
        paths = _local_paths(root, configuration.layout, rows)
        fallback_layout = getattr(configuration, "fallback_layout", ())
        if fallback_layout:
            fallback = _local_paths(root, fallback_layout, rows)
            paths = _merge_fallback_paths(paths, fallback)

    else:
        raise QueryError("unsupported", "/source", "source is not a file locator")
    return tuple(dict.fromkeys(Path(p).absolute() for p in paths))


def _local_paths(root, templates, rows):
    paths = []
    for template in templates:
        rendered = []
        for row in rows:
            values = _template_values(template, row.to_dict())
            pattern = template.format(**values)
            path = root / pattern
            if not path.resolve().is_relative_to(root):
                raise QueryError("invalid_config", "/source/root", "local path escapes root")
            if "*" not in values.values():
                rendered.append(path)
                continue
            # Discover actual files for the explicit origin, lead and member pattern.
            try:
                for found in root.glob(pattern):
                    if not found.resolve().is_relative_to(root):
                        raise QueryError("invalid_config", "/source/root", "local path escapes root")
                    if found.is_file():
                        rendered.append(found)
            except PermissionError as exc:
                raise SourceError(
                    "permission_denied", "/source/directory", "cannot discover local files"
                ) from exc
            except OSError as exc:
                raise SourceError(
                    "io_error", "/source/directory", "local file discovery failed"
                ) from exc
        paths.extend(sorted(set(rendered)))
    return paths


def _merge_fallback_paths(primary, fallback):
    # A matching filename keeps the exact cycle, lead and member across dates.
    alternatives = {}
    for path in fallback:
        if _is_archive_file(path):
            alternatives.setdefault(path.name, path)
    for path in primary:
        if path.name in alternatives and _is_archive_file(path):
            del alternatives[path.name]
    return [alternatives.pop(path.name, path) for path in primary] + list(alternatives.values())


def _is_archive_file(path):
    try:
        return S_ISREG(path.stat().st_mode)
    except FileNotFoundError:
        return False
    except PermissionError as exc:
        raise SourceError(
            "permission_denied", "/source/path", "cannot inspect archive path"
        ) from exc
    except OSError as exc:
        raise SourceError("io_error", "/source/path", "cannot inspect archive path") from exc


def _template_fields(template):
    return {name for _, name, _, _ in Formatter().parse(template) if name is not None}


def _template_values(template, query):
    fields = _template_fields(template)
    values = {}
    if fields & {
        "start_time_label",
        "date_label",
        "year",
        "beijing_date_label",
        "beijing_year",
        "next_beijing_date_label",
        "next_beijing_year",
    }:
        time = query.get("time")
        if not isinstance(time, str):
            raise QueryError(
                "unsupported", "/queries", "local layout needs explicit discrete time"
            )
        dt = datetime.fromisoformat(time.replace("Z", "+00:00"))
        # Registered legacy templates are hourly; never round finer origin times.
        if "start_time_label" in fields and (dt.minute or dt.second or "." in time):
            raise QueryError(
                "unsupported", "/queries", "hourly layout cannot represent finer time"
            )
        values.update(
            start_time_label=dt.strftime("%Y%m%d%H"),
            date_label=dt.strftime("%Y%m%d"),
            year=dt.strftime("%Y"),
        )
        # REPS is stored by the Beijing date of the UTC reference time.
        # This affects directory rendering only; canonical time stays UTC.
        local = dt.astimezone(ZoneInfo("Asia/Shanghai"))
        values.update(
            beijing_date_label=local.strftime("%Y%m%d"),
            beijing_year=local.strftime("%Y"),
        )
        if fields & {"next_beijing_date_label", "next_beijing_year"}:
            next_day = local + timedelta(days=1)
            values.update(
                next_beijing_date_label=next_day.strftime("%Y%m%d"),
                next_beijing_year=next_day.strftime("%Y"),
            )
    if fields & {"forecast_hour", "forecast_hour_label"}:
        step = query.get("step")
        if step is None:
            values.update(forecast_hour="*", forecast_hour_label="*")
        elif not isinstance(step, str) or duration_seconds(step) % 3600:
            raise QueryError(
                "unsupported",
                "/queries",
                "hourly layout cannot represent this step",
            )
        else:
            hour = int(duration_seconds(step) / 3600)
            values.update(forecast_hour=hour, forecast_hour_label=f"{hour:03d}")
    if "member_3digit" in fields:
        member = query.get("member")
        if member is None:
            values["member_3digit"] = "*"
        elif type(member) is not int or not 0 <= member <= 999:
            raise QueryError(
                "unsupported", "/queries", "member template needs a member in 0..999"
            )
        else:
            values["member_3digit"] = f"{member:03d}"
    return values


def _fingerprint(stat):
    return (
        stat.st_dev,
        stat.st_ino,
        stat.st_size,
        stat.st_mtime_ns,
        stat.st_ctime_ns,
    )


def _stat(path):
    try:
        return _fingerprint(Path(path).stat())
    except FileNotFoundError as exc:
        raise SourceError(
            "resource_not_found", "/source/path", "file no longer exists"
        ) from exc
    except PermissionError as exc:
        raise SourceError(
            "permission_denied", "/source/path", "cannot inspect file snapshot"
        ) from exc
    except OSError as exc:
        raise SourceError(
            "io_error", "/source/path", "file snapshot inspection failed"
        ) from exc


@dataclass(frozen=True)
class FileSnapshot:
    """Pin one file generation; native record IDs must also include message location."""

    path: Path
    fingerprint: tuple

    @classmethod
    def capture(cls, path):
        path = Path(path).absolute()
        return cls(path, _stat(path))

    def verify(self, stream=None):
        actual = (
            _stat(self.path) if stream is None else _fingerprint(os.fstat(stream.fileno()))
        )
        if actual != self.fingerprint:
            raise SourceError(
                "io_error",
                "/source/path",
                "file changed since selection",
                {"reason": "resource_changed"},
            )

    def load(self, loader):
        """Load array values inside the generation guard, without retaining a cache."""
        self.verify()
        result = loader()
        load = getattr(result, "load", None)
        if callable(load):
            result = load()
        self.verify()
        return result
