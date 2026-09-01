# 数据集目录

数据集目录将稳定的逻辑数据集 ID 绑定到可序列化的 `SourceSpec`。加载或解析目录
不会打开 source、扫描目录或发起网络请求。

```python
import reki

catalog = reki.load_catalog()
source_spec = catalog.resolve("my_dataset").source
```

目录文档必须是严格的 YAML（或 JSON）：

```yaml
api_version: reki.catalog/v1
datasets:
  - id: my_dataset
    aliases: [MY-DATASET]
    source:
      name: local
      args: [my_dataset/grib2/orig]
      kwargs: {data_class: od}
```

优先级从高到低依次为：显式传入的目录/调用参数、用户目录、已安装的
`reki.catalogs` 插件和内置目录。高优先级层会替换整条记录，而非替换其中个别字段。
用户文件为 `$XDG_CONFIG_HOME/reki/catalog.yaml`（或
`~/.config/reki/catalog.yaml`）；可设置 `REKI_CATALOG_PATH` 使用其他文件。
需要进行可复现诊断时，可传入 `user=False` 或 `plugins=False` 排除相应层。

```console
reki catalog list --no-user --no-plugins
reki catalog show my_dataset
reki catalog resolve MY-DATASET
```

CLI 输出会脱敏 source kwargs。它会报告生效层以及被其替换的记录，但绝不会构造
source。

内置目录包含 CMA-GFS、CMA-MESO-3KM、CMA-MESO-1KM、CMA-TYM、CMA-GEPS 和
CMA-REPS 的本地业务绑定。历史名称 ``CMA-MESO`` 会解析为
``cma_meso_3km``；如需显式选择一公里数据集，请使用 ``CMA-MESO-1KM``。

内置的远程 CMADaaS bindings 按产品类型分开，以免将确定性分析/预报或集合控制/扰动
误作同一数据集：

| 产品 | catalog alias |
| --- | --- |
| CMA-GFS 分析 / 预报 | ``CMA-GFS-ANALYSIS-CMADaaS`` / ``CMA-GFS-FORECAST-CMADaaS`` |
| CMA-MESO-3KM 分析 / 预报 | ``CMA-MESO-3KM-ANALYSIS-CMADaaS`` / ``CMA-MESO-3KM-FORECAST-CMADaaS`` |
| CMA-MESO-1KM 分析 / 预报 | ``CMA-MESO-1KM-ANALYSIS-CMADaaS`` / ``CMA-MESO-1KM-FORECAST-CMADaaS`` |
| CMA-TYM 分析 / 预报 | ``CMA-TYM-ANALYSIS-CMADaaS`` / ``CMA-TYM-FORECAST-CMADaaS`` |
| CMA-GEPS 控制 / 扰动预报 | ``CMA-GEPS-CONTROL-CMADaaS`` / ``CMA-GEPS-PERTURBATION-CMADaaS`` |
| CMA-REPS 控制 / 扰动预报 | ``CMA-REPS-CONTROL-CMADaaS`` / ``CMA-REPS-PERTURBATION-CMADaaS`` |

历史别名 ``CMA-GFS-CMADaaS`` 继续表示 CMA-GFS 预报。所有远程记录均不包含凭证，且
source 构造不会产生网络副作用；凭证应配置在运行时的 CMADaaS client 中。在线服务
可用性、产品/网格等价性和集合成员请求方式属于环境集成问题，而不是目录解析所保证的
内容。区域部署、试验产品和账号专属的 data code 不应修改内置记录；请在用户或插件目录
中提供同一 ID 的完整替代记录。目录按整条记录覆盖，因此替代记录必须重新声明
``source``、别名和所需 metadata，且可通过 ``reki catalog resolve`` 查看其生效来源。

对于任务提供的目录和文件名，请使用 ``file-pattern`` source。它只接受
``{start_time_label}``、``{forecast_hour}`` 和 ``{forecast_hour_label}``
替换；渲染时不会执行表达式或文件系统检查。
