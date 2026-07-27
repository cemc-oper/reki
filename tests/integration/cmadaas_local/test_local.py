"""Tests for LocalSource against the mounted CMADaaS disk tree (/CMADAAS)."""

import pandas as pd
import pytest
import xarray as xr

import reki
from reki.data_finder import find_local_file
from reki.readers.grib import GribReader
from reki.sources.file import FileSource
from reki.sources.local import LocalSource


@pytest.fixture
def storage_base():
    return "/CMADAAS"


@pytest.fixture
def query_args(storage_base, last_two_day, forecast_time_24h):
    return dict(
        data_class="cmadaas",
        data_type="cma_gfs_gmf/grib2/orig",
        start_time=last_two_day,
        forecast_time=forecast_time_24h,
        storage_base=storage_base,
    )


class TestResolvePath:
    def test_resolve_path_matches_find_local_file(self, query_args):
        src = LocalSource(**query_args)
        assert src.resolve_path() == find_local_file(**query_args)

    def test_resolve_path_not_found_returns_none(self, storage_base):
        src = LocalSource(
            "cma_gfs_gmf/grib2/orig",
            start_time="2000010100",
            forecast_time="24h",
            data_class="cmadaas",
            storage_base=storage_base,
        )
        assert src.resolve_path() is None

    def test_unknown_data_type_raises_value_error(self):
        src = LocalSource(
            "no/such/data_type", start_time="2023122000",
        )
        with pytest.raises(ValueError, match="data type is not found"):
            src.resolve_path()

    def test_string_times_are_parsed(self, query_args):
        src = LocalSource(
            **{
                **query_args,
                "start_time": query_args["start_time"].strftime("%Y%m%d%H"),
                "forecast_time": "24h",
            }
        )
        assert src.resolve_path() == find_local_file(**query_args)


class TestMutate:
    def test_mutate_returns_file_source(self, query_args):
        src = LocalSource(**query_args)
        file_src = src.mutate()
        assert isinstance(file_src, FileSource)
        assert file_src.path == str(src.resolve_path())

    def test_mutate_not_found_raises(self, storage_base):
        src = LocalSource(
            "cma_gfs_gmf/grib2/orig",
            start_time="2000010100",
            forecast_time="24h",
            data_class="cmadaas",
            storage_base=storage_base,
        )
        with pytest.raises(FileNotFoundError, match="Data not found"):
            src.mutate()


class TestFromSourceLocal:
    def test_from_source_local_dispatches_to_reader(self, query_args):
        query_args = dict(query_args)
        data_type = query_args.pop("data_type")
        start_time = query_args.pop("start_time")
        forecast_time = query_args.pop("forecast_time")
        ds = reki.from_source(
            "local", data_type,
            start_time=start_time, forecast_time=forecast_time, **query_args,
        )
        assert isinstance(ds, GribReader)

    def test_from_source_local_full_chain(self, query_args):
        query_args = dict(query_args)
        data_type = query_args.pop("data_type")
        start_time = query_args.pop("start_time")
        forecast_time = query_args.pop("forecast_time")
        data = reki.from_source(
            "local", data_type,
            start_time=start_time, forecast_time=forecast_time, **query_args,
        ).sel(
            parameter="2t", level_type="heightAboveGround", level=2
        ).first().to_xarray()
        assert isinstance(data, xr.DataArray)
        assert data.name == "2t"

    def test_from_source_local_not_found(self, storage_base):
        with pytest.raises(FileNotFoundError):
            reki.from_source(
                "local", "cma_gfs_gmf/grib2/orig",
                start_time="2000010100",
                forecast_time="24h",
                data_class="cmadaas",
                storage_base=storage_base,
            )
