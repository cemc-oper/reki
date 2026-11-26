"""Protected low-frequency adapters sharing v1 acquisition and assembly.

The raw ecCodes predicate is an adapter restriction, not another public Query
language. Its exact inputs are retained in the report's adapter provenance;
v1 still owns deduplication, conflicts, grid checks, coordinates and reports.
"""

import json

from cedarkit_query import QueryError
from reki._legacy import check_engine, ignore_index
from reki.catalog import plan_source_binding
from reki.core.source_spec import redact
from reki.selection.core import construct_source
from reki.translation.grib_backend import GribBackend, NATIVE_KEYS
from reki.translation.common import software_origin
from .eccodes._check import _check_message
from .eccodes._level import _fix_level


def read_collection(
    paths,
    parameter=None,
    level_type=None,
    level=None,
    *,
    engine="eccodes",
    with_index=False,
    single_variable=False,
    include_report: bool = False,
    **conditions,
):
    check_engine(engine)
    ignore_index(with_index)
    paths = list(paths)
    if not paths:
        raise QueryError("invalid_query", "/files", "File collection must be nonempty")
    fixed, _ = _fix_level(level_type, None)
    if level == "all":
        level = None
    selector = dict(
        parameter=parameter, level_type=level_type, level=level, **conditions
    )
    encoded = json.dumps(redact(selector), sort_keys=True, default=str)

    class LegacyBackend(GribBackend):
        def _legacy_filter(self, handle):
            return _check_message(handle, parameter, fixed, level, **conditions)

        def start(self, plan):
            scan = super().start(plan)
            scan.context["origins"]["adapter"] = software_origin(
                "grib.legacy;selection=" + encoded
            )
            return scan

    # Retain expressible native criteria in the Query snapshot as well as the
    # complete legacy predicate in provenance. Never infer a canonical identity.
    native = (
        {"shortName": parameter}
        if isinstance(parameter, str)
        else dict(parameter or {})
    )
    native.update(conditions)
    native = {k: v for k, v in native.items() if k in NATIVE_KEYS}
    query = {"native": {"grib": native}} if native else {}
    configuration = plan_source_binding(
        {"kind": "file", "path": [str(p) for p in paths]}
    )
    with construct_source(configuration, LegacyBackend(configuration)) as source:
        fields = source.sel(query).all()
        if single_variable:
            from reki.selection.output import _variable

            variables = {_variable(field)[0] for field in fields}
            if len(variables) > 1:
                raise QueryError(
                    "multiple_variables",
                    "",
                    "DataArray requires exactly one variable",
                    {
                        "operation": "load_field_from_files",
                        "variable_count": len(variables),
                    },
                )
        return fields.to_xarray(include_report=include_report)


def load_fields_from_file(
    file_path,
    parameter=None,
    level_type=None,
    level=None,
    with_index=False,
    *,
    engine="eccodes",
    include_report: bool = False,
):
    """Return a memory Dataset, with a report on request even if empty."""
    return read_collection(
        [file_path],
        parameter,
        level_type,
        level,
        with_index=with_index,
        engine=engine,
        include_report=include_report,
    )


def load_field_from_files(
    file_list,
    parameter,
    level_type,
    level,
    level_dim=None,
    show_progress=False,
    lazy=False,
    field_name=None,
    *,
    include_report: bool = False,
    **kwargs,
):
    """Return one variable or None; reject unsupported options and ambiguity."""
    if level_dim is not None:
        raise QueryError(
            "unsupported",
            "/level_dim",
            "Collection coordinates use the public organization",
        )
    if lazy:
        raise QueryError(
            "unsupported", "/lazy", "Collection results are independent memory arrays"
        )
    dataset = read_collection(
        file_list,
        parameter,
        level_type,
        level,
        single_variable=True,
        include_report=include_report,
        **kwargs,
    )
    if not dataset.data_vars:
        return None
    if len(dataset.data_vars) != 1:
        raise QueryError(
            "multiple_variables",
            "",
            "DataArray requires exactly one variable",
            {
                "variables": list(dataset.data_vars),
                "operation": "load_field_from_files",
            },
        )
    value = dataset[next(iter(dataset.data_vars))]
    return value.rename(field_name) if field_name is not None else value
