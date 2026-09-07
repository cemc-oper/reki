# 扩展 source

实现 `Source` 子类，声明稳定名称并仅保存构造参数；在 `mutate()` 中将其转换为更具体的
source，或在 `to_data_object()` 中返回对象。第三方包通过 `reki.sources` entry point
注册，测试可使用 `register()`。

```text
third-party entry point → source class → mutate → FileSource / custom object → reader
```

远程实现必须设置 `remote=True`，不能在 `__init__` 发 I/O。为 source 写正常路径、错误、
惰性边界和 capability 测试；公开接口见 {doc}`../api/sources`。
