# 产品目录、上下文与资源加载（阶段 1.1 I04）

I04 采用 `cedarkit-query` 的 `Catalog`、`Context`、`Request` 和共享校验。目录格式为 `cedarkit.catalog/v1`；旧 `reki.catalog/v1`、`CatalogSnapshot`、`ResolvedDataset` 和 Binding 不再是当前配置契约。CLI 和运行来源的同步消费由 I05／I08 承接，当前交付不能作为完整配套发布。

`load_catalog(reference=None, *, base_dir=None)` 只加载一份明确选中的资源，返回公共 `Catalog`。`load_resource(reference, kind, ...)` 另返回实际字节 SHA、规范资源引用和源文件目录；`load_context(mapping_or_path, ...)` 固定引用基准并冻结配置。允许本地 JSON／YAML 和有限登记的 builtin；不搜索插件、环境变量、用户目录、上级目录或网络，不合并多个目录，不在失败后寻找其他版本。读取配置文件属于构造 I/O，业务文件扫描、服务调用和值读取尚未执行。

资源引用是 path/builtin 二选一，可固定精确内容 version 和实际文件字节 sha256。JSON／YAML 同一内容可能具有不同字节摘要。格式版本、内容版本、业务产品版本和适配器软件版本分别记录；路径变化不等于业务版本变化。

内置 `reki.catalog` 当前登记旧目录有据的 18 个数据集身份／别名，**没有可发布的产品定义或可执行来源绑定**。`products: []` 表示该数据集的产品定义未发布，不表示无限提供范围。旧 YAML 保留在源码中作为核查材料，新运行加载器不读取它；新 wheel 只打包新目录。实际产品版本、合法配对 provides、统计总体／方法、服务时区和精确接口引用仍需补证据。不得用样本日期或门户抓取日期填产品业务版本。

参数库引用为显式上下文 > 已明确登记的内置默认；目录亦同。当前没有冒充完整覆盖的内置参数／映射快照。按后端分别选择映射：上下文 > 数据集 > 内置登记，同一后端选中一个完整资源，不能拼接规则。未提供该后端引用时才考虑下层；空 mappings 对象本身没有后端项。目录内映射相对路径基于目录资源自身位置。显式坏引用不回退。

`plan_source_binding(source, *, context=None, product=None, product_version=None, source_id=None, ...)` 是供 I05 消费的**内部构造计划**，不是 `from_source` 的执行替身。source 与 context 仍按共享契约校验；dataset 别名精确解析，产品和业务版本来自调用层明确解析的事实，通过内部参数传入，不在公共 Query／Request.source 加新字段，也不自动挑最新版本。多个同类来源必须明确 source_id；不按列表顺序试探接口。无 dataset 的 file 可只固定路径／glob，参数解释不足时须由 I05 选择层报告。

构造调用共享 `validate_resource_set`／`validate_product` 和 `analyze_product_mappings`。后者逐一保留 provides 配对及原索引，检查精确参数身份、产品身份、applies_to.time、when 和有效 scope 的联合交集；父参数映射不会自动继承给变体。`mapping_applicability` 保留行级关系，`product_coverage` 给出 covered／partial／missing／undetermined。明确缺失或部分覆盖的选中资源报带资源／参数／provides 索引的上下文不足；有限离散分区可以联合证明覆盖。连续区间联合覆盖尚不能证明或内部 10000 单元静态检查预算耗尽时保留 undetermined，不把配置域大小当执行上限错误。covered 只证明声明的静态谓词覆盖，原生翻译、动态成员关系、接口关联与实际来源仍为 pending_I06；未选择映射资源或 provides 没有明确参数域时也不产生后端覆盖证明。

产品 scope 与 context.scope 求交，矛盾报冲突；`provides` 保留 Query 分支配对，不展开成笛卡尔积，不注入原 Query。执行默认逐字段按上下文 > 数据集 > 库默认（available、10000），max_expansion 固定在计划中。本次终结 completeness 的覆盖留 I05。角色按明确成员覆盖；仅已识别 CEMC 数据集使用 0 control、正整数 perturbation 默认，其他来源未知。

file 的字面路径／有序列表或 directory＋有序 glob 原样固定，不调用 glob。local 要求 dataset/root 及显式登记的根目录相对模板；`local_layouts` 是部署传入的内部 `(dataset, product, business_version, source_id) -> ordered templates` 登记，不是新公共资源 schema。当前只验证相对性和有限占位字段，尚未在运行来源中渲染或确认实际布局匹配；执行时的根目录包含性、查询时间／时效解析和有序发现归 I05。旧 finder Jinja 模板不会自动翻译或启用。

CMADaaS 的 data_code／interface_contract／time_zone 来自产品来源绑定；连接配置只引用，外部 client 不序列化。config/client 互斥；没有连接输入时报上下文不足。I06 提供明确 `(id, version)` 契约注册集合；默认空，未知引用拒绝。构造不读取认证文件、不创建 client、不验证连接，不因接口名称或14 位时间格式猜 UTC。`source_binding` 保留完整时区等已登记事实，供 I06 使用；`report_context()` 遵守共享报告结构，排除连接配置和 client。

实际 I03 组合及未覆盖范围见工作区阶段证据 `doc/2026-10-13-stage1.1-query-reki/evidence/I04/`。I04 整项仍进行中；此目录提供内部接口和机制说明，不代表 Q17／Q20 已通过。


I04 续作已将 16 份旧配置整理为 60 个有序根目录方案，保留原位置和字节摘要，仅在工作区 round-2 证据中提供未启用的 root-relative 候选。有限内部模板字段另支持 `year`、`date_label`、`member_3digit`，分别承接旧声明的四位年、八位日期和三位补零成员文本；已有 start_time_label／forecast_hour_label 按原声明格式传入。I05 仍负责从有效 Query 安全生成这些文本、物理包含性与发现，不会将模板时间插值加入 glob。合成格式等价不证明业务版本、部署根或产品提供范围。旧 REPS 挂载模板的 query.system=cma_geps 冲突保留在审核材料，未自动修复或启用。
