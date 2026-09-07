# 扩展 reader

reader factory 接收 source、path、magic 和 `deeper_check`，快速探测不能读取大量内容；深度
探测才可检查格式结构。返回 `None` 表示不认领，返回 Reader 表示认领。

```text
magic probe → None | Reader → deep probe → Reader → metadata / conversion methods
```

实现 capabilities、`sel()`、metadata 及受支持的转换；不支持的操作抛出
`UnsupportedOperationError`。明确 reader 名称应绕过自动分派。API：
{doc}`../api/readers`，GRIB 参考见 {doc}`../architecture/grib-reader-and-index`。

## 最小 factory 骨架

factory 在浅探测阶段只能使用 `magic`；深探测阶段才可打开文件验证结构。两阶段都无法
确认时必须返回 `None`，以便其他 reader 继续尝试：

```python
from reki.readers import Reader


class DemoReader(Reader):
    def to_numpy(self, **kwargs):
        return self._values


def READER(source, path, magic=None, deeper_check=False, **kwargs):
    if magic is not None and not magic.startswith(b"DEMO"):
        return None
    if not deeper_check:
        return None
    reader = DemoReader(source, path)
    reader._values = [1, 2, 3]  # 实际实现应从已验证的 path 解码
    return reader
```

测试至少覆盖：不匹配 magic 返回 `None`、浅探测不读取完整文件、深探测认领正确文件、
显式 `reader="demo"` 的错误名称，以及未实现的 `to_xarray()` 抛出清晰异常。
