"""Synthetic products only: these fixtures do not assert CEMC availability."""

import json
from copy import deepcopy

import pytest


@pytest.fixture
def resources(tmp_path):
    parameters = {
        "api_version": "cedarkit.parameters/v1",
        "id": "synthetic.parameters",
        "version": "1",
        "parameters": [
            {"parameter_id": "test.t", "name": "t", "unit": "K"},
            {
                "parameter_id": "test.t2m",
                "name": "t2m",
                "parent": "test.t",
                "fixed_conditions": {"level_type": "height_above_ground", "level": 2},
            },
        ],
    }
    mappings = {
        "api_version": "cedarkit.mappings/v1",
        "id": "synthetic.grib",
        "version": "1",
        "backend": "grib2",
        "tables": [],
        "mappings": [
            {
                "id": "temperature",
                "parameter_id": "test.t2m",
                "backend": "grib2",
                "applies_to": {
                    "dataset": "synthetic",
                    "product": "orig",
                    "product_version": "test-1",
                },
                "when": {},
                "native": {
                    "match": {
                        "discipline": 0,
                        "parameterCategory": 0,
                        "parameterNumber": 0,
                    },
                    "translate": {
                        "vertical": {"rule": "grib.fixed_surfaces"},
                        "unit": {"rule": "common.value_unit"},
                    },
                },
                "evidence": ["SYNTHETIC"],
            }
        ],
    }
    catalog = {
        "api_version": "cedarkit.catalog/v1",
        "id": "synthetic.catalog",
        "version": "1",
        "datasets": [
            {
                "id": "synthetic",
                "aliases": ["alias"],
                "mappings": {"grib2": {"path": "maps.json"}},
                "member_roles": {"0": "perturbation", "2": "control"},
                "execution": {"completeness": "required", "max_expansion": 25},
                "products": [
                    {
                        "id": "orig",
                        "version": "test-1",
                        "scope": {"step": "PT0H"},
                        "provides": [{"parameter": "test.t2m"}],
                        "populations": [],
                        "methods": [],
                        "sources": [
                            {"id": "files", "kind": "file"},
                            {"id": "local", "kind": "local"},
                            {
                                "id": "remote",
                                "kind": "cmadaas",
                                "data_code": "SYNTHETIC",
                                "interface_contract": {
                                    "id": "synthetic.grid",
                                    "version": 1,
                                },
                                "time_zone": "Asia/Shanghai",
                            },
                        ],
                        "evidence": ["SYNTHETIC"],
                    }
                ],
            }
        ],
    }

    def write(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return str(path)

    context = {
        "catalog": {"path": write("catalog.json", catalog)},
        "parameter_registry": {"path": write("parameters.json", parameters)},
    }
    write("maps.json", mappings)
    return {
        "parameters": parameters,
        "mappings": mappings,
        "catalog": catalog,
        "context": context,
        "write": write,
        "source": {"kind": "file", "path": "SYNTHETIC*.grb", "dataset": "alias"},
        "product": deepcopy(catalog["datasets"][0]["products"][0]),
    }
