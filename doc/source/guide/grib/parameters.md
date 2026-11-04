# Select GRIB parameters

Use the ecCodes shortName or pass a native key dictionary to the legacy message reader. A key such as `typeOfFirstFixedSurface:int` requests its integer representation. With the public Query API, use `native.grib` and pass the integer code directly. GRIB centre, table, parameter, template and surface keys can disambiguate records that share a short name.
