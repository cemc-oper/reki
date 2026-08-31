import hashlib
import json

import eccodes
import yaml
from click.testing import CliRunner

from reki.cli import cli


SYSTEMS = ("CMA-GFS", "CMA-MESO-3KM", "CMA-MESO-1KM", "CMA-TYM", "CMA-GEPS", "CMA-REPS")


def _write_grib(path):
    with path.open("wb") as output:
        for level in (850, 850):
            message = eccodes.codes_grib_new_from_samples("GRIB2")
            try:
                eccodes.codes_set(message, "shortName", "t")
                eccodes.codes_set(message, "typeOfLevel", "isobaricInhPa")
                eccodes.codes_set(message, "level", level)
                eccodes.codes_write(message, output)
            finally:
                eccodes.codes_release(message)


def _manifest(path, relative_path, digest, size):
    samples = []
    for position, system in enumerate(SYSTEMS):
        samples.append({
            "id": f"sample-{position}", "system": system, "dataset_id": system.lower(),
            "product": "grib2/orig", "start_time": "2026-08-30T00:00:00Z",
            "forecast_time": "PT0H", "member": None, "path_label": relative_path,
            "size": size if position == 0 else None, "sha256": digest if position == 0 else None,
            "scan_status": "ready" if position == 0 else "input_pending",
        })
    path.write_text(yaml.safe_dump({
        "schema_version": "cedarkit.cmadaas-sample-manifest/v1",
        "staging_root_env": "CEDARKIT_CMADAAS_GRIB_ROOT",
        "path_privacy": "relative_to_staging_root", "samples": samples,
        "stability_check": {"status": "pending_inputs", "rule": "equal_identity_sets_then_extend_until_two_successive_additions_have_zero_new_identities"},
    }), encoding="utf-8")


def test_cmadaas_inventory_is_metadata_only_deterministic_and_deduplicated(tmp_path):
    grib = tmp_path / "sample.grib2"
    _write_grib(grib)
    digest = hashlib.sha256(grib.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.yaml"
    _manifest(manifest, grib.name, digest, grib.stat().st_size)
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    runner = CliRunner()

    for output in (first, second):
        result = runner.invoke(cli, ["cmadaas-inventory", "--manifest", str(manifest),
                                     "--root", str(tmp_path), "--output", str(output)])
        assert result.exit_code == 0, result.output
    assert first.read_bytes() == second.read_bytes()

    inventory = json.loads(first.read_text(encoding="utf-8"))
    assert inventory["generated_from"] == ["sample-0"]
    assert len(inventory["messages"]) == 2
    assert inventory["messages"][0]["resolution_status"] == "resolved"
    assert len(inventory["fields"]) == 1
    assert inventory["fields"][0]["systems"]["CMA-GFS"]["identity_count"] == 1


def test_cmadaas_inventory_rejects_a_ready_file_with_wrong_digest(tmp_path):
    grib = tmp_path / "sample.grib2"
    _write_grib(grib)
    manifest = tmp_path / "manifest.yaml"
    _manifest(manifest, grib.name, "0" * 64, grib.stat().st_size)
    result = CliRunner().invoke(cli, ["cmadaas-inventory", "--manifest", str(manifest),
                                      "--root", str(tmp_path), "--output", str(tmp_path / "out.json")])
    assert result.exit_code != 0
    assert "sha256 does not match manifest" in result.output
