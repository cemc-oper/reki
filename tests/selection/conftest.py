"""All fixtures are SYNTHETIC. No business/native/backend acceptance is implied."""

from dataclasses import replace
import json

import numpy as np
import pytest
import xarray as xr

from cedarkit_query import normalize_query
from reki.catalog import plan_source_binding
from reki.catalog.model import thaw
from reki.selection.backend import Plan, FieldReference
from reki.selection.core import construct_source, matches

TIME = "2026-01-01T00:00:00Z"
GRID = {"type": "SYNTHETIC_regular_latlon", "projection": "SYNTHETIC-earth-v1"}


def identity(**changes):
    return normalize_query(
        {
            **dict(
                parameter="synthetic.t",
                level_type="pressure",
                level=850,
                time=TIME,
                step="PT6H",
            ),
            **changes,
        }
    )


class Scan:
    def __init__(self, backend, plan):
        self.backend, self.plan, self.context = backend, plan, {}

    def __iter__(self):
        for ref in self.backend.records:
            self.backend.visits += 1
            if isinstance(ref, Exception):
                raise ref
            yield replace(
                ref, branches=tuple((i, 0) for i in range(len(self.plan.translations)))
            )

    def close(self):
        self.backend.scan_closes += 1


class ControlledBackend:
    """Exhaustive fixture acquisition; expected sets are supplied independently."""

    def __init__(self, records, expected, *, branches=1, residual=None, pending=False):
        self.records, self.expected = records, expected
        self.branch_count, self.residual, self.pending = branches, residual, pending
        self.visits = self.loads = self.starts = self.scan_closes = self.closes = 0

    def plan(self, queries, configuration):
        self.queries = queries
        return Plan(
            tuple(
                dict(
                    query_index=i,
                    coverage=dict(
                        status="pending" if self.pending else "passed",
                        message="SYNTHETIC exhaustive fixture scope",
                    ),
                    branches=[
                        dict(
                            index=bi,
                            backend="grib2",
                            scope={},
                            candidate_filter={},
                            residual={} if self.residual is None else self.residual,
                            basis=[dict(kind="builtin", rule="SYNTHETIC.i05.fixture")],
                        )
                        for bi in range(self.branch_count)
                    ],
                    checks=[
                        dict(
                            code="complete_retrieval_supported",
                            status="passed",
                            message="SYNTHETIC fixture stream",
                        )
                    ],
                )
                for i, _ in enumerate(queries)
            ),
            tuple(
                None
                if self.expected is None
                else tuple(q.to_dict() for q in self.expected if matches(q, query))
                for query in queries
            ),
        )

    def start(self, plan):
        self.starts += 1
        return Scan(self, plan)

    def close(self):
        self.closes += 1


@pytest.fixture
def factory(tmp_path):
    params = dict(
        api_version="cedarkit.parameters/v1",
        id="SYNTHETIC.parameters",
        version="1",
        parameters=[
            dict(parameter_id="synthetic.t", name="t", unit="K"),
            dict(parameter_id="synthetic.u", name="u", unit="m/s"),
            dict(parameter_id="synthetic.st", name="st", unit="K"),
        ],
    )
    path = tmp_path / "parameters.json"
    path.write_text(json.dumps(params))
    dummy = tmp_path / "SYNTHETIC.not-grib"
    dummy.write_bytes(b"NOT A BUSINESS FILE; NEVER DECODED")

    def make(
        identities=(),
        expected=(),
        *,
        context=None,
        metadata=None,
        grid=None,
        records=None,
        branches=1,
        residual=None,
        pending=False,
        no_resources=False,
        extra_parameters=(),
    ):
        if extra_parameters:
            path.write_text(
                json.dumps(
                    {
                        **params,
                        "parameters": params["parameters"] + list(extra_parameters),
                    }
                )
            )
        ctx = {} if no_resources else dict(parameter_registry={"path": str(path)})
        ctx.update(context or {})
        configuration = plan_source_binding(
            dict(kind="file", path=str(dummy)), context=ctx
        )
        backend = ControlledBackend(
            [], expected, branches=branches, residual=residual, pending=pending
        )
        refs = []
        for i, query in enumerate(identities):
            q = normalize_query(query)
            p = (
                None
                if no_resources or "parameter" not in q.to_dict()
                else configuration.resources.parameter(q.parameter)
            )
            meta = dict(
                source_unit="K",
                unit="K",
                vertical_definition={"id": "SYNTHETIC.pressure-v1"},
            )
            if p:
                meta.update(
                    parameter_id=p["parameter_id"],
                    parameter_name=p["name"],
                    unit=p["unit"],
                    source_unit=p["unit"],
                    fixed_conditions=thaw(p["fixed_conditions"]),
                )
            meta.update(metadata or {})

            def load(i=i):
                backend.loads += 1
                return xr.DataArray(
                    np.full((2, 2), float(i + 1)),
                    dims=("latitude", "longitude"),
                    coords={"latitude": [45.0, 40.0], "longitude": [100.0, 105.0]},
                )

            refs.append(
                FieldReference(
                    f"SYNTHETIC:version-1:record-{i}",
                    q,
                    meta,
                    GRID if grid is None else grid,
                    load,
                    ((0, 0),),
                )
            )
        backend.records = refs if records is None else records
        return construct_source(configuration, backend), backend, refs

    return make


@pytest.fixture
def q():
    return identity()
