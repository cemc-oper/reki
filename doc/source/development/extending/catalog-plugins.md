# 维护外部产品目录

阶段 1.1 I04 使用明确的本地 `cedarkit.catalog/v1` 资源。共用 CEMC 目录随 reki 提供；业务目录可在自己的配置仓库独立维护，通过 context.catalog.path 引用。旧 catalog entry point、用户目录自动搜索及多层合并已退出新加载器。

外部目录与参数库、映射资源分别版本化。部署固定 path/builtin、精确内容 version 和字节 sha256。文件内默认映射的相对引用基于目录文件位置；参数和原生翻译规则留在各自资源，目录只登记产品身份／业务版本、合法配对范围、总体／方法及来源绑定。

使用 `load_catalog({"path": "/deployment/catalog.json", "version": "1", "sha256": digest})` 检查明确资源，使用 `plan_source_binding` 组合所选参数／映射及精确产品。坏引用、别名冲突、必要定义不足必须报错；不能将示例契约 ID、未知版本、空提供范围或未经核实的统计总体当成真实业务结论。

构造接口与静态检查边界见 {doc}`../architecture/catalog-and-plugins`；公开 API 见 {doc}`../api/catalog`。当前机制不负责文件扫描、服务调用或发布，I05／I06／I08 仍需同步接入。
