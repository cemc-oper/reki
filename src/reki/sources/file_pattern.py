"""A deliberately small, expression-free local file pattern source."""

from __future__ import annotations

from pathlib import Path
from string import Formatter

import pandas as pd

from reki.core import Source
from reki.sources import get_source


_TEMPLATE_FIELDS = frozenset({
    "start_time_label", "forecast_hour", "forecast_hour_label",
})


def _format_template(template: str, values: dict[str, object], label: str) -> str:
    if not isinstance(template, str) or not template:
        raise ValueError(f"{label} must be a non-empty string")
    for _, field_name, format_spec, conversion in Formatter().parse(template):
        if field_name is None:
            continue
        if field_name not in _TEMPLATE_FIELDS or format_spec or conversion:
            raise ValueError(
                f"{label} uses unsupported template field {field_name!r}; "
                f"only simple {_TEMPLATE_FIELDS!r} substitutions are allowed"
            )
    try:
        return template.format(**values)
    except KeyError as exc:
        raise ValueError(f"{label} uses unknown template field {exc.args[0]!r}") from exc


class FilePatternSource(Source):
    """Render constrained directory and filename templates into a file source.

    Rendering does not inspect the filesystem.  The resulting ``file`` source
    opens data only when the normal reki source pipeline reaches its reader.
    """

    def __init__(self, data_dir, file_name_template, *, start_time, forecast_time="0", **kwargs):
        super().__init__(**kwargs)
        self.data_dir = data_dir
        self.file_name_template = file_name_template
        self.start_time = start_time
        self.forecast_time = forecast_time

    def resolve_path(self) -> Path:
        if isinstance(self.start_time, str) and len(self.start_time) == 10 and self.start_time.isdigit():
            start_time = pd.to_datetime(self.start_time, format="%Y%m%d%H")
        else:
            start_time = pd.Timestamp(self.start_time)
        forecast_time = pd.Timedelta(self.forecast_time)
        seconds = forecast_time.total_seconds()
        if seconds % 3600:
            raise ValueError("forecast_time must be an integer number of hours")
        forecast_hour = int(seconds // 3600)
        values = {
            "start_time_label": start_time.strftime("%Y%m%d%H"),
            "forecast_hour": forecast_hour,
            "forecast_hour_label": f"{forecast_hour:03d}",
        }
        data_dir = _format_template(str(self.data_dir), values, "data_dir")
        file_name = _format_template(self.file_name_template, values, "file_name_template")
        return Path(data_dir) / file_name

    def mutate(self):
        return get_source("file", self.resolve_path(), **self._kwargs)


source = FilePatternSource
