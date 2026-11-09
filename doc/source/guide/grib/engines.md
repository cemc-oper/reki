# 读取引擎

GRIB 只使用 ecCodes。cfgrib 后端、`reki.format.grib.cfgrib` /
`reki.readers.grib.cfgrib` 及子模块已删除，包不再依赖 cfgrib；不会自动卸载用户已有安装。
旧路径导入正常失败，不转成 SourceError，也不透明转发到 ecCodes。

受保护字段函数显式 `engine="cfgrib"` 报 `QueryError(code="unsupported")`。
普通 format 与 ecCodes 公共导入仍使用各自原有导出，并由同一 ecCodes 内核实现。

高频 first-match / 多层行为和低频 Dataset 组织有不同保护范围，不能仅机械替换 import；
详见 {doc}`/guide/legacy_grib` 和 {doc}`/guide/migration`。
