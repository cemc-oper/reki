"""
GRIB2 要素注册表查询接口。

数据文件为同目录 ``param_registry.yaml``，约束规范见 ``param_registry_spec.md``。
匹配语义（规范 §5）：

1. 变体命中：``when`` 中每个键都等于实际值；缺省键 = 通配；实际值缺失不命中。
2. 最具体匹配：命中变体中 ``when`` 键数最多者胜出，并列时 ``params`` 中靠后者胜出。
3. 无变体命中时回退到条目级通用名 ``name``。
4. ``wgrib2_name`` 层次无关，由 :func:`find_wgrib2_name` 单独返回。
"""

from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Optional, Union

import yaml

#: ``when`` 条件键白名单（规范 §3.4）
WHEN_KEYS = (
    "first_level_type",
    "first_level",
    "second_level_type",
    "second_level",
    "stepType",
    "time_range_hours",
)


@cache
def get_param_registry() -> dict[tuple[int, int, int], dict]:
    """
    Load the GRIB2 parameter registry from ``param_registry.yaml``.

    Returns
    -------
    dict
        mapping ``(discipline, category, number)`` to the registry entry.
    """
    ref = files("reki.readers.grib.config").joinpath("param_registry.yaml")
    with ref.open("r", encoding="utf-8") as f:
        document = yaml.safe_load(f)
    # T2-02 publishes the versioned v2 document.  Keep accepting the old
    # top-level list until the T2-03 resolver removes this compatibility path.
    entries = document["entries"] if isinstance(document, dict) else document
    return {
        (entry["key"]["discipline"], entry["key"]["category"], entry["key"]["number"]): entry
        for entry in entries
    }


@dataclass
class GribParameterKey:
    discipline: int
    category: int
    number: int
    first_level_type: Optional[int] = None
    first_level: Optional[float] = None
    second_level_type: Optional[int] = None
    second_level: Optional[float] = None
    stepType: Optional[str] = None
    time_range_hours: Optional[float] = None


def check_value(expected_value, actual_value) -> bool:
    if expected_value is None:
        return True
    if actual_value is None or actual_value == "undef":
        return False
    return expected_value == actual_value


def find_short_name(discipline: int, category: int, number: int) -> Optional[str]:
    """
    Get parameter's generic name from the registry.

    The generic name prefers the CEMC parameter name; parameters without a
    CEMC name use the WGRIB2 short name.

    Parameters
    ----------
    discipline
        GRIB key discipline
    category
        GRIB key parameterCategory
    number
        GRIB key parameterNumber

    Returns
    -------
    Optional[str]
        generic name if found, or None if not.
    """
    entry = get_param_registry().get((discipline, category, number))
    if entry is None:
        return None
    return entry["name"]


def find_wgrib2_name(param_key: GribParameterKey) -> Optional[str]:
    """
    Get the WGRIB2 short name of a parameter, or None if not defined.
    """
    entry = get_param_registry().get(
        (param_key.discipline, param_key.category, param_key.number)
    )
    if entry is None:
        return None
    return entry.get("wgrib2_name")


def _variant_matches(when: dict, param_key: GribParameterKey) -> bool:
    for name, expected in when.items():
        if not check_value(expected, getattr(param_key, name)):
            return False
    return True


def find_cemc_name(param_key: GribParameterKey) -> Optional[str]:
    """
    Get the CEMC name of a parameter.

    The most specific matching variant (most ``when`` keys) wins; ties are
    resolved by the later variant in ``params``. When no variant matches,
    falls back to the entry's generic name. Returns None for unknown
    parameters.
    """
    entry = get_param_registry().get(
        (param_key.discipline, param_key.category, param_key.number)
    )
    if entry is None:
        return None

    best_name = None
    best_score = -1
    for variant in entry.get("params", []):
        when = variant["when"]
        if len(when) < best_score:
            continue
        if _variant_matches(when, param_key):
            best_name = variant["name"]
            best_score = len(when)

    if best_name is not None:
        return best_name
    return entry["name"]


def find_parameter_record(parameter: str) -> Optional[dict]:
    """
    Reverse lookup: find the registry record for a name.

    Search order: ``wgrib2_name`` of every entry, then variant names and
    aliases, then entry generic names. Returns a dict with the entry key
    and the matched record (variant or entry), or None.
    """
    registry = get_param_registry()
    for key, entry in registry.items():
        if entry.get("wgrib2_name") == parameter:
            return {"key": key, "record": entry, "source": "wgrib2"}
    for key, entry in registry.items():
        for variant in entry.get("params", []):
            if variant["name"] == parameter or parameter in variant.get("aliases", []):
                return {"key": key, "record": variant, "source": "cemc"}
    for key, entry in registry.items():
        if entry["name"] == parameter or parameter in entry.get("aliases", []):
            return {"key": key, "record": entry, "source": "cemc"}
    return None
