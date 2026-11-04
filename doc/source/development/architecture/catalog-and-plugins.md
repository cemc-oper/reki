# 原生数据集目录

`load_catalog(reference=None, *, base_dir=None)` 加载一份 `cedarkit.catalog/v1` 目录。目录登记数据集标识、别名、可选的根目录相对布局和执行默认值。显式引用可固定内容版本和字节 SHA256。

内置目录为六套 CEMC 原始产品登记文件布局。构造阶段固定上下文和来源参数。执行阶段按起报、时效及成员定位文件，再用原生 GRIB 键过滤报文。
