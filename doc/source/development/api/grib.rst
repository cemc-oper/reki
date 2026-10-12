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
原生 GRIB shortName 的映射；选择成员时还须提供 ID 到角色的映射。未核验的层次、
网格和 coverage 条件报 ``unsupported``。

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
