GRIB 与参数解析
===============

GRIB reader、参数 registry/resolver 和消息级辅助函数。持久 index 是内部实现，
只在 :doc:`../architecture/grib-reader-and-index` 中说明。

.. automodule:: reki.readers.grib
   :members:
   :member-order: bysource

.. automodule:: reki.readers.grib.config
   :members:
   :member-order: bysource

.. autodata:: reki.readers.grib.config.WHEN_KEYS

.. autofunction:: reki.readers.grib.config.check_value

.. autofunction:: reki.readers.grib.config.find_cemc_name

.. autofunction:: reki.readers.grib.config.find_short_name

.. autofunction:: reki.readers.grib.config.find_wgrib2_name

.. autofunction:: reki.readers.grib.config.get_param_registry

.. autofunction:: reki.readers.grib.config.get_parameter_index

.. automodule:: reki.readers.grib.eccodes
   :members:
   :member-order: bysource

公共查询定位
------------

``reki.query_locator`` 从 T08 的受控 ``BindingPlan`` 展开有限查询，并通过现有
GRIB index 或头扫描执行 ``list_fields`` / ``locate_fields``；两者不解码 values。
本地结果分别报告 ``not_found``、``path_exists`` 或 ``field_confirmed``，天擎
绑定只报告 ``remote_unverified``，不访问服务。调用方须显式提供稳定参数 ID 到
原生 GRIB shortName 的映射；选择成员时还须提供 ID 到角色的映射。地面、等压面和
单一离地高度可定位；其他未核验的层次、网格和 coverage 条件报 ``unsupported``。

返回的 ``LocatedItem``、``DataReference`` 与 ``ListedField`` 含受控文件路径，不能直接用于公开
日志。``verify_data_reference`` 可从 JSON/dict 回读引用，检查本地文件的
size、mtime_ns、device、inode 指纹；``locate_fields(hash_resources=True)``
另存 SHA256，并在回读时核对文件内容。文件变化报 ``stale_reference``。四元指纹
无法证明文件在相同元数据下未被改写；严格内容核验会额外读取整个文件，但不解码
GRIB values。``reki-local`` 解析需要调用方提供
配置目录，并由调用方保证 T08 的 ``config_version`` 对应所选配置。

.. automodule:: reki.query_locator
   :members:
   :member-order: bysource

多文件 GRIB 读取
---------------

``read_grib_collection`` 消费受控 ``BindingPlan`` 与调用方明确给定的有限
``candidate_paths``。file-pattern 绑定要求所有候选路径位于其解析后的根目录内。
首版只组织单参数、单起报时次、单统计方式和同一层类型；稳定参数到原生 shortName、
成员 ID 到角色的映射由调用方显式提供。候选文件顺序不影响结果；重复字段报
``multiple_matches``，缺项默认报 ``not_found`` 并附期望身份列表。

``missing="partial"`` 返回已读取的 ``fields``、缺失组合 ``missing`` 与缺失候选路径
``missing_paths``，其中 ``data`` 为
``None``，不会用零或 NaN 偷填完整立方体。完整结果的 ``data`` 是
``xarray.DataArray``，按 ``lead_time``、可选 ``isobaricInPa``、可选 ``member``、
原生纬经度排序。``member_role`` 和 ``valid_time`` 是坐标；GRIB 单位、网格类型
及每个字段的 ``source_references`` 留在属性或结果对象中。相同形状但不同坐标、
原生网格类型或单位的数据不能合并。读取前后均校验文件引用；需要防止相同文件
元数据下的改写时使用 ``hash_resources=True``。集合读取会解码 values；
元数据查询仍使用上面的 ``locate_fields`` / ``list_fields``。

.. automodule:: reki.query_collection
   :members:
   :member-order: bysource

批量读取与会话缓存
------------------

``CollectionSession`` 提供 ``read``、按输入顺序返回的 ``read_many``、
``cache_info``、``clear``、``close`` 和上下文管理。``read_many`` 接受
``CollectionRequest`` 序列；首个失败会向调用方抛出异常。会话只缓存原生
GRIB metadata 和已解码的原生字段，不缓存公共查询结果或 transform 输出。
因此查询、目录绑定、词汇快照或变换改变时会重新匹配和构造结果；同一资源
的原生字段仍可安全复用。返回数组是独立副本，调用方修改或关闭会话不会改变
已返回结果。会话不共享打开的文件句柄，也不管理 IndexStore 的磁盘索引。

缓存键包含解析路径、文件 size/mtime_ns/device/inode 指纹、索引策略与目录；
``hash_resources=True`` 还包含文件 SHA256。每次读取前后核对资源版本，
变化时删除旧条目并重新定位/解码；默认 stat 指纹不能识别相同元数据的原地
改写。LRU 容量由 ``max_resources``、``max_fields``（metadata 字段数量）与
``max_bytes``（缓存值数组的 ``nbytes``）共同约束。超出容量的单个文件或字段
可正常读取，但不留在缓存。``cache_info`` 报告当前容量、命中、未命中、淘汰
和关闭状态；``clear`` 清空条目，保留会话累计计数；``close`` 后读取失败，
已返回的数组仍有效。同步异常和取消会释放本次 ecCodes 消息；批量结果只在
全部作业成功后返回。

首版会话只支持本地绑定；未核验版本的天擎资源不进入此缓存。需要跨进程
索引复用时使用已有 ``index_policy="auto"`` 和显式 ``index_dir``。同一会话
不提供并发访问保证，由调用方管理其生命周期。
