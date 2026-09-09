"""Metadata-only, deterministic inventory for CMADaaS GRIB samples.

This module deliberately scans headers through reki's owned ecCodes boundary.
It never requests the ``values`` key, so an inventory is safe to retain when
the original operational GRIB files cannot be redistributed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import click
import eccodes
import yaml

from reki.readers.grib.config import GribParameterKey, get_parameter_index


SCHEMA_VERSION = "cedarkit.cmadaas-field-inventory/v1"
SYSTEMS = ("CMA-GFS", "CMA-MESO-3KM", "CMA-MESO-1KM", "CMA-TYM", "CMA-GEPS", "CMA-REPS")


def _get(message, key: str, default=None):
    import eccodes
    try:
        return eccodes.codes_get(message, key)
    except (eccodes.KeyValueNotFoundError, eccodes.WrongTypeError):
        return default


def _integer(message, key: str, default=0) -> int:
    value = _get(message, key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _number(message, key: str):
    value = _get(message, key)
    if value in (None, "undef", "missing"):
        return None
    try:
        return float(value) if isinstance(value, str) and "." in value else int(value)
    except (TypeError, ValueError):
        return None


def _text(message, key: str, default="unknown") -> str:
    value = _get(message, key, default)
    return default if value in (None, "undef") else str(value)


def _identity(message) -> dict[str, Any]:
    """Return the schema-defined identity without decoding grid values."""
    return {
        "edition": _integer(message, "edition"),
        "discipline": _integer(message, "discipline"),
        "parameter_category": _integer(message, "parameterCategory"),
        "parameter_number": _integer(message, "parameterNumber"),
        "tables_version": _integer(message, "tablesVersion"),
        "local_tables_version": _integer(message, "localTablesVersion"),
        "centre": _integer(message, "centre:int"),
        "subcentre": _integer(message, "subCentre"),
        "product_definition_template": _integer(message, "productDefinitionTemplateNumber"),
        "type_of_level": _text(message, "typeOfLevel"),
        "level": _number(message, "level"),
        "second_level": _number(message, "scaledValueOfSecondFixedSurface"),
        "step_type": _text(message, "stepType"),
        "start_step": _number(message, "startStep"),
        "end_step": _number(message, "endStep"),
        "time_range": _text(message, "stepRange", default="unknown"),
        "perturbation_number": _number(message, "perturbationNumber"),
        "ensemble_forecast_type": _number(message, "typeOfEnsembleForecast"),
        "short_name": _text(message, "shortName"),
        "name": _text(message, "name"),
        "units": _text(message, "units"),
    }


def _identity_key(identity: dict[str, Any]) -> str:
    """Canonical key excludes only file-specific ordinal/sample details."""
    return json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _query(record) -> dict[str, Any]:
    query = record.conditions.copy()
    query.update({"parameter": record.parameter_id, "level_type": record.conditions.get("typeOfLevel")})
    query.pop("typeOfLevel", None)
    if "time_range_hours" in query:
        query["time_range"] = query.pop("time_range_hours")
    return {key: value for key, value in sorted(query.items()) if value is not None}


def _resolve(identity: dict[str, Any], message):
    record = get_parameter_index().reverse(GribParameterKey(
        identity["discipline"], identity["parameter_category"], identity["parameter_number"],
        _integer(message, "typeOfFirstFixedSurface"), identity["level"],
        _integer(message, "typeOfSecondFixedSurface", 255),
        identity["second_level"], identity["step_type"], _hours(identity["start_step"], identity["end_step"]),
    ))
    if record is None or record.parameter_id is None or record.entry_parameter_id is None:
        return None
    return record


def _hours(start, end):
    if start is None or end is None:
        return None
    return max(0, end - start) or None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_inventory(manifest: dict[str, Any], root: str | Path) -> dict[str, Any]:
    """Scan ready/success manifest samples and return a canonical inventory."""
    from reki.readers.grib.eccodes._scan import iter_headers

    root = Path(root)
    messages = []
    inputs = []
    field_data: dict[str, dict[str, Any]] = {}
    for sample in sorted(manifest["samples"], key=lambda item: item["id"]):
        if sample["scan_status"] not in {"ready", "success"}:
            continue
        path = root / sample["path_label"]
        if not path.is_file():
            raise FileNotFoundError(f"ready sample {sample['id']!r} is missing: {sample['path_label']}")
        actual_size = path.stat().st_size
        if sample["size"] is not None and sample["size"] != actual_size:
            raise ValueError(f"sample {sample['id']!r} size does not match manifest")
        actual_sha = _sha256(path)
        if sample["sha256"] is not None and sample["sha256"] != actual_sha:
            raise ValueError(f"sample {sample['id']!r} sha256 does not match manifest")
        inputs.append({"sample_id": sample["id"], "sha256": actual_sha, "size": actual_size})
        for header in iter_headers(path, headers_only=True):
            identity = _identity(header.handle)
            message = {"sample_id": sample["id"], "message_index": header.ordinal,
                       "identity": identity}
            record = _resolve(identity, header.handle)
            if record is None:
                message.update({"resolution_status": "unresolved_grib", "reason": "no parameter registry record"})
            else:
                message.update({"resolution_status": "resolved", "parameter_id": record.parameter_id,
                                "entry_parameter_id": record.entry_parameter_id,
                                "field_query": _query(record)})
                field = field_data.setdefault(record.entry_parameter_id, {
                    "entry_parameter_id": record.entry_parameter_id, "parameter_ids": set(),
                    "systems": {}, "identities": set(), "external_names": dict(record.external_names),
                })
                field["parameter_ids"].add(record.parameter_id)
                field["identities"].add(_identity_key(identity))
                system = field["systems"].setdefault(sample["system"], {"present": True, "sample_ids": set(), "identity_count": 0, "_identities": set()})
                system["sample_ids"].add(sample["id"])
                system["_identities"].add(_identity_key(identity))
            messages.append(message)
    fields = []
    for entry_id, field in sorted(field_data.items()):
        systems = {}
        for system, item in sorted(field["systems"].items()):
            systems[system] = {"present": True, "sample_ids": sorted(item["sample_ids"]),
                               "identity_count": len(item["_identities"])}
        code = field["external_names"].get("cmadaas")
        cmadaas = ({"status": "already_confirmed", "code": code,
                    "reason": "pre-existing registry mapping; M-05 review pending"} if code else
                   {"status": "ambiguous", "reason": "CMADaaS semantic review pending (M-05)"})
        fields.append({"entry_parameter_id": entry_id, "parameter_ids": sorted(field["parameter_ids"]),
                       "systems": systems, "cmadaas": cmadaas})
    return {"schema_version": SCHEMA_VERSION, "tool_version": "reki.cmadaas-inventory/v1",
            "generated_from": [item["sample_id"] for item in inputs], "systems": list(SYSTEMS),
            "inputs": inputs, "messages": messages, "fields": fields}


@click.command("cmadaas-inventory")
@click.option("--manifest", "manifest_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--root", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Staging root containing manifest-relative GRIB files.")
@click.option("--output", "output_path", required=True, type=click.Path(dir_okay=False, path_type=Path))
def cmadaas_inventory(manifest_path: Path, root: Path, output_path: Path):
    """Write a deterministic, metadata-only CMADaaS GRIB inventory."""
    with manifest_path.open(encoding="utf-8") as stream:
        manifest = yaml.safe_load(stream)
    if manifest.get("schema_version") != "cedarkit.cmadaas-sample-manifest/v1":
        raise click.ClickException("unsupported sample manifest schema_version")
    try:
        result = build_inventory(manifest, root)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
