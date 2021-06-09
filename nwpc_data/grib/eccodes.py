"""
Warnings
--------
This module is only for backward compatibility.

Please use ``nwpc_data.format.grib.eccodes`` instead.
"""
from nwpc_data.format.grib.eccodes import *

import warnings
warnings.warn("Please use `nwpc_data.format.grib.eccodes` instead.", FutureWarning)
