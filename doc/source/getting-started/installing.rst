安装
#########

.. _dependencies:

依赖库
-------

``reki`` 使用 ecCodes 解码 GRIB 数据。PyPI 上的 ``eccodes`` wheel 包
自带 ecCodes 二进制库，pip 安装即可，无需单独安装系统库：

.. code-block:: bash

    python -m pip install eccodes

也可以使用 conda 安装：

.. code-block:: bash

    conda install -c conda-forge eccodes

可选依赖：

- ``reki[cmadaas]``：CMADaaS MUSIC 服务数据源（``nuwe-cmadaas``）
- ``reki[lazy]``：惰性加载（``dask``）

.. _install_reki:

安装 reki
-----------

使用 pip 在线安装：

.. code-block:: bash

    python -m pip install reki

从 Github 中下载最新的源代码：

.. code-block:: bash

    git clone https://github.com/cemc-oper/reki
    cd reki

使用 ``pip`` 命令安装：

.. code-block:: bash

    pip install .
