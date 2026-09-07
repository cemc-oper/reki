# GRIB reader 与 index

GRIB 先扫描 header，选择匹配消息，再在 `to_xarray()` 时延迟解码 values。持久 index
保存 metadata 而非数组值，并以文件指纹、schema 和锁保证可重建性。

```text
GRIB file → header scan → metadata / index hit → query match → lazy decode → DataArray
                         ↘ stale/corrupt → lock → rebuild
```

index 的扩展边界是内部模块，不能作为稳定 public API。失败模式包括只读 index 缺失、
文件改变、锁超时和 decoder 不兼容；调用者应选择明确 index policy。公开 reader 与参数
接口见 {doc}`../api/grib`，用户行为见 {doc}`/guide/loading/grib`。
