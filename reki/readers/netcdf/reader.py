"""NetCDF reader bound to the ``reader()`` dispatch."""

import os

import xarray as xr

from reki.readers import Reader

NETCDF4_MAGIC = b"\x89HDF"
NETCDF3_MAGIC = b"CDF"


class NetCDFReader(Reader):
    """Reader for NetCDF files (NetCDF3 / NetCDF4 / HDF5)."""

    def to_xarray(self, **kwargs) -> xr.Dataset:
        return xr.open_dataset(self.path, **kwargs)

    def to_pandas(self, **kwargs):
        return self.to_xarray().to_dataframe()

    def to_numpy(self, **kwargs):
        return self.to_xarray().to_array().to_numpy()


def READER(source, path, magic=None, deeper_check=False, **kwargs):
    """Claim files with the NetCDF3 (``CDF``) or NetCDF4/HDF5 magic.

    When the reader is explicitly named (``magic`` is None), the file
    is trusted to be NetCDF.
    """
    if os.path.isdir(path):
        return None
    if magic is None:
        return NetCDFReader(source, path, **kwargs)
    if magic.startswith(NETCDF4_MAGIC) or magic[:3] == NETCDF3_MAGIC:
        return NetCDFReader(source, path, **kwargs)
    return None
