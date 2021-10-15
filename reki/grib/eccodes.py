"""
Warnings
--------
This module is only for backward compatibility.

Please use ``reki.format.grib.eccodes`` instead.
"""
from reki.format.grib.eccodes import *

import warnings
warnings.warn("Please use `reki.format.grib.eccodes` instead.", FutureWarning)
