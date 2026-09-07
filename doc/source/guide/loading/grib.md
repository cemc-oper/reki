---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.0
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# GRIB

GRIB reader 支持参数、层次、时间、时效、时间范围、集合成员和原生键条件。优先使用
稳定 `parameter_id` 或规范参数名；`resolve_parameter()` 可解析外部命名空间，未知、
歧义和条件冲突分别以明确异常报告。

## 最小可运行筛选

冻结测试数据包含 2 米温度。下例先创建 reader，再以参数、层次类型和层次值共同约束
查询；这比只写 `parameter="2t"` 更容易在多层次产品中得到预期字段：

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs")
field = reader.sel(
    parameter="2t", level_type="heightAboveGround", level=2,
).first()
assert field is not None
data = field.to_xarray()
data.name, data.shape
```

## 逐步缩小查询

字段较多时，先查看匹配数量，再调用 `first()`。`all()` 可保留候选字段供进一步选择；
在业务代码中，零个或多个候选都应作为独立分支处理：

```{code-cell} ipython3
candidates = reader.sel(parameter="2t")
len(candidates.all())
```

```python
field = candidates.first()
if field is None:
    raise LookupError("没有匹配的 2t 字段；请检查参数、层次和时效条件")
```

GRIB header 会映射为统一 metadata、坐标和属性。批量字段可先用 `ls()` / `unique()`；
需要大量重复探索时可选择持久 metadata index。index 会检查文件指纹并在过期、损坏或
不兼容时重建；只读 index 缺失时会失败，不能把它当作数据值缓存。

完整的参数名、层次别名、时效和原生键示例见 {doc}`/guide/grib_parameter`、
{doc}`/guide/grib_level` 与 {doc}`/guide/parameter_resolver`。ecCodes 消息级函数是
兼容边界，见 {doc}`legacy-api`。
