# 查询契约（阶段 1）

`SourceSpec` 是不可变、可序列化的 source 描述；`FieldQuery` 仅描述字段需求。
新代码对于必需字段使用 `reader.sel(query).one()`，对于可选字段使用
`one_or_none()`；`first()` 仍是保持兼容的宽松 API。

## Xarray 契约矩阵

标准化不会修改原对象。验证仅检查元数据，默认模式为 `warn`，因此不会计算惰性
values，也不会改变 legacy reader 的返回值。

| 项目 | 阶段 1 规则 | 状态 / 例外 |
| --- | --- | --- |
| 坐标 | 存在时使用 `latitude`、`longitude`、`time`、`step`、`valid_time`、`level` 与 `number`/`member`。 | 已覆盖 GRIB、NetCDF、GrADS 和 CMADaaS 离线场景。 |
| 经度 | 保持 reader 原生的范围和顺序。 | 不隐式转换 `0..360` / `-180..180`；因此可直接追溯原始范围。 |
| 纬度 | 保持原生一维方向。 | 二维网格作为已记录的例外保留。 |
| 时间 | 保持 xarray datetime dtype；同时保留两个值的 reader 必须满足 `time + step = valid_time`。 | 不进行时区转换。 |
| 层次 | 输出时使用 `level`；在 source attributes 中保留 GRIB level type。 | 本阶段不重命名 reader 特有名称。 |
| 参数 | 使用解码后的稳定数据名称；在 attrs 中保留 GRIB 标识。 | 不迁移参数注册表。 |
| 单位 | 将单位保存到 `attrs["units"]`。 | 缺失单位产生 `missing-units`；未知单位按原样保留。 |
| 网格 / CRS | 保持 grid mapping 和坐标拓扑。 | 对未知 CRS 不伪造 CRS。 |
| 统计 | 保持 `stepType`、time-range 和累积属性。 | 不推断统计含义。 |
| 集合 | 保持 `number`/`member` 和 control-member 表示。 | reader 未输出时不进行 member 标准化。 |
| 溯源 | `normalize_data_array(..., source=...)` 记录 `reki_source`。 | 传入前必须对 source 摘要脱敏。 |

阶段 1 唯一会标准化的元数据问题是 `missing-units`。以下已记录的 backlog 有意仅以
warn 形式提示：`XR-001` 经度/纬度方向、`XR-002` CRS/grid mapping、`XR-003` 二维
坐标、`XR-004` 集合表示，以及 `XR-005` 累积/统计字段。它们都会保留 reader 原生
元数据，而不会静默改变数组布局或数值语义；fixture 扩展属于阶段 2/3 评审范围。
