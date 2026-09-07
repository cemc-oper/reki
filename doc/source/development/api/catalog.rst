数据集目录与 CLI
================

Catalog 解析不执行 I/O。CLI 的参数和退出语义由 ``reki --help`` 定义；这里记录公开
命令组和绑定 API。

.. automodule:: reki.catalog
   :members:
   :member-order: bysource

命令
----

``reki catalog list``、``reki catalog show DATASET_ID`` 和
``reki catalog resolve DATASET_ID`` 分别列出、查看和解析数据集。``--no-user`` 与
``--no-plugins`` 控制配置层；命令失败时输出 Click 错误并使用非零退出码。
