"""Bounded CEMC v12.6 producer encodings reviewed in stage 1.1 I03/I06.

The original paraNum.h and setGrib2Section4Parameters define these codes.
The complete writer sets centre 38, master table 4 and local table 1.
These slices cover reviewed operational instantaneous producer encodings.
Additional exact GFS surface and TOA clear-sky longwave energy encodings are checked
separately; its declared unit belongs to the finite product mapping.
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


def member_instantaneous(meta):
    """Recognize only the reviewed CDBZ/DCAPE local member encodings.

    Original cases281/329 and current GEPS/REPS headers establish these
    surface PDT1 forms. Product mappings retain their exact phase/role
    conditions; grib.member checks the product's complete joint numbering.
    This supplies no unit, member domain or ensemble-statistic identity.
    """
    keys = (
        "edition",
        "centre",
        "subCentre",
        "tablesVersion",
        "localTablesVersion",
        "productionStatusOfProcessedData",
        "productDefinitionTemplateNumber",
        "discipline",
        "parameterCategory",
        "parameterNumber",
        "typeOfFirstFixedSurface",
        "typeOfSecondFixedSurface",
    )
    native = tuple(meta.get(k) for k in keys)
    return all(type(v) is int for v in native) and native in {
        (2, 38, 0, 4, 1, 0, 1, 0, 16, 224, 1, 255),
        (2, 38, 0, 4, 1, 0, 1, 0, 7, 224, 1, 255),
    }


def composite_reflectivity_maximum(meta):
    """Recognize the CEMC surface composite maximum encoding."""
    expected = {
        "edition": 2,
        "centre": 38,
        "subCentre": 0,
        "tablesVersion": 4,
        "localTablesVersion": 1,
        "productionStatusOfProcessedData": 0,
        "productDefinitionTemplateNumber": 8,
        "typeOfProcessedData": 1,
        "typeOfGeneratingProcess": 2,
        "significanceOfReferenceTime": 1,
        "discipline": 0,
        "parameterCategory": 16,
        "parameterNumber": 224,
        "typeOfFirstFixedSurface": 1,
        "typeOfSecondFixedSurface": 255,
        "typeOfStatisticalProcessing": 2,
    }
    return all(
        type(meta.get(key)) is int and meta[key] == value
        for key, value in expected.items()
    )


def terrain_source_unit(meta, *, context, parameter_id, source_unit):
    """Resolve reviewed current ORIG ZS decoder views from producer evidence.

    Original case7 and reviewed model declarations state Gpm; GEPS has its
    own explicit business Gpm declaration and reviewed member context.
    ecCodes' generic geopotential-height concept says gpm, while its surface
    orography concept selects m. Neither string is stored in the message.
    This scoped interpretation changes no values and defines no global m/Gpm
    equivalence. Native queries and other product contexts keep their unit view.
    """
    if (
        parameter_id != "cedarkit.zs"
        or source_unit != "Gpm"
        or context.get("dataset")
        not in {"cma_gfs_gmf", "cma_meso_1km", "cma_meso_3km", "cma_tym", "cma_geps"}
        or any(
            context.get(key) != value
            for key, value in {
                "product": "orig",
                "product_version": "current",
            }.items()
        )
        or meta.get("units") != "m"
        or meta.get("parameterUnits") != "gpm"
    ):
        return None
    keys = (
        "edition",
        "centre",
        "subCentre",
        "tablesVersion",
        "localTablesVersion",
        "productionStatusOfProcessedData",
        "productDefinitionTemplateNumber",
        "discipline",
        "parameterCategory",
        "parameterNumber",
        "typeOfFirstFixedSurface",
        "typeOfSecondFixedSurface",
    )
    native = tuple(meta.get(key) for key in keys)
    phase = tuple(
        meta.get(key)
        for key in (
            "typeOfProcessedData",
            "typeOfGeneratingProcess",
            "significanceOfReferenceTime",
        )
    )
    if all(type(value) is int for value in native + phase) and (
        (
            context.get("dataset") != "cma_geps"
            and native == (2, 38, 0, 4, 0, 0, 0, 0, 3, 5, 1, 255)
            and phase in {(0, 0, 0), (1, 2, 1)}
        )
        or (
            context.get("dataset") == "cma_geps"
            and native == (2, 38, 0, 4, 0, 0, 1, 0, 3, 5, 1, 255)
            and phase in {(3, 4, 0), (3, 4, 1), (4, 4, 0), (4, 4, 1)}
        )
    ):
        return "Gpm"
    return None


def sweat_source_unit(meta, *, context, parameter_id, source_unit):
    """Interpret the explicitly unitless GFS SWEAT numeric score, without scaling.

    Business table0 row49 says no unit (无), independently of original [-].
    Numeric is an ecCodes view; it is not a shared alias for dimensionless1.
    The score is neither a probability nor a categorical code-table field.
    """
    if (
        parameter_id != "cedarkit.sweatidx"
        or source_unit != "1"
        or any(
            context.get(k) != v
            for k, v in {
                "dataset": "cma_gfs_gmf",
                "product": "orig",
                "product_version": "current",
            }.items()
        )
        or meta.get("units") != "Numeric"
        or meta.get("parameterUnits") != "Numeric"
    ):
        return None
    keys = (
        "edition",
        "centre",
        "subCentre",
        "tablesVersion",
        "localTablesVersion",
        "productionStatusOfProcessedData",
        "productDefinitionTemplateNumber",
        "discipline",
        "parameterCategory",
        "parameterNumber",
        "typeOfFirstFixedSurface",
        "typeOfSecondFixedSurface",
    )
    native = tuple(meta.get(k) for k in keys)
    phase = tuple(
        meta.get(k)
        for k in (
            "typeOfProcessedData",
            "typeOfGeneratingProcess",
            "significanceOfReferenceTime",
        )
    )
    if (
        all(type(v) is int for v in native + phase)
        and native == (2, 38, 0, 4, 0, 0, 0, 0, 7, 5, 1, 255)
        and phase in {(0, 0, 0), (1, 2, 1)}
    ):
        return "1"
    return None


def is_gfs_clear_sky_longwave_energy(meta):
    """Recognize the reviewed local-use0/5/224 written with local table1.

    Original writer element108 and business declarations identify the surface
    and top-of-atmosphere forms of this exact
    producer encoding. Do not relax local-table checks for other codes, layers,
    templates or producers. Time/statistic consistency is checked by its rules;
    this function supplies neither a unit nor a parameter identity.
    """
    keys = (
        "edition",
        "centre",
        "subCentre",
        "tablesVersion",
        "localTablesVersion",
        "productionStatusOfProcessedData",
        "productDefinitionTemplateNumber",
        "discipline",
        "parameterCategory",
        "parameterNumber",
        "typeOfFirstFixedSurface",
        "typeOfSecondFixedSurface",
    )
    context = tuple(meta.get(k) for k in keys)
    phase = tuple(
        meta.get(k)
        for k in (
            "typeOfProcessedData",
            "typeOfGeneratingProcess",
            "significanceOfReferenceTime",
        )
    )
    return (
        all(type(v) is int for v in context + phase)
        and context in {
            (2, 38, 0, 4, 1, 0, 8, 0, 5, 224, 1, 255),
            (2, 38, 0, 4, 1, 0, 8, 0, 5, 224, 8, 255),
        }
        and phase in {(0, 0, 0), (1, 2, 1)}
    )
