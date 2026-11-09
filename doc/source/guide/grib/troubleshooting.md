# 排错

先核头信息、来源范围和查询基数，再解码数值。

| 现象 | 检查与处理 |
| --- | --- |
| 没有匹配字段 | 读取 all() 的 metadata / report，核参数、层次、时效、成员和选中的实际文件。 |
| one() 多个匹配 | 细化查询；multiple_matches 不应被当成 no_match。 |
| 输出冲突 / 网格不同 | 分别检查 duplicate_field / incompatible_grid 和记录来源。 |
| cfgrib / 旧索引选项 | 已退出，按迁移页使用 ecCodes；不要尝试创建索引绕过。 |
| 访问、认证、超时或损坏 | 保留 SourceError 的 code / context / 底层异常链，不能伪装成缺场。 |

公开 Request CLI 当前支持的 explain/read 与 Python 使用相同 Request 结构；历史所有
调用方式一致性的余项仍须独立补验。报告不应包含凭据或无关原场数值。
