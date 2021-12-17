.. reki documentation master file, created by
   sphinx-quickstart on Fri Oct 15 10:31:48 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

欢迎来到 reki 文档
================================

**reki** (前称 **nwpc-data**) 是为 CMA 天气模式开发的数据访问 Python 开源工具库，提供检索要素场的便捷方法。

reki 支持 GRIB、GrADS、NetCDF、CSV 等多种数据格式，对接中国气象局 CMA-PI 高性能计算机、二级存储等多种数据来源，可在 Windows、Linux 等环境中运行。
reki 提供区域截取、插值等多种数据操作方法。

开始使用
==========

.. toctree::
   :maxdepth: 2

   getting-started/index

用户指南
==========

本章节提供 **reki** 库更详细的说明和示例，介绍 **reki** 库可以实现的常见功能。

.. toctree::
   :maxdepth: 2

   usage/data_find
   usage/data_load
   usage/data_process


索引和表格
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`