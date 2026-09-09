# xarray 数据契约

reader 在边界处规范化和验证 `DataArray`，使 operator 可以依赖可识别的经纬度、时间、
层次和属性；格式特有信息仍保留为属性或特定坐标。

```text
reader output → normalize_data_array → validate_data_array → DataArray operator
                                     ↘ issue / warning / error
```

不要在 operator 中加入格式探测或 GRIB 修补。常见失败是缺少经纬度、坐标维度不一致或
无法安全规范化；根据 mode 接收 warning 或 error。API：{doc}`../api/core`。
用户可观察的 GRIB 坐标、维度、时间与成员约定见 {doc}`/guide/grib/xarray-output`；处理
操作接受何种输入见 {doc}`/guide/processing/index`。
