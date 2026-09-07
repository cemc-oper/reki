# 扩展 source

实现 `Source` 子类，声明稳定名称并仅保存构造参数；在 `mutate()` 中将其转换为更具体的
source，或在 `to_data_object()` 中返回对象。第三方包通过 `reki.sources` entry point
注册，测试可使用 `register()`。

```text
third-party entry point → source class → mutate → FileSource / custom object → reader
```

远程实现必须设置 `remote=True`，不能在 `__init__` 发 I/O。为 source 写正常路径、错误、
惰性边界和 capability 测试；公开接口见 {doc}`../api/sources`。

## 最小 source 与注册测试

下例的 source 只保存参数，默认 `mutate()` 返回自身，因此适合先验证发现和延后构建契约。
生产 source 可在 `mutate()` 返回 `FileSource` 或在 `to_data_object()` 返回专用数据对象：

```python
from reki import Source, from_source, register


class DemoSource(Source):
    def __init__(self, dataset_id: str, **kwargs):
        super().__init__(**kwargs)
        self.dataset_id = dataset_id


register("demo", DemoSource)
source = from_source("demo", "daily-temperature")
assert source.dataset_id == "daily-temperature"
```

将该代码放入 package-local pytest 时，应在 fixture 中保存并恢复 `REGISTERED` 与
`SourceMaker.SOURCES`，避免测试污染其他 source。远程 source 还应断言
`from_source()` 仅返回 `LazySource`，首次调用转换方法才发生 I/O。

发布第三方 source 时，在项目元数据中声明 entry point，而不是要求用户先调用
`register()`：

```toml
[project.entry-points."reki.sources"]
demo = "my_reki_plugin.sources:DemoSource"
```
