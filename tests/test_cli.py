import json

import eccodes
from click.testing import CliRunner

from reki.cli import EXIT_NO_MATCH, cli
from reki.diagnostics import collect_io_metrics


def _write(path):
    with path.open("wb") as output:
        for level in (850, 500):
            message = eccodes.codes_grib_new_from_samples("GRIB2")
            try:
                eccodes.codes_set(message, "shortName", "t")
                eccodes.codes_set(message, "typeOfLevel", "isobaricInhPa")
                eccodes.codes_set(message, "level", level)
                eccodes.codes_write(message, output)
            finally:
                eccodes.codes_release(message)


def test_inspect_and_ls_json_use_public_metadata_api(tmp_path):
    path = tmp_path / "fields.grib"
    _write(path)
    runner = CliRunner()

    with collect_io_metrics() as metrics:
        result = runner.invoke(cli, ["inspect", str(path), "--no-index", "--json"])
        assert result.exit_code == 0, result.output
        inspect = json.loads(result.output)
        assert inspect["summary"]["field_count"] == 2
        assert inspect["capabilities"]["metadata"] is True
        assert metrics.snapshot()["value_decode_count"] == 0

    result = runner.invoke(cli, [
        "ls", str(path), "--parameter", "t", "--level-type", "pl", "--level", "850",
        "--keys", "index,level", "--no-index", "--json",
    ])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == [{"index": 0, "level": 850.0}]


def test_query_is_bounded_and_has_a_no_match_exit_code(tmp_path):
    path = tmp_path / "fields.grib"
    _write(path)
    runner = CliRunner()

    result = runner.invoke(cli, [
        "query", str(path), "--level", "100", "--no-index", "--json",
    ])
    assert result.exit_code == EXIT_NO_MATCH
    assert json.loads(result.output) == []

    duplicate = runner.invoke(cli, ["ls", str(path), "--keys", "level,level"])
    assert duplicate.exit_code == 2
    conflict = runner.invoke(cli, ["inspect", str(path), "--use-index", "--refresh-index"])
    assert conflict.exit_code == 2


def test_indexing_requires_an_explicit_cli_opt_in(tmp_path):
    path = tmp_path / "fields.grib"
    index_dir = tmp_path / "indexes"
    _write(path)
    runner = CliRunner()

    default = runner.invoke(cli, ["inspect", str(path), "--index-dir", str(index_dir), "--json"])
    assert default.exit_code == 0, default.output
    assert not index_dir.exists()

    enabled = runner.invoke(cli, ["inspect", str(path), "--use-index", "--index-dir", str(index_dir), "--json"])
    assert enabled.exit_code == 0, enabled.output
    assert list(index_dir.glob("*.sqlite"))


def test_catalog_commands_remain_available():
    result = CliRunner().invoke(cli, ["catalog", "--help"])
    assert result.exit_code == 0
    assert "resolve" in result.output
