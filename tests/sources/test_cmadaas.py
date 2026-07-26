"""Tests for the CMADaaS source (low-level and high-level modes).

All MUSIC access is faked: the low-level mode receives a fake client,
and high-level retrieve functions are monkeypatched. No real MUSIC
service is involved.
"""

import sys

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from nuwe_cmadaas.music.data import (
    Array2D,
    FileInfo,
    FilesInfo,
    GridArray2D,
    MusicError,
    RequestInfo,
)

import reki
from reki.sources.cmadaas import CmadaasSource, CMADAASError
from reki.sources.file import FileSource
from reki.sources.url import UrlSource


class FakeClient:
    """Records calls and returns prepared responses by method name."""

    def __init__(self, **responses):
        self.responses = responses
        self.calls = []

    def __getattr__(self, name):
        if not name.startswith("callAPI_to_"):
            raise AttributeError(name)

        def call(interface_id, params):
            self.calls.append((name, interface_id, params))
            return self.responses[name]

        return call


def ok_grid():
    return GridArray2D(
        data=np.arange(6, dtype=float).reshape(2, 3),
        start_lat=0, end_lat=10, lat_count=2,
        start_lon=100, end_lon=120, lon_count=3,
        lats=[], lons=[], units="K", user_element_name="TEM",
        request=RequestInfo(error_code=0),
    )


class TestModeValidation:
    def test_interface_id_and_kind_are_mutually_exclusive(self):
        with pytest.raises(ValueError, match="exactly one"):
            CmadaasSource(interface_id="x", kind="model_grid")

    def test_one_of_interface_id_or_kind_is_required(self):
        with pytest.raises(ValueError, match="exactly one"):
            CmadaasSource()


class TestLowLevelMode:
    def test_grid_array_2d_end_to_end(self):
        client = FakeClient(callAPI_to_gridArray2D=ok_grid())

        field = reki.from_source(
            "cmadaas",
            interface_id="getNafpEleGrid",
            params={"dataCode": "NAFP_CMA_GFS_GMF", "fcstEle": "TEM"},
            client=client,
        ).to_xarray()

        assert isinstance(field, xr.DataArray)
        assert field.name == "TEM"
        assert field.shape == (2, 3)
        assert client.calls == [(
            "callAPI_to_gridArray2D",
            "getNafpEleGrid",
            {"dataCode": "NAFP_CMA_GFS_GMF", "fcstEle": "TEM"},
        )]

    def test_array_2d_end_to_end(self):
        response = Array2D(
            data=np.array([[1.0, 2.0]]),
            element_names=["TEM", "RHU"],
            request=RequestInfo(error_code=0),
        )
        client = FakeClient(callAPI_to_array2D=response)

        df = reki.from_source(
            "cmadaas", interface_id="getSurfEleGridByTime",
            params={}, client=client, return_type="array2D",
        ).to_pandas()

        assert isinstance(df, pd.DataFrame)
        assert df.columns.tolist() == ["TEM", "RHU"]

    def test_file_list_mutates_to_url_source(self):
        response = FilesInfo(
            files_info=[FileInfo(file_url="https://example.com/a.grib2")],
            request=RequestInfo(error_code=0),
        )
        client = FakeClient(callAPI_to_fileList=response)

        src = CmadaasSource(
            "getNafpFileList", {}, client=client, return_type="fileList",
        ).mutate()

        assert isinstance(src, UrlSource)
        assert src.url == "https://example.com/a.grib2"

    def test_save_as_file_mutates_to_file_source(self):
        response = FilesInfo(
            files_info=[FileInfo(save_path="/tmp/downloaded.grib2")],
            request=RequestInfo(error_code=0),
        )
        client = FakeClient(callAPI_to_saveAsFile=response)

        src = CmadaasSource(
            "getNafpFile", {}, client=client, return_type="saveAsFile",
        ).mutate()

        assert isinstance(src, FileSource)
        assert src.path == "/tmp/downloaded.grib2"

    def test_error_code_raises_cmadaas_error(self):
        response = GridArray2D(
            request=RequestInfo(error_code=-10001, error_message="boom"),
        )
        client = FakeClient(callAPI_to_gridArray2D=response)

        with pytest.raises(CMADAASError) as exc_info:
            CmadaasSource("x", {}, client=client).mutate()
        assert exc_info.value.code == -10001
        assert "boom" in str(exc_info.value)

    def test_unsupported_return_type(self):
        with pytest.raises(NotImplementedError, match="dataBlock"):
            CmadaasSource("x", {}, client=FakeClient(),
                          return_type="dataBlock").mutate()

    def test_unknown_return_type(self):
        with pytest.raises(ValueError, match="return_type"):
            CmadaasSource("x", {}, client=FakeClient(),
                          return_type="bogus").mutate()

    def test_missing_nuwe_cmadaas_hint(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "nuwe_cmadaas.music", None)
        with pytest.raises(ImportError, match=r"reki\[cmadaas\]"):
            CmadaasSource("x", {}, client=FakeClient()).mutate()


class TestHighLevelMode:
    def test_model_grid_end_to_end(self, monkeypatch):
        import nuwe_cmadaas.model

        expected = xr.DataArray(np.ones((2, 2)), dims=("latitude", "longitude"))
        received = {}

        def fake_retrieve(**kwargs):
            received.update(kwargs)
            return expected

        monkeypatch.setattr(
            nuwe_cmadaas.model, "retrieve_model_grid", fake_retrieve
        )

        field = reki.from_source(
            "cmadaas",
            kind="model_grid",
            data_code="NAFP_CMA_GFS_GMF",
            parameter="TEM",
            level=850,
        ).to_xarray()

        assert field is expected
        assert received["data_code"] == "NAFP_CMA_GFS_GMF"
        assert received["parameter"] == "TEM"
        assert received["level"] == 850
        assert received["config"] is None
        assert received["client"] is None

    def test_obs_station_returns_data_frame(self, monkeypatch):
        import nuwe_cmadaas.obs

        expected = pd.DataFrame({"TEM": [1.0]})
        monkeypatch.setattr(
            nuwe_cmadaas.obs, "retrieve_obs_station", lambda **kw: expected
        )

        df = reki.from_source(
            "cmadaas", kind="obs_station", data_code="SURF_CHN_MUL_HOR",
        ).to_pandas()

        assert df is expected

    def test_music_error_returned_raises_cmadaas_error(self, monkeypatch):
        import nuwe_cmadaas.model

        monkeypatch.setattr(
            nuwe_cmadaas.model,
            "retrieve_model_grid",
            lambda **kw: MusicError(code=1001, message="no data"),
        )

        # remote sources defer the request to first use, so the error
        # surfaces on access, not at from_source() time
        with pytest.raises(CMADAASError) as exc_info:
            reki.from_source(
                "cmadaas", kind="model_grid", data_code="X",
            ).to_xarray()
        assert exc_info.value.code == 1001
        assert "no data" in str(exc_info.value)

    def test_model_file_mutates_to_file_source(self, monkeypatch, tmp_path):
        import nuwe_cmadaas.model

        downloaded = tmp_path / "a.grib2"
        downloaded.touch()
        monkeypatch.setattr(
            nuwe_cmadaas.model, "download_model_file", lambda **kw: [downloaded]
        )

        src = CmadaasSource(
            kind="model_file", data_code="NAFP_CMA_GFS_GMF",
        ).mutate()

        assert isinstance(src, FileSource)
        assert src.path == str(downloaded)

    def test_multiple_files_not_supported(self, monkeypatch, tmp_path):
        import nuwe_cmadaas.model

        files = [tmp_path / "a.grib2", tmp_path / "b.grib2"]
        monkeypatch.setattr(
            nuwe_cmadaas.model, "download_model_file", lambda **kw: files
        )

        with pytest.raises(NotImplementedError, match="2 files"):
            CmadaasSource(kind="model_file", data_code="X").mutate()

    def test_unknown_kind(self):
        with pytest.raises(ValueError, match="kind"):
            CmadaasSource(kind="bogus").mutate()

    def test_client_and_config_forwarded(self, monkeypatch):
        import nuwe_cmadaas.model

        received = {}
        monkeypatch.setattr(
            nuwe_cmadaas.model,
            "retrieve_model_grid",
            lambda **kw: received.update(kw) or xr.DataArray([1.0]),
        )
        client = FakeClient()

        reki.from_source(
            "cmadaas", kind="model_grid", data_code="X",
            config="conf.yaml", client=client,
        ).to_xarray()

        assert received["config"] == "conf.yaml"
        assert received["client"] is client
