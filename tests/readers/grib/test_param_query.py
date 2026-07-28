"""
Query-semantics tests for the GRIB2 parameter registry (spec §5).

Covers: most-specific match, tie handling, generic-name fallback,
time_range_hours discrimination, wgrib2 name lookup, reverse lookup
(including aliases) and convert_parameter.
"""

import pytest

from reki.readers.grib.config import (
    GribParameterKey,
    find_short_name,
    find_wgrib2_name,
    find_cemc_name,
    find_parameter_record,
)
from reki.readers.grib.common._parameter import convert_parameter


def key(number, category=0, discipline=0, **kwargs) -> GribParameterKey:
    return GribParameterKey(discipline=discipline, category=category, number=number, **kwargs)


class TestFindShortName:
    def test_cemc_generic_name_preferred(self):
        # CEMC 通用名优先于 wgrib2 名
        assert find_short_name(0, 0, 0) == "t"

    def test_wgrib2_only_parameter(self):
        assert find_short_name(0, 0, 17) == "SKINT"

    def test_unknown(self):
        assert find_short_name(0, 255, 255) is None


class TestFindWgrib2Name:
    def test_found(self):
        assert find_wgrib2_name(key(0)) == "TMP"

    def test_not_defined(self):
        assert find_wgrib2_name(key(225)) is None

    def test_unknown_parameter(self):
        assert find_wgrib2_name(key(255, category=255)) is None


class TestFindCemcName:
    def test_generic_fallback_without_conditions(self):
        # 无条件行已提升为通用名：无条件的温度场回退到 t
        assert find_cemc_name(key(0)) == "t"

    def test_generic_fallback_for_unmatched_conditions(self):
        # 混合层次上的 (0,0,0)：无变体命中，回退通用名
        assert find_cemc_name(key(0, first_level_type=119, first_level=1)) == "t"

    def test_most_specific_match(self):
        # 土壤层：st(0-10)（4 键）比 st（1 键）更具体
        assert find_cemc_name(key(
            0, first_level_type=106, first_level=0,
            second_level_type=106, second_level=0.1,
        )) == "st(0-10)"

    def test_less_specific_variant(self):
        assert find_cemc_name(key(0, first_level_type=106, first_level=0.5)) == "st"

    def test_step_type_condition(self):
        assert find_cemc_name(key(
            4, first_level_type=103, first_level=2, stepType="max",
        )) == "mx2t"

    def test_missing_actual_value_does_not_match(self):
        # 调用方未提供 stepType：mx2t 变体（带 stepType=max 条件）不命中，
        # 回退到条目通用名（本身也是 mx2t，M2 case 2）
        assert find_cemc_name(key(4, first_level_type=103, first_level=2)) == "mx2t"

    def test_time_range_hours_discriminates(self):
        base = dict(first_level_type=103, first_level=10, stepType="max")
        assert find_cemc_name(key(2, category=2, **base)) == "u10mmax"
        assert find_cemc_name(key(2, category=2, time_range_hours=1, **base)) == "u10mmax#1"
        assert find_cemc_name(key(2, category=2, time_range_hours=3, **base)) == "u10mmax#3"

    def test_synthesized_base_variant(self):
        # cdbzmax/dbzmax 基名变体由 M7b 合成
        assert find_cemc_name(key(224, category=16, stepType="max")) == "cdbzmax"
        assert find_cemc_name(
            key(224, category=16, stepType="max", time_range_hours=3)
        ) == "cdbzmax#3"

    def test_unknown_parameter(self):
        assert find_cemc_name(key(255, category=255)) is None


class TestFindParameterRecord:
    def test_wgrib2_name(self):
        found = find_parameter_record("TMP")
        assert found["key"] == (0, 0, 0)
        assert found["source"] == "wgrib2"

    def test_variant_name(self):
        found = find_parameter_record("t2m")
        assert found["key"] == (0, 0, 0)
        assert found["record"]["name"] == "t2m"

    def test_variant_alias(self):
        found = find_parameter_record("tmax2m")
        assert found["record"]["name"] == "mx2t"

    def test_entry_level_alias(self):
        # 被提升行的别名保留在条目级
        found = find_parameter_record("cr")
        assert found["key"] == (0, 16, 224)
        assert found["record"]["name"] == "cdbz"

    def test_generic_name_with_conditional_variant(self):
        # M2 case 2：ps 既是通用名又是带条件的变体，反查命中变体
        found = find_parameter_record("ps")
        assert found["record"].get("when") == {"first_level_type": 1}

    def test_unknown(self):
        assert find_parameter_record("unknown") is None


class TestConvertParameter:
    def test_wgrib2_name(self):
        assert convert_parameter("TMP") == {
            "discipline": 0, "parameterCategory": 0, "parameterNumber": 0,
        }

    def test_cemc_variant(self):
        assert convert_parameter("t2m") == {
            "discipline": 0.0, "parameterCategory": 0.0, "parameterNumber": 0.0,
            "typeOfLevel": "heightAboveGround", "level": 2, "first_level": 2.0,
        }

    def test_cemc_alias(self):
        assert convert_parameter("psfc") == {
            "discipline": 0.0, "parameterCategory": 3.0, "parameterNumber": 0.0,
            "typeOfLevel": "surface",
        }

    def test_step_type(self):
        result = convert_parameter("mx2t")
        assert result["stepType"] == "max"

    def test_unknown_returns_input(self):
        assert convert_parameter("unknown") == "unknown"

    def test_dict_passthrough(self):
        assert convert_parameter({"parameterCategory": 0}) == {"parameterCategory": 0}
