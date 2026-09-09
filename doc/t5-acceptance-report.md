# T5 验收报告

日期：2026-09-09

固定数据：`ecmwf_ifs` release `v2026.9.1`（core、time、ensemble、layers、global）
范围：T5-1 自动门禁，以及任务方案第 10 节的 12 项真实 GRIB 工作流。

## 可复验环境

在 `repo/reki` 中执行；所有下载文件进入被忽略的 `doc/.cache/`，所有示例 index 使用
该目录或 `TemporaryDirectory`，不会写入用户级缓存：

```bash
UV_CACHE_DIR=/tmp/reki-uv-cache uv pip install -r doc/requirements.txt
UV_CACHE_DIR=/tmp/reki-uv-cache uv run --no-sync make -C doc data
UV_CACHE_DIR=/tmp/reki-uv-cache uv run --no-sync make -C doc check SPHINXOPTS='-W --keep-going'
UV_CACHE_DIR=/tmp/reki-uv-cache uv run --no-sync pytest -m 'not needs_data and not cma_hpc and not cmadaas_local and not cmadaas_service'
```

## T5-1：自动门禁结果

以上命令在 2026-09-09 的本地干净文档构建中通过：

- `make data` 获取并校验五个 `v2026.9.1` 冻结资产；
- `data-check` 通过，校验 checksum、time 的 0/6/12/24 h、累计 `tp` 的
  `step_type="accum"` 与 24 h `time_range`、control + PF 1--20、soil layer
  bounds 以及可重建的 SQLite index；
- `examples-check` 运行四个独立 E1 程序并比对固定 JSON 输出；
- 严格 Sphinx HTML 构建执行 MyST-NB 单元，构建 89 个源页面且无 warning；
- `api-check`、`codespell` 和严格 `linkcheck` 均通过；
- 环境无关 pytest 为 **374 passed, 165 deselected, 13 warnings**。13 条均为既有
  pytest collection 或 pandas parser warning，并非测试失败。

CI 的 docs job 仍调用同一 `make -C doc check SPHINXOPTS="-W --keep-going"` 入口，
因此本地与 CI 的数据、示例和文档门禁一致。

## T5-2：真实任务走查

以下走查执行列出的 MyST 页面代码；CLI 项由 subprocess 测试执行。严格 HTML 构建会再次
执行页面单元。输出列是实际断言的关键可观察结果，不以页面文字替代运行证据。

| # | 页面与代码 | 复现命令 | 关键结果 |
|---:|---|---|---|
| 1 | `guide/grib/open-and-inspect` | `from_source("test", "ecmwf_ifs").summary(); reader.unique("parameter")` | 11 个字段；参数含 `2t`、`t`；全程只读 header。 |
| 2 | `guide/grib/select-fields`、`levels` | `reader.sel(parameter="t", level_type="isobaricInhPa", level=850).to_xarray()` | 得到 850 hPa 温度；公开 metadata 为 `level_type="pl"`、`level=850`。 |
| 3 | `guide/grib/levels` | `reader.sel(parameter="t", level_type="isobaricInhPa", level=[500, 850]).to_xarray()` | `isobaricInhPa` 坐标排序后为 `[500, 850]`，不是依赖 GRIB 消息顺序。 |
| 4 | `guide/grib/time-and-step` | `from_source("test", "ecmwf_ifs", variant="time").sel(..., step=[0, 6, 12, 24]).all()` | 4 个字段，step 集合为 0/6/12/24 h；`valid_time` 由起报时间和 step 形成。 |
| 5 | `guide/grib/time-and-step` | `reader.sel(parameter="tp", level_type="surface", level=0, step=24).all().one()` | `tp` 的 `step_type` 为 `accum`，`time_range` 为 24 h。 |
| 6 | `guide/grib/select-fields`、`multiple-fields` | `one_or_none()` 处理不存在参数；`fetch_many(..., errors="collect")` | 零匹配返回 `None`；多匹配由 `one()` 抛出 `MultipleFieldsMatchedError`；批量缺失项带 error，不掩盖成功项。 |
| 7 | `guide/grib/ensemble` | `from_source("test", "ecmwf_ifs", variant="ensemble").sel(..., step=24)` | control 为 `member=0`；PF 1--20 完整存在；xarray `number` 坐标为 0--20。 |
| 8 | `guide/grib/multiple-fields` | `fetch_many([{...850}, {...500}], cardinality="one")` | 按输入顺序返回层次 `[850, 500]`；`errors="collect"` 可逐项报告失败。 |
| 9 | `guide/grib/indexes` | `from_source("file", path, index_policy="auto", index_dir=TemporaryDirectory())` | 首次查询建立 `.sqlite`；同目录 `readonly` 查询可复用该 index。 |
| 10 | `guide/grib/lazy-loading` | `collect_io_metrics()` 包围 metadata 查询与 `to_xarray(lazy=True)` | `value_decode_count == 0`；只有 `.values`、`.load()` 或数值聚合才触发 values decode。 |
| 11 | `guide/grib/cli` | `reki inspect FILE --json`、`reki ls FILE ... --json`、`reki query FILE ... --json` | JSON 保持在 stdout；无匹配的 `query` 退出码为 4，供脚本处理。CLI subprocess 由 `tests/test_cli.py` 覆盖。 |
| 12 | `guide/processing/subset-and-sample`、`regrid` | 从固定 `2t` 执行 `extract_region`、`sample_nearest`、`extract_point`、`interpolate_grid` | 区域为 `(81, 81)`，抽稀和目标网格均为 `(11, 11)`；站点点值为 0 维，目标坐标保持一致。 |

## 结论

12 项均由发布的固定 GRIB2 数据复现；没有把 CMA-HPC、CMADaaS 凭据或公网服务列为默认
验收前提。没有阻断验收的已知事项；外部 URL 仍由每次 CI 的 `linkcheck` 持续监测。
