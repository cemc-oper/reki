"""Desktop tests for the CMADaaS source against the real MUSIC service.

These tests use the *remote* MUSIC retrieval path (the ``cmadaas``
source), not the mounted-disk path (``local`` source with
``data_class="cmadaas"`` configs). They require:

- ``nuwe-cmadaas`` installed (the ``cmadaas`` extra), and
- a valid ``~/.config/cedarkit.yaml`` with MUSIC credentials, and
- network access to the MUSIC service.

All tests are skipped when the service is unreachable or the requested
operational data is not available.
"""

from pathlib import Path

import pandas as pd
import pytest
import xarray as xr

import reki
from reki.sources.cmadaas import CMADAASError

DATA_CODE = "NAFP_FOR_FTM_GRAPES_GFS_25KM_GLB"
INTERFACE_ID = "getNafpEleGridInRectByTimeAndLevelAndValidtime"

# a small rect around Beijing to keep the download tiny
REGION = {"minLat": "39", "maxLat": "41", "minLon": "115", "maxLon": "117"}


def _params(start_time: pd.Timestamp) -> dict:
    return {
        "dataCode": DATA_CODE,
        "fcstEle": "TEM",
        "time": start_time.strftime("%Y%m%d%H%M%S"),
        "validTime": "24",
        "levelType": "100",
        "fcstLevel": "850",
        **REGION,
    }


@pytest.fixture(scope="module")
def start_time() -> pd.Timestamp:
    """Yesterday's 00Z run; operational data should be available."""
    return pd.Timestamp.now("UTC").floor(freq="D") - pd.Timedelta(days=1)


@pytest.fixture(scope="module")
def music_available(start_time):
    """Skip the whole module when the MUSIC service is not usable."""
    if not Path("~/.config/cedarkit.yaml").expanduser().exists():
        pytest.skip("CMADaaS config ~/.config/cedarkit.yaml not found")
    try:
        field = reki.from_source(
            "cmadaas",
            interface_id=INTERFACE_ID,
            params=_params(start_time),
        ).to_xarray()
    except CMADAASError as e:
        pytest.skip(f"MUSIC service or data not available: {e}")
    except Exception as e:  # connection errors, auth errors, ...
        pytest.skip(f"MUSIC service not reachable: {e}")
    return field


class TestLowLevelMode:
    def test_grid_array_2d(self, music_available):
        field = music_available
        assert isinstance(field, xr.DataArray)
        assert field.sizes["latitude"] > 1
        assert field.sizes["longitude"] > 1
        # the cmadaas reader builds coordinates itself (the upstream
        # GridArray2D.to_xarray mixes up lats/lons)
        assert 38.5 <= float(field.latitude.min()) <= 39.5
        assert 40.5 <= float(field.latitude.max()) <= 41.5
        assert 114.5 <= float(field.longitude.min()) <= 115.5
        assert 116.5 <= float(field.longitude.max()) <= 117.5

    def test_bad_data_code_raises_cmadaas_error(
            self, music_available, start_time
    ):
        params = {**_params(start_time), "dataCode": "NO_SUCH_DATA_CODE"}
        # the request is deferred to first use (remote source)
        with pytest.raises(CMADAASError):
            reki.from_source(
                "cmadaas", interface_id=INTERFACE_ID, params=params,
            ).to_xarray()


class TestHighLevelMode:
    def test_model_grid(self, music_available, start_time):
        field = reki.from_source(
            "cmadaas",
            kind="model_grid",
            data_code=DATA_CODE,
            parameter="TEM",
            start_time=start_time,
            forecast_time="24h",
            level_type=100,
            level=850,
            region={
                "type": "rect",
                "start_latitude": 39, "end_latitude": 41,
                "start_longitude": 115, "end_longitude": 117,
            },
        ).to_xarray()
        assert isinstance(field, xr.DataArray)
        assert field.sizes["latitude"] > 1
        assert field.sizes["longitude"] > 1
