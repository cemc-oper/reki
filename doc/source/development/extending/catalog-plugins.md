# 扩展 catalog 插件

catalog 插件提供可验证的静态记录，并让系统在不 I/O 的情况下合并为 `ResolvedDataset`。

```text
plugin catalog → schema validation → precedence merge → dataset ID / alias resolution
```

不要在插件导入时读取服务、环境变量或文件内容。为冲突覆盖、别名和无效 schema 编写测试；
将运行时参数放在 source 构造而不是 catalog 解析。API：{doc}`../api/catalog`。

## 最小插件层

entry point 可以返回 YAML/字典对象或返回该对象的零参数 callable。记录必须采用
`reki.catalog/v1`，并且 source 描述保持可序列化：

```python
def catalog_layer():
    return {
        "api_version": "reki.catalog/v1",
        "datasets": [
            {
                "id": "demo-temperature",
                "aliases": ["demo-t2m"],
                "source": {"name": "test", "args": ["ecmwf_ifs"]},
                "metadata": {"owner": "example-plugin"},
            }
        ],
    }
```

```toml
[project.entry-points."reki.catalogs"]
demo = "my_reki_plugin.catalog:catalog_layer"
```

使用 `load_catalog(explicit=catalog_layer(), builtin=False, plugins=False, user=False)` 测试
schema、别名解析和来源；另写冲突测试，确认同一 dataset ID 的替换是整条记录替换，且新
别名不能夺取仍有效记录的别名。不要在 `catalog_layer()` 中读取环境变量、目录或远程服务。
