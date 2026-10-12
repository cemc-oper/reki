# 公共网格查询：从请求到字段

本指南使用 `cedarkit-query` v1 值模型和 reki 的公开绑定、定位与集合读取 API。从 `repo/reki` 执行以下命令。生成器仅在 `/tmp/reki-t17` 创建合成 GRIB2，仓库不保存生成文件：

```bash
uv run --offline --group test python tests/fixtures/t09/generate.py --output-dir /tmp/reki-t17
uv run --offline --group test python - <<'PY'
from pathlib import Path

from cedarkit_query import QueryError, load_request, normalize_request
from reki.catalog import load_catalog
from reki.catalog.query_binding import CatalogSnapshot, plan_source_binding
from reki.query_collection import read_grib_collection
from reki.query_locator import locate_fields

root = Path("/tmp/reki-t17/baseline")
path = root / "f024_m1.grib2"
catalog = load_catalog(builtin=False, plugins=False, user=False, explicit={
    "api_version": "reki.catalog/v1", "datasets": [{"id": "grid", "source": {
        "name": "file-pattern", "args": [str(root), "f{forecast_hour_label}_m1.grib2"]}}],
})
snapshot = CatalogSnapshot(catalog, "t17-local")
request = load_request({
    "api_version": "cedarkit.request/v1", "action": "locate",
    "query": {"api_version": "cedarkit.query/v1", "domain": "grid", "dataset": "grid",
              "parameter": "cedarkit.t", "reference_time": "2026-08-30T00:00:00Z",
              "lead_time": "PT24H", "vertical": {"type": "isobaric", "unit": "hPa", "values": 850},
              "statistic": {"kind": "instant"}, "member": {"id": "1", "role": "perturbation"}},
})
query = normalize_request(request).normalized_request.query
plan = plan_source_binding(query, snapshot=snapshot)
mapping = {"cedarkit.t": "t"}
roles = {"1": "perturbation"}
located = locate_fields(plan, native_parameters=mapping, member_roles=roles,
                        candidate_paths=[path], index_policy="off")
assert located.status == "available" and len(located.references) == 1
result = read_grib_collection(plan, candidate_paths=[path], native_parameters=mapping,
                              member_roles=roles, index_policy="off")
assert result.complete and result.data.attrs["units"] == "K"
assert result.fields[0].reference == located.references[0]
print(result.data.shape, result.data.attrs["units"], located.references[0].verification)

missing_query = query.to_dict()
missing_query["vertical"]["values"] = 70000
missing_plan = plan_source_binding(missing_query, snapshot=snapshot)
try:
    locate_fields(missing_plan, native_parameters=mapping, member_roles=roles,
                  candidate_paths=[path], index_policy="off")
except QueryError as error:
    assert error.code == "not_found"
    print(error.code, error.path)
partial = locate_fields(missing_plan, native_parameters=mapping, member_roles=roles,
                        candidate_paths=[path], missing="partial", index_policy="off")
assert partial.status == "partial" and partial.items[0].verification == "path_exists"
PY
```

`plan_source_binding()` 仅按给定版本的目录快照产生无凭据 Binding，不读资料。`locate_fields()` 扫描本地 GRIB 头并返回带文件指纹和字段位置的 `DataReference`，不解码 values；`read_grib_collection()` 才读取值。只有单个参数、可核对的原生短名映射和成员角色才能进入此例。上例的 `hPa` 查询层规范化为 `85000 Pa`；原始温度值仍为 `K`，reki 不自动换成摄氏度。完整集合的 `result.data` 是 xarray DataArray，`result.fields` 保留逐字段引用；显式 `missing="partial"` 时 `missing` 列出缺项，读取结果不伪造完整立方体。默认缺项、重复匹配和不兼容网格都会报错。

## 多文件与执行边界

`lead_time`、`vertical.values` 和 `member` 可为列表或范围，独立维度展开为笛卡尔积。调用方提供受控的有限 `candidate_paths`；reki 按字段身份组织多个文件，而非按文件顺序或文件名推断成员。T09 生成器的 `manifest.json` 记录 0–72h 每 6h、两层、三个成员的 78 个字段；对应读取和缺项回归见 `tests/readers/grib/test_query_collection.py`。对重复调用，可使用 `CollectionSession` 的有界原生元数据/值缓存；文件指纹变化会使旧引用失效。`index_policy="off"` 不创建索引；其他策略与缓存限制见 {doc}`../development/api/grib`。

公共本地 `list/locate/read` 当前只支持 GRIB。`native_grid`、`coverage`、层边界和不能核验的原生条件会返回 `unsupported`；NetCDF、GrADS、表格/NWPC 继续使用原有 reader/API。`read` 不自动执行公共 `transforms`。请求结构、JSON Schema 和错误码见同一工作区的 `repo/cedarkit-query/docs/protocol-v1.md`；非绘图命令与退出码见 {doc}`query-cli`。

## 冻结的 CMADaaS 支持

内置数据集 `cma_gfs_gmf_cmadaas` 的 `plan_frozen_cmadaas()` 可离线计算请求；`read_frozen_cmadaas()` 才使用现有可选客户端访问服务。必须提供冻结参数注册表 SHA256。例如从 `repo/reki` 离线检查 TEM 绑定：

```bash
uv run --offline --group test python - <<'PY'
from reki.catalog.query_binding import builtin_catalog_snapshot, plan_source_binding
from reki.parameter_adapter import FROZEN_REGISTRY_SHA256
from reki.query_cmadaas import plan_frozen_cmadaas

query = {"api_version": "cedarkit.query/v1", "domain": "grid",
         "dataset": "cma_gfs_gmf_cmadaas", "parameter": "cedarkit.t",
         "reference_time": "2026-08-30T00:00:00Z", "lead_time": "PT24H",
         "vertical": {"type": "surface"}, "statistic": {"kind": "instant"}}
binding = plan_source_binding(query, snapshot=builtin_catalog_snapshot())
execution = plan_frozen_cmadaas(binding, registry_sha256=FROZEN_REGISTRY_SHA256)
assert execution.request.parameter == "TEM"
print(execution.request.parameter, execution.request.level_type, execution.request.level)
PY
```

首版仅覆盖 2026-08-30 00Z、+24h、历史北京区域 39–41°N/115–117°E 地面场的 `cedarkit.t/TEM`、`cedarkit.h.any/GPH` 瞬时场和 `cedarkit.rainc.any/CPE`、`cedarkit.rainnc.any/LPE` 0–24h 累计场。远端离线定位返回 `remote_unverified`，没有服务版本时不能当作本地缓存已验证数据。详见 {doc}`../development/api/cmadaas`；离线冻结请求/响应测试不证明服务当前可达。
