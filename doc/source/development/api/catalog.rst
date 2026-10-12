数据集目录与 CLI
================

Catalog 解析不执行 I/O。CLI 的参数和退出语义由 ``reki --help`` 定义；这里记录公开
命令组和绑定 API。

.. automodule:: reki.catalog
   :members:
   :member-order: bysource

公共查询的静态绑定
----------------

``reki.catalog.query_binding`` 将调用方明确给定的目录快照转换为公共
``cedarkit-query`` Binding。``builtin_catalog_snapshot()`` 只装载打包的内置目录，
不读取插件或用户目录。需要覆盖层时，先按现有优先级调用 ``load_catalog()``，
再用 ``CatalogSnapshot(catalog, version)`` 固定已选目录与版本。

``plan_source_binding(query, snapshot=...)`` 只解析配置，不检查文件或调用服务。
它返回规范 Query、受控 Binding、各自的身份，以及保留覆盖链的来源诊断；
``to_display_dict()`` 省略可执行 locator 和用户目录路径。使用内置 ``local``
来源时必须显式传入 ``local_config_version``；这只是配置版本声明，资料可用性仍须
在后续定位步骤核实。新 Query 中的目录别名写为
``{"namespace":"reki-catalog","name":"CMA-GFS-CMADaaS"}``，裸字符串只表示稳定 ID。

.. automodule:: reki.catalog.query_binding
   :members:
   :member-order: bysource

命令
----

``reki catalog list``、``reki catalog show DATASET_ID`` 和
``reki catalog resolve DATASET_ID`` 分别列出、查看和解析数据集。``--no-user`` 与
``--no-plugins`` 控制配置层；命令失败时输出 Click 错误并使用非零退出码。
