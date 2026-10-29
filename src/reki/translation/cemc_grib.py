"""Bounded CEMC v12.6 producer encodings reviewed in stage 1.1 I03/I06.

The original paraNum.h and setGrib2Section4Parameters define these codes.
The complete writer sets centre 38, master table 4 and local table 1.
These slices cover operational deterministic instantaneous messages only.
It supplies no default parameter IDs, product scope, members or statistics.
See doc/2026-10-13-stage1.1-query-reki/evidence/grib-util-v12.6 in the workspace.
"""

# (discipline, category, number): allowed first fixed surface. The eight local
# codes have matching typed business headers; soil encodings also have binary
# writer/reader evidence. Other codes and template families remain unsupported.
SURFACES = {
    (0, 16, 224): 1,  # 281 CDBZ
    (0, 16, 225): 100,  # 282 DBZ
    (0, 7, 224): 1,  # 329 DCAPE
    (0, 19, 224): 1,  # 245 FOGH
    (0, 3, 225): 1,  # 322 HT0
    (0, 3, 226): 1,  # 323 HT2
    (0, 3, 228): 1,  # 91 ZNT
    (0, 16, 226): 1,  # 284 DBZMAXH
    (0, 0, 0): 106,  # 85 ST, ordinary producer status
    (0, 1, 0): 106,  # 144 SW, ordinary producer status
}


def applies(meta):
    """Match an exact finite producer profile, not any local-table message."""
    context = tuple(
        meta.get(k)
        for k in (
            "edition",
            "centre",
            "subCentre",
            "tablesVersion",
            "localTablesVersion",
            "productionStatusOfProcessedData",
            "productDefinitionTemplateNumber",
        )
    )
    code = tuple(
        meta.get(k) for k in ("discipline", "parameterCategory", "parameterNumber")
    )
    first = SURFACES.get(code)
    return (
        all(type(v) is int for v in context + code)
        and (
            context == (2, 38, 0, 4, 1, 0, 0)
            # Original GFS soil messages also use local table 0. Only these
            # exact soil encodings inherit the reviewed producer interpretation.
            or (context == (2, 38, 0, 4, 0, 0, 0) and code in {(0, 0, 0), (0, 1, 0)})
        )
        and first is not None
        and meta.get("typeOfFirstFixedSurface") == first
        and meta.get("typeOfSecondFixedSurface") == (106 if first == 106 else 255)
    )


def value_unit(meta):
    """The soil-water encoding overloads the WMO specific-humidity code.

    ecCodes' derived SPFH unit is not producer evidence for this exact encoding.
    The raw ecCodes literal remains in FieldReference.metadata.native_fields.
    All other units continue through the normal native/mapping consistency check.
    """
    if applies(meta) and meta.get("parameterCategory") == 1:
        return "m3/m3"
    return None
