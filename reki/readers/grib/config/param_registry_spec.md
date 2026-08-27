# GRIB2 要素注册表约束规范

本文档是 `param_registry.yaml` 的**约束规范**（specification）。注册表文件必须满足
本文档全部编号规则；`tests/` 中的校验测试按规则编号逐条实现，任何注册表修改必须
通过校验方可合入。

- 版本：v2.0
- 适用文件：`reki/readers/grib/config/param_registry.yaml`
- 强制级别用语：**必须**（MUST，违反即校验失败）、**应当**（SHOULD，违反产生
  警告）、**可以**（MAY，可选项）。

变更记录：

- v1.1：条目级增加可选 `aliases` 字段（被提升为通用名的行的别名）；变体级增加
  可选信息性字段 `typeOfLevel`/`level`（供反查生成 ecCodes 过滤键，不参与
  `when` 匹配，修订 M6）；M7 增加基名变体合成规则（M7b）。
- v2.0：快照升级为带 `api_version`/`entries` 的文档；entry 和 variant 均发布
  全局唯一的 `parameter_id`，并由 reki 的只读 resolver 解析为 `FieldQuery`。

## 1. 文件组织

- **F1** 注册表由单一 YAML 文件承载，编码为 UTF-8。
- **F2** v2 顶层结构为含 `api_version: reki.parameter-registry/v2` 与 `entries`
  的文档对象；兼容 loader 可读取历史顶层列表，但不得再发布它。
- **F3** 条目**应当**按 `(discipline, category, number)` 升序排列，以保证 diff 可读。
- **F4** 文件中**不应**使用 YAML 锚点（`&`/`*`）、合并键（`<<`）与自定义标签，
保持数据可被任何 YAML 解析器以 `safe_load` 读取。

## 快照文档版本（v2）

当前发布格式为：

```yaml
api_version: reki.parameter-registry/v2
entries:
  - parameter_id: cedarkit.t
    key: {discipline: 0, category: 0, number: 0}
    name: t
    params:
      - parameter_id: cedarkit.t2m
        name: t2m
```

`api_version`、`entries` 及 entry/variant 的 `parameter_id` 都是必填项。ID
必须全局唯一，采用 `cedarkit.` 命名空间和小写 ASCII/数字/连字符组成的分段 ID，且不得根据 name、alias
或导出顺序在运行时重算。旧的顶层 list 仅可由兼容 loader 读取，不能由 v2
exporter 重新发布。

## 2. 数据模型

```
注册表
 └─ 条目 entry                 # 一个 GRIB2 要素（编号三件套唯一确定）
     ├─ key                    # 主体检索键：discipline / category / number
     ├─ name                   # 通用名（CEMC 优先）
     ├─ wgrib2_name            # WGRIB2 风格短名（可选）
     ├─ unit / description / description_cn   # 通用名元数据（可选）
     └─ params []              # 条件变体列表（可选）
         ├─ name               # 变体名
         ├─ aliases []         # 别名（可选）
         ├─ when               # 匹配条件（必填）
         └─ unit / description / description_cn   # 可选，缺省继承条目级
```

命名体系：每个要素至多一个 `wgrib2_name`（层次无关，要素级），一个通用名
`name`（尽量采用 CEMC 要素名称），以及若干按层次/时间等条件区分的变体名。

## 3. 字段定义

### 3.1 条目级字段

| 字段 | 必填 | 类型 | 约束 |
|---|---|---|---|
| `key` | 必须 | map | 见 3.2 |
| `name` | 必须 | str | **E1** 非空，不含空白字符 |
| `aliases` | 可选 | list[str] | **E4** 通用名的别名（被提升行原有的别名），每个元素满足 E1 |
| `wgrib2_name` | 可选 | str | **E2** 非空，**应当**为 WGRIB2 风格大写短名 |
| `unit` | 可选 | str | **E3** 不需要时省略字段，**不得**写空字符串 |
| `description` | 可选 | str | 同 E3 |
| `description_cn` | 可选 | str | 同 E3 |
| `typeOfLevel` | 可选 | str | **E5** 信息性字段：ecCodes 层次类型名，不参与 `when` 匹配 |
| `level` | 可选 | number | **E5** 信息性字段：与 `typeOfLevel` 配对的层次值 |
| `params` | 可选 | list | **E6** 省略或为空列表表示该要素无条件变体 |

### 3.2 `key` 子字段

| 字段 | 必填 | 类型 | 约束 |
|---|---|---|---|
| `discipline` | 必须 | int | **K1** 0–255（GRIB2 代码表 0.0） |
| `category` | 必须 | int | **K2** 0–255（参数类别） |
| `number` | 必须 | int | **K3** 0–255（参数编号） |

### 3.3 变体（`params` 元素）字段

| 字段 | 必填 | 类型 | 约束 |
|---|---|---|---|
| `name` | 必须 | str | **V1** 同 E1 |
| `when` | 必须 | map | **V2** 非空，键必须属于 §3.4 白名单 |
| `aliases` | 可选 | list[str] | **V3** 每个元素满足 E1 |
| `typeOfLevel` | 可选 | str | **V4** 信息性字段，同 E5 |
| `level` | 可选 | number | **V4** 信息性字段，同 E5 |
| `unit` | 可选 | str | 缺省时继承条目级 |
| `description` | 可选 | str | 缺省时继承条目级 |
| `description_cn` | 可选 | str | 缺省时继承条目级 |

### 3.4 `when` 条件键白名单

| 键 | 类型 | 含义 |
|---|---|---|
| `first_level_type` | int 0–255 | GRIB2 第一层类型代码（如 1=地面，100=等压面，103=距地高度，106=土层深度） |
| `first_level` | number | 第一层数值（单位由层次类型决定） |
| `second_level_type` | int 0–255 | 第二层类型代码（层次区间时与第一层配对） |
| `second_level` | number | 第二层数值 |
| `stepType` | str | 时间统计方式，取值**应当**限于：`instant`、`accum`、`max`、`min`、`avg` |
| `time_range_hours` | number > 0 | 统计处理时间窗长度，统一归一化为**小时**（分钟级用小数） |

新增条件键必须先修订本规范（升版本号）再加入白名单，**不得**直接在注册表中
使用白名单外的键。

## 4. 约束规则

### 唯一性

- **U1** `key`（三元组）全局唯一。
- **U2** 同一条目内，变体 `name` 互不重复。
- **U3** 变体 `name` 允许与条目通用名相同（表示通用名同时带有精确条件，见
  迁移规则 M2），但同一条目内至多一个这样的变体。
- **U4** 同一条目内，`aliases`（条目级与变体级）不得与本条目任何 `name`
  （通用名或变体名）重复；**应当**保证别名全局不与任何 `name` 冲突。

### 条件约束

- **C1** `when` 中不得出现 §3.4 白名单以外的键。
- **C2** `second_level_type` / `second_level` 必须成对出现，且出现时
  `first_level_type` / `first_level` 必须同时存在（层次区间语义不允许只有上界）。
- **C3** `time_range_hours` 必须为正数；`stepType: instant` 时**不得**出现
  `time_range_hours`（瞬时量无时间窗）。
- **C4** 同一条目内不得出现 `when` 完全相同的两个变体。历史遗留的并列命名
  （如 `u10mmax#1/#3`）已通过 `time_range_hours` 区分；确需新增并列命名时，
  必须先在本规范附录 B 登记并说明理由。

### 通用名选取（数据语义约束）

- **N1** 通用名**应当**采用 CEMC 要素名称；仅当无 CEMC 命名时使用 `wgrib2_name`。
- **N2** 存在无条件（通配）命名时，该名称**必须**作为条目级通用名，而不得
  以无 `when` 的变体形式出现在 `params` 中（V2 已禁止无条件的变体）。

### 展示性约束（SHOULD，产生警告）

- **L1** 条目按 F3 排序。
- **L2** `wgrib2_name` 大写。
- **L3** `stepType` 取值属于 §3.4 建议集合。

## 5. 匹配语义（注册表作者须知）

注册表按以下语义被 `reki.readers.grib.config` 消费，编写条目时必须以此为依据：

1. **变体命中**：`when` 中每个键的值都等于实际值；`when` 中缺省的键 = 该维度
   通配。实际值缺失（`undef`）时该变体不命中。
2. **最具体匹配**：命中的变体中，`when` 键数最多者胜出。
3. **并列裁决**：键数并列时，`params` 列表中书写靠后者胜出。（正常数据不应
   依赖此规则——见 C4。）
4. **通用名回退**：无变体命中时返回条目级 `name`。
5. **wgrib2 名**：与层次无关，不进入变体匹配，由 `find_wgrib2_name` 单独返回。

## 6. 校验实现

- 结构类规则（F、E、K、V、C1–C3、字段类型）由附录 A 的 JSON Schema 覆盖，
  CI 使用 `jsonschema` 包校验（加入 reki 的 test 依赖组）。
- 跨字段与全局规则（U1–U4、C4、N2）由 pytest 自定义断言实现，测试用例名与
  规则编号一一对应（如 `test_registry_U1_unique_keys`）。
- 展示性规则（L1–L3）以 warning 形式报告，不阻断 CI。

## 附录 A：JSON Schema（结构约束的参考实现）

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
type: array
items:
  type: object
  required: [key, name]
  additionalProperties: false
  properties:
    key:
      type: object
      required: [discipline, category, number]
      additionalProperties: false
      properties:
        discipline: {type: integer, minimum: 0, maximum: 255}
        category:   {type: integer, minimum: 0, maximum: 255}
        number:     {type: integer, minimum: 0, maximum: 255}
    name:         {type: string, pattern: "^\\S+$"}
    aliases:
      type: array
      items: {type: string, pattern: "^\\S+$"}
    wgrib2_name:  {type: string, pattern: "^\\S+$"}
    unit:         {type: string, minLength: 1}
    description:      {type: string, minLength: 1}
    description_cn:   {type: string, minLength: 1}
    typeOfLevel:      {type: string, minLength: 1}
    level:            {type: number}
    params:
      type: array
      items:
        type: object
        required: [name, when]
        additionalProperties: false
        properties:
          name:    {type: string, pattern: "^\\S+$"}
          aliases:
            type: array
            items: {type: string, pattern: "^\\S+$"}
          when:
            type: object
            minProperties: 1
            additionalProperties: false
            properties:
              first_level_type:  {type: integer, minimum: 0, maximum: 255}
              first_level:       {type: number}
              second_level_type: {type: integer, minimum: 0, maximum: 255}
              second_level:      {type: number}
              stepType:          {type: string}
              time_range_hours:  {type: number, exclusiveMinimum: 0}
          typeOfLevel:     {type: string, minLength: 1}
          level:           {type: number}
          unit:            {type: string, minLength: 1}
          description:     {type: string, minLength: 1}
          description_cn:  {type: string, minLength: 1}
```

## 附录 B：并列命名豁免登记

当前无豁免条目。历史并列组 `u10mmax#1/#3`、`v10mmax#1/#3`、`wmax#1/#3`、
`cdbzmax#1/#3` 已通过 `time_range_hours` 条件区分，不再属于并列。

## 附录 C：迁移规则（cemc-param-table.csv / wgrib2_short_name.csv → 本注册表）

- **M1** cemc CSV 按三元组分组，组内保持原文件行序作为 `params` 顺序。
- **M2** 通用名提升：组内存在条件全空的行 → 其 `name`/元数据提升为条目级，
  该行不进 `params`；否则取首个非 alias 行提升为条目级通用名，该行保留在
  `params` 中。
- **M3** wgrib2 CSV 按三元组 join，结果填入条目级 `wgrib2_name`；wgrib2 独有
  的三元组生成仅有 `key`/`name`/`wgrib2_name` 的条目（`name` 取 wgrib2 名）。
- **M4** `alias=TRUE` 行并入同条件正名行的 `aliases`。
- **M5** `first_level_type` 等 5 列中非空者写入 `when`，全空则省略（随 M2
  提升后不出现无 `when` 的变体）。
- **M6** 旧列 `typeOfLevel`/`level` 以条目级/变体级信息性字段保留（E5/V4），
  供 `convert_parameter` 生成 ecCodes 过滤键，不参与 `when` 匹配。
- **M7** `#1/#3` 并列组按模型输出间隔补充 `time_range_hours` 条件（1 或 3）。
- **M7b** 每个 `#<N>` 后缀变体必须存在对应的无后缀基名变体（`when` 相同但
  不含 `time_range_hours`）；源数据缺失时迁移合成（如 `cdbzmax`、`dbzmax`），
  插入在 `#` 变体之前。
- **M8** 迁移结果须通过对拍测试：新旧两套数据对全部三元组 × 代表性层次
  组合执行三个查询函数，结果一致。认可的豁免项：
  (a) `find_short_name` 由 wgrib2 优先改为 CEMC 通用名优先；
  (b) `find_cemc_name` 无变体命中时回退通用名（原返回 `None`）；
  (c) 调用方未提供时间窗时，原返回 `#` 后缀名（行序巧合）现返回基名。
```
