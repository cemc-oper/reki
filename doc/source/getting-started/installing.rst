安装
#########

.. _dependencies:

依赖库
-------

``reki`` 使用 eccodes 解码 GRIB 数据，请安装 ecCodes 的 Python API 接口。
推荐使用 ``conda`` 安装，conda 会自动完成 ecCodes python 接口的依赖包安装：

.. code-block:: bash

    conda install -c conda-forge eccodes

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

如果使用系统安装的 Python 环境且没有管理员权限，例如在 CMA-PI 上使用 ``apps/python/3.6.3/gnu`` 环境，请在运行 ``pip`` 命令时添加 ``--user`` 参数将 Python 包安装到用户目录。

.. _cma_pi:

CMA-PI
--------

本项目部分功能已在中国气象局 CMA-PI 高性能计算机上进行测试，使用如下环境：

.. code-block:: bash

    # module load compiler/intel/composer_xe_2018.1.163
    module load apps/eccodes/2.17.0/intel
    module load apps/python/3.6.3/gnu

安装 reki 前需要单独安装依赖库 eccodes-python，可以使用下面的命令安装。

.. code-block:: bash

    pip install --user /g11/wangdp/lib/python/reki-install/attrs-19.3.0-py2.py3-none-any.whl
    pip install --user /g11/wangdp/lib/python/reki-install/findlibs-0.0.2.tar.gz
    pip install --user /g11/wangdp/lib/python/reki-install/eccodes-1.3.3.tar.gz

CMA-PI 上已保存 reki 的最新版本，使用下面的命令将软件包安装到用户目录。

.. code-block:: bash

    pip install --user /g11/wangdp/project/work/data/tool/reki
