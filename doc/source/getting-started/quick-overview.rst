快速开始
#########

介绍 reki 库的一些常用示例。

首先导入需要使用的一些库。

.. code-block:: pycon

    >>> import numpy as np
    >>> import pandas as pd
    >>> import xarray as xr

.. _data_find:

文件查找
===========

可以使用内置的配置文件从多种途径获取 CMA 天气模式业务系统产品文件目录，包括：

- CMA-PI 高性能计算机
- CMA 二级存储 (挂载到 Linux 服务器)
- CEMC 共享存储 (支持挂载到 Windows 桌面电脑)

下面代码在 CMA-PI 中获取 GRAPES GFS 系统 2021 年 10 月 14 日 00 时次 024 时效的原始分辨率 GRIB 2 文件路径。

.. code-block:: pycon

    >>> from reki.data_finder import find_local_file
    >>> file_path = find_local_file(
    ...     "grapes_gfs_gmf/grib2/orig",
    ...     start_time="2021101400",
    ...     forecast_time="24h"
    ... )
    >>> file_path
    PosixPath('/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2021101400/ORIG/gmf.gra.2021101400024.grb2')

``find_local_file`` 函数接收任意在配置文件中引入的自定义参数，例如使用 ``number`` 参数指定集合预报的成员编号。

下面代码从 CEMC 共享存储中获取 GRAPES GEPS 系统第 20 个成员 2021 年 10 月 14 日 12 时次 048 时效的原始分辨率 GRIB 2 文件路径。

.. Note::
    使用 ``storage_base`` 参数指定挂载盘符，本文档中 CEMC 共享存储挂载到 Windows 的 M: 盘符下。

.. code-block:: pycon

    >>> find_local_file(
    ...     "grapes_geps/grib2/orig",
    ...     start_time=pd.to_datetime("2021-10-14 12:00:00"),
    ...     forecast_time=pd.Timedelta(hours=48),
    ...     number=20,
    ...     storage_base="M:"
    ... )
    WindowsPath('M:/GRAPES_GEPS/Prod-grib/2021101412/grib2/gef.gra.020.2021101412048.grb2')


下面代码从二级存储中获取 GRAPES GFS 系统 2021 年 10 月 14 日 00 时次检索的 RSING 观测资料，观测时间为 10 月 13 日 23 点。

.. Note::
    使用 ``data_level`` 参数指定存储级别，``storage`` 表示归档存储，即二级存储 (/sstorage1)。

.. code-block:: pycon

    >>> find_local_file(
    ...     data_type="grapes_gfs_gmf/obs/rsing",
    ...     start_time="2021101400",
    ...     data_level="storage",
    ...     obs_time=pd.to_datetime("2021-10-13 23:00:00")
    ... )
    PosixPath('/sstorage1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Obs-prep/2021101400/rec_RSING_20211013212300_g.dat')

.. _data_load:

数据加载
=========


.. _grib:

GRIB 2
--------

**reki** 使用 ecCodes 解码 GRIB 数据，提供两套 API 接口用于从 GRIB 文件中提取要素场：

* GRIB 消息：返回 ecCodes 使用的 GRIB Handler
* GRIB 要素场：返回 ``xarray.DataArray``

.. _grib_message:

加载 GRIB 2 消息
~~~~~~~~~~~~~~~~~~

下面代码以 GRAPES GFS 系统的预报文件作为示例文件

.. code-block:: pycon

    >>> from reki.data_finder import find_local_file
    >>> data_path = find_local_file(
    ...     "grapes_gfs_gmf/grib2/orig",
    ...     start_time="2021101500",
    ...     forecast_time="24h",
    ... )
    >>> data_path
    PosixPath('/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2021101500/ORIG/gmf.gra.2021101500024.grb2')

从文件中检索 850hPa 温度场

.. code-block:: pycon

    >>> from reki.format.grib.eccodes import load_message_from_file
    >>> t850 = load_message_from_file(
    ...     data_path,
    ...     parameter="t",
    ...     level_type="pl",
    ...     level=850,
    ... )
    >>> t850
    94384982006640

返回对象 ``t850`` 是 ecCodes 内部使用的 GRIB 消息，可以使用 ecCodes 的 API 接口获取 GRIB 2 消息的属性和数据。

获取要素场属性：

.. code-block:: pycon

    >>> import eccodes
    >>> print("shortName:   ", eccodes.codes_get(t850, "shortName"))
    shortName:    t
    >>> print("typeOfLevel: ", eccodes.codes_get(t850, "typeOfLevel"))
    typeOfLevel:  isobaricInhPa
    >>> print("level:       ", eccodes.codes_get(t850, "level"))
    level:        850

获取要素场数据：

.. code-block:: pycon

    >>> values = eccodes.codes_get_double_array(t850, "values")
    >>> values = values.reshape([720, 1440])
    >>> values
    array([[256.42785156, 256.40785156, 256.41785156, ..., 256.43785156,
            256.44785156, 256.43785156],
           [256.51785156, 256.51785156, 256.51785156, ..., 256.51785156,
            256.50785156, 256.50785156],
           [256.58785156, 256.58785156, 256.57785156, ..., 256.59785156,
            256.59785156, 256.59785156],
           ...,
           [232.83785156, 232.84785156, 232.83785156, ..., 232.83785156,
            232.83785156, 232.84785156],
           [233.23785156, 233.24785156, 233.29785156, ..., 233.21785156,
            233.22785156, 233.26785156],
           [233.78785156, 233.84785156, 233.78785156, ..., 233.79785156,
            233.66785156, 233.66785156]])

.. WARNING::
    需要手动调用 ``eccodes.codes_release`` 释放消息对象。

.. code-block::

    >>> eccodes.codes_release(t850)

.. _grib_field:

加载 GRIB 2 要素场
~~~~~~~~~~~~~~~~~~~~

**reki** 还提供对上述检索得到 GRIB 2 消息的封装，返回 ``xarray.DataArray`` 对象，类似 [cfgrib](https://github.com/ecmwf/cfgrib) 库。

.. code-block:: pycon

    >>> from reki.format.grib.eccodes import load_field_from_file
    >>> t850 = load_field_from_file(
    ...     data_path,
    ...     parameter="t",
    ...     level_type="pl",
    ...     level=850,
    ... )
    >>> t850
    <xarray.DataArray 't' (latitude: 720, longitude: 1440)>
    array([[256.427852, 256.407852, 256.417852, ..., 256.437852, 256.447852,
            256.437852],
           [256.517852, 256.517852, 256.517852, ..., 256.517852, 256.507852,
            256.507852],
           [256.587852, 256.587852, 256.577852, ..., 256.597852, 256.597852,
            256.597852],
           ...,
           [232.837852, 232.847852, 232.837852, ..., 232.837852, 232.837852,
            232.847852],
           [233.237852, 233.247852, 233.297852, ..., 233.217852, 233.227852,
            233.267852],
           [233.787852, 233.847852, 233.787852, ..., 233.797852, 233.667852,
            233.667852]])
    Coordinates:
        time        datetime64[ns] 2021-10-15
        step        timedelta64[ns] 1 days
        valid_time  datetime64[ns] 2021-10-16
        pl          float64 850.0
      * latitude    (latitude) float64 89.88 89.62 89.38 89.12 88.88 88.62 88.38 ...
      * longitude   (longitude) float64 0.0 0.25 0.5 0.75 1.0 1.25 1.5 1.75 2.0 ...
    Attributes:
        GRIB_edition:             2
        GRIB_centre:              babj
        GRIB_subCentre:           0
        GRIB_tablesVersion:       4
        GRIB_localTablesVersion:  0
        GRIB_dataType:            fc
        GRIB_dataDate:            20211015
        GRIB_dataTime:            0
        GRIB_validityDate:        20211016
        GRIB_validityTime:        0
        GRIB_step:                24
        GRIB_stepType:            instant
        GRIB_stepUnits:           1
        GRIB_stepRange:           24
        GRIB_endStep:             24
        long_name:                discipline=0 parmcat=0 parm=0

``t850`` 对象已对 GRIB 2 消息进行解码，包含两个维度：

* ``latitude``：纬度
* ``longitude``：经度

同时包含另外四个坐标，因为仅有单个文件，所以坐标只有单个值：

* ``time``：起报时间
* ``step``：预报时长
* ``valid_time``：预报时间
* ``pl``：层次，``pl`` 表示等压面层

可以使用 xarray 库提供的一系列工具对数据进行处理。
比如，求纬向平均值：

.. code-block:: pycon

    >>> t850.mean(dim="longitude")
    <xarray.DataArray 't' (latitude: 720)>
    array([256.444428, 256.473713, 256.525643, ..., 234.457449, 234.342393,
           234.335428])
    Coordinates:
        time        datetime64[ns] 2021-10-15
        step        timedelta64[ns] 1 days
        valid_time  datetime64[ns] 2021-10-16
        pl          float64 850.0
      * latitude    (latitude) float64 89.88 89.62 89.38 89.12 88.88 88.62 88.38 ...

加载模式层 GRIB 2 要素场

.. code-block:: pycon

    >>> model_file_path = find_local_file(
    ...     "grapes_gfs_gmf/grib2/modelvar",
    ...     start_time="2021101400",
    ...     forecast_time="24h",
    ... )
    >>> data_array = load_field_from_file(
    ...     file_path=model_file_path,
    ...     parameter="t",
    ...     level_type="ml",
    ...     level=60,
    ... )
    >>> data_array
    <xarray.DataArray 't' (latitude: 720, longitude: 1440)>
    array([[216.229266, 216.227266, 216.227266, ..., 216.228266, 216.228266,
            216.229266],
           [216.272266, 216.271266, 216.271266, ..., 216.274266, 216.274266,
            216.272266],
           [216.264266, 216.263266, 216.261266, ..., 216.268266, 216.267266,
            216.266266],
           ...,
           [197.408266, 197.410266, 197.412266, ..., 197.399266, 197.402266,
            197.404266],
           [197.529266, 197.530266, 197.532266, ..., 197.523266, 197.526266,
            197.527266],
           [197.602266, 197.603266, 197.604266, ..., 197.600266, 197.601266,
            197.601266]])
    Coordinates:
        time        datetime64[ns] 2021-10-14
        step        timedelta64[ns] 1 days
        valid_time  datetime64[ns] 2021-10-15
        ml          int64 60
      * latitude    (latitude) float64 89.88 89.62 89.38 89.12 88.88 88.62 88.38 ...
      * longitude   (longitude) float64 0.0 0.25 0.5 0.75 1.0 1.25 1.5 1.75 2.0 ...
    Attributes:
        GRIB_edition:             2
        GRIB_centre:              babj
        GRIB_subCentre:           0
        GRIB_tablesVersion:       4
        GRIB_localTablesVersion:  0
        GRIB_dataType:            fc
        GRIB_dataDate:            20211014
        GRIB_dataTime:            0
        GRIB_validityDate:        20211015
        GRIB_validityTime:        0
        GRIB_step:                24
        GRIB_stepType:            instant
        GRIB_stepUnits:           1
        GRIB_stepRange:           24
        GRIB_endStep:             24
        long_name:                discipline=0 parmcat=0 parm=0

返回数据中层次坐标名为 ``ml``，表示模式层。

.. _grads:

GrADS 格点二进制数据
---------------------

**reki** 内置简单的 GrADS 格点二进制格式数据文件解析器。

使用 ``find_local_file()`` 获取 GRAPES GFS 系统等压面 GrADS 数据文件路径，返回数据描述文件路径：

.. code-block:: pycon

    >>> postvar_file_path = find_local_file(
    ...     "grapes_gfs_gmf/bin/postvar_ctl",
    ...     start_time="2021101500",
    ...     forecast_time="36h",
    ... )
    >>> postvar_file_path
    PosixPath('/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Fcst-long/2021101500/post.ctl_2021101500_036')

加载 850hPa 温度场

.. code-block:: pycon

    >>> from reki.format.grads import load_field_from_file
    >>> load_field_from_file(
    ...     postvar_file_path,
    ...     parameter="t",
    ...     level_type="pl",
    ...     level=850
    ... )
    <xarray.DataArray 't' (latitude: 720, longitude: 1440)>
    array([[256.28766, 256.28326, 256.29086, ..., 256.2877 , 256.29395, 256.2932 ],
           [256.28036, 256.27902, 256.27872, ..., 256.28076, 256.2761 , 256.27777],
           [256.28793, 256.28992, 256.28824, ..., 256.28506, 256.286  , 256.28528],
           ...,
           [234.0174 , 234.04938, 234.06163, ..., 234.06227, 234.08116, 234.07538],
           [234.26164, 234.24377, 234.23071, ..., 234.22185, 234.24457, 234.25938],
           [234.50842, 234.471  , 234.43414, ..., 234.57632, 234.54097, 234.49728]],
          dtype=float32)
    Coordinates:
      * latitude       (latitude) float64 89.88 89.62 89.38 89.12 88.88 88.62 ...
      * longitude      (longitude) float64 0.0 0.25 0.5 0.75 1.0 1.25 1.5 1.75 ...
        pl             int64 850
        valid_time     datetime64[ns] 2021-10-16T12:00:00
        start_time     datetime64[ns] 2021-10-15
        forecast_time  timedelta64[ns] 1 days 12:00:00
    Attributes:
        description:  temperature

**reki** 支持单一描述文件对应多个数据文件。
GRAPES TYM 等压面 GrADS 数据每个时次只有一个描述文件，对应多个单时效二进制数据文件。
获取 POSTVAR 文件路径：

.. code-block:: pycon

    >>> postvar_file_path = find_local_file(
    ...     "grapes_tym/bin/postvar_ctl",
    ...     start_time="2021101400",
    ... )
    >>> postvar_file_path
    PosixPath('/g1/COMMONDATA/OPER/NWPC/GRAPES_TYM/Fcst-main/2021101400/post.ctl_2021101400')

CTL 文件名只包含起报日期 (2021.09.26) 和起报时次 (00)。
加载海平面气压：

.. code-block:: pycon

    >>> load_field_from_file(
    ...     postvar_file_path,
    ...     parameter="psl",
    ...     level_type="single",
    ... )
    We can't recognize ctl file name.
    <xarray.DataArray 'psl' (latitude: 835, longitude: 1557)>
    array([[1016.1363 , 1016.17535, 1016.2182 , ..., 1005.5745 , 1005.60333,
            1005.62775],
           [1016.171  , 1016.21216, 1016.25354, ..., 1005.51605, 1005.54626,
            1005.57404],
           [1016.2113 , 1016.25037, 1016.2875 , ..., 1005.4542 , 1005.48773,
            1005.51746],
           ...,
           [1013.8922 , 1013.8431 , 1013.8072 , ..., 1010.9525 , 1010.94916,
            1010.954  ],
           [1013.84155, 1013.8077 , 1013.76   , ..., 1010.96796, 1010.95734,
            1010.95685],
           [1013.80206, 1013.7625 , 1013.7305 , ..., 1010.9776 , 1010.9665 ,
            1010.96265]], dtype=float32)
    Coordinates:
      * latitude    (latitude) float64 60.06 59.97 59.88 59.79 59.7 59.61 59.52 ...
      * longitude   (longitude) float64 40.0 40.09 40.18 40.27 40.36 40.45 40.54 ...
        level       float64 0.0
        valid_time  datetime64[ns] 2021-10-14
    Attributes:
        description:  sea level pressure

.. _other_formats:

其他格式
------------

**reki** 还提供对 NetCDF、CSV 等格式数据的简单支持。

.. _netcdf:

NetCDF
~~~~~~~~~

**reki** 内部使用 xarray 提供的接口读取 NetCDF 文件。

查找 HRCLDAS 文件目录

.. code-block:: pycon

    >>> from reki.data_finder import find_local_files
    >>> file_paths = find_local_files(
    ...     data_type="obs/grid/HRCLDAS/chn/1km",
    ...     start_time=pd.Timestamp("2021-02-05 00:00:00"),
    ...     data_class="smart2022",
    ...     parameter="DPT"
    ... )
    >>> file_path = file_paths[0]
    >>> file_path
    PosixPath('/g11/nwpc_ep3/SMART2022/OBS/grid/HRCLDAS/20210205/00/Z_NAFP_C_BABJ_20210205000916_P_HRCLDAS_RT_CHN_0P01_HOR-DPT-2021020500.nc')

加载露点温度场

.. code-block:: pycon

    >>> from reki.format.netcdf import load_field_from_file
    >>> load_field_from_file(file_path)
    <xarray.DataArray 'DAIR' (LAT: 4500, LON: 7000)>
    [31500000 values with dtype=float32]
    Coordinates:
      * LON      (LON) float32 70.03125 70.04125 70.05125 70.06125 70.07125 ...
      * LAT      (LAT) float32 15.03125 15.04125 15.05125 15.06125 15.07125 ...
    Attributes:
        _Fillvalue:  -999.0

.. _table:

表格数据
~~~~~~~~~

**reki** 内部使用 ``pandas.read_table()`` 函数解析表格数据。

查找观测资料路径

.. code-block:: pycon

    >>> file_path = find_local_file(
    ...     data_type="grapes_gfs_gmf/obs/rgwst",
    ...     start_time="2021080400",
    ...     data_level="storage",
    ...     storage_base="M:",
    ...     obs_time=pd.to_datetime("2021-08-03 23:00:00")
    ... )
    >>> file_path
    WindowsPath('M:/GRAPES_GFS_GMF/Obs-prep/2021080400/rec_RSURF_20210803212300_g.dat')

加载表格数据

.. NOTE::
    非真实数据，仅用于展示 API 用法。

.. code-block:: pycon

    >>> from reki.format.table import load_nwpc_obs_from_file
    >>> load_nwpc_obs_from_file(file_path)
          Station_Id_C  Station_Id_d     Lat  ...  Q_WIN_D  Q_WIN_S            obs_time
    01001         0.00             0       0  ...      8.0      0.0 2021-08-03 23:00:00
    01003         0.00             0       0  ...      8.0      0.0 2021-08-03 23:00:00
                ...           ...     ...  ...      ...      ...                 ...
    N259     999999.00             0       0  ...      8.0      8.0 2021-08-03 23:00:00
    [8505 rows x 25 columns]


.. _data_process:

数据处理
===========

``reki.operator`` 包中集成多种用于数据操作的函数，函数名称参考 esmvalcore 库设计。

.. _extract_region:

裁剪区域
---------

查找 GRAPES TYM 系统的数据文件：

.. code-block:: pycon

    >>> data_path = find_local_file(
    ...     "grapes_tym/grib2/orig",
    ...     start_time="2021101400",
    ...     forecast_time=f"72h"
    ... )
    >>> data_path
    PosixPath('/g1/COMMONDATA/OPER/NWPC/GRAPES_TYM/Prod-grib/2021101400/ORIG/rmf.tcgra.2021101400072.grb2')

加载总降水要素场：

.. code-block:: pycon

    >>> from reki.format.grib.eccodes import load_field_from_file
    >>> field = load_field_from_file(
    ...     data_path,
    ...     parameter="APCP",
    ... )
    >>> field
    <xarray.DataArray 'unknown' (latitude: 835, longitude: 1557)>
    array([[2.691072e+00, 2.691680e+00, 2.578080e+00, ..., 4.035200e-01,
            4.257920e-01, 4.250880e-01],
           [2.688864e+00, 2.687904e+00, 2.576672e+00, ..., 1.083616e+00,
            1.140576e+00, 4.247360e-01],
           [2.628544e+00, 2.625728e+00, 2.523136e+00, ..., 1.409056e+00,
            1.418176e+00, 8.219840e-01],
           ...,
           [2.752320e-01, 2.730880e-01, 2.048000e-03, ..., 4.160000e-03,
            0.000000e+00, 0.000000e+00],
           [6.873600e-02, 6.672000e-02, 5.440000e-04, ..., 1.344000e-03,
            0.000000e+00, 0.000000e+00],
           [6.883200e-02, 6.876800e-02, 5.120000e-04, ..., 2.880000e-04,
            0.000000e+00, 0.000000e+00]])
    Coordinates:
        time        datetime64[ns] 2021-10-14
        step        timedelta64[ns] 3 days
        valid_time  datetime64[ns] 2021-10-17
        surface     int64 0
      * latitude    (latitude) float64 60.06 59.97 59.88 59.79 59.7 59.61 59.52 ...
      * longitude   (longitude) float64 40.0 40.09 40.18 40.27 40.36 40.45 40.54 ...
    Attributes:
        GRIB_edition:             2
        GRIB_centre:              babj
        GRIB_subCentre:           0
        GRIB_tablesVersion:       4
        GRIB_localTablesVersion:  0
        GRIB_dataType:            fc
        GRIB_dataDate:            20211014
        GRIB_dataTime:            0
        GRIB_validityDate:        20211017
        GRIB_validityTime:        0
        GRIB_step:                72
        GRIB_stepType:            accum
        GRIB_stepUnits:           1
        GRIB_stepRange:           0-72
        GRIB_endStep:             72
        long_name:                discipline=0 parmcat=1 parm=8

抽取区域：

.. code-block:: pycon

    >>> from reki.operator import extract_region
    >>> extract_region(
    ...     field,
    ...     start_longitude=103,
    ...     end_longitude=126.875,
    ...     start_latitude=47,
    ...     end_latitude=35.125
    ... )
    <xarray.DataArray 'unknown' (latitude: 132, longitude: 266)>
    array([[0.000000e+00, 3.200000e-05, 6.400000e-05, ..., 1.766176e+00,
            1.687872e+00, 1.587904e+00],
           [0.000000e+00, 3.200000e-05, 1.920000e-04, ..., 1.495584e+00,
            1.446816e+00, 1.388576e+00],
           [0.000000e+00, 0.000000e+00, 3.200000e-05, ..., 1.416800e+00,
            1.425824e+00, 1.451200e+00],
           ...,
           [1.693475e+01, 1.831757e+01, 1.882371e+01, ..., 2.187318e+01,
            2.305267e+01, 2.425610e+01],
           [1.351926e+01, 1.441987e+01, 1.540243e+01, ..., 2.254189e+01,
            2.355629e+01, 2.409763e+01],
           [1.065578e+01, 1.181683e+01, 1.347645e+01, ..., 2.282579e+01,
            2.337466e+01, 2.367184e+01]])
    Coordinates:
        time        datetime64[ns] 2021-10-14
        step        timedelta64[ns] 3 days
        valid_time  datetime64[ns] 2021-10-17
        surface     int64 0
      * latitude    (latitude) float64 46.92 46.83 46.74 46.65 46.56 46.47 46.38 ...
      * longitude   (longitude) float64 103.0 103.1 103.2 103.3 103.4 103.5 ...
    Attributes:
        GRIB_edition:             2
        GRIB_centre:              babj
        GRIB_subCentre:           0
        GRIB_tablesVersion:       4
        GRIB_localTablesVersion:  0
        GRIB_dataType:            fc
        GRIB_dataDate:            20211014
        GRIB_dataTime:            0
        GRIB_validityDate:        20211017
        GRIB_validityTime:        0
        GRIB_step:                72
        GRIB_stepType:            accum
        GRIB_stepUnits:           1
        GRIB_stepRange:           0-72
        GRIB_endStep:             72
        long_name:                discipline=0 parmcat=1 parm=8

.. _extract_point:

抽取数据点
------------

查找 GRAPES MESO 3KM 系统的数据文件：

.. code-block:: pycon

    >>> data_path = find_local_file(
    ...     "grapes_meso_3km/grib2/orig",
    ...     start_time="2021101400",
    ...     forecast_time=f"6h"
    ... )
    >>> data_path
    PosixPath('/g1/COMMONDATA/OPER/NWPC/GRAPES_MESO_3KM/Prod-grib/2021101400/ORIG/rmf.hgra.2021101400006.grb2')

加载总云量要素场：

.. code-block:: pycon

    >>> from reki.format.grib.eccodes import load_field_from_file
    >>> field = load_field_from_file(
    ...     data_path,
    ...     parameter="TCDC",
    ... )

提取特定点数据：

.. code-block:: pycon

    >>> from reki.operator.regrid import extract_point
    >>> extract_point(
    ...     field,
    ...     39.9,
    ...     116.3906,
    ...     scheme="nearest",
    ...     engine="scipy",
    ... )
    <xarray.DataArray (latitude: 1, longitude: 1)>
    array([[100.]])
    Coordinates:
        time        datetime64[ns] 2021-10-14
        step        timedelta64[ns] 06:00:00
        valid_time  datetime64[ns] 2021-10-14T06:00:00
        nominalTop  int64 0
      * latitude    (latitude) float64 39.9
      * longitude   (longitude) float64 116.4

.. _interpolate_grid:

插值
-----

查找 GRAPES GFS 系统的数据文件：

.. code-block:: pycon

    >>> data_path = find_local_file(
    ...     "grapes_gfs_gmf/grib2/orig",
    ...     start_time="2021101412",
    ...     forecast_time="120h"
    ... )
    >>> data_path
    PosixPath('/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2021101412/ORIG/gmf.gra.2021101412120.grb2')

加载 2 米温度场：

.. code-block:: pycon

    >>> field = load_field_from_file(
    ...     data_path,
    ...     parameter="2t",
    ... )

构建目标网格：

.. Note::
    下面代码在 CMA-PI 的 apps/python/3.6.3/gnu 环境下运行，该环境安装的 Xarray 不支持默认 ``data`` 参数。高版本 Xarray 可以省去 ``data``。

.. code-block:: pycon

    >>> lats = np.arange(89.95, -90, -0.1)
    >>> lons = np.arange(0, 360, 0.1)
    >>> target_grid = xr.DataArray(
    ...     data=np.zeros((len(lats), len(lons))),
    ...     coords=[
    ...         ("latitude", lats),
    ...         ("longitude", lons)
    ...     ]
    ... )
    >>> target_grid
    <xarray.DataArray (latitude: 1800, longitude: 3600)>
    array([[0., 0., 0., ..., 0., 0., 0.],
           [0., 0., 0., ..., 0., 0., 0.],
           [0., 0., 0., ..., 0., 0., 0.],
           ...,
           [0., 0., 0., ..., 0., 0., 0.],
           [0., 0., 0., ..., 0., 0., 0.],
           [0., 0., 0., ..., 0., 0., 0.]])
    Coordinates:
      * latitude   (latitude) float64 89.95 89.85 89.75 89.65 89.55 89.45 89.35 ...
      * longitude  (longitude) float64 0.0 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 ...

将要素场 ``field`` 插值到目标网格 ``target_grid``：

.. Note::
    ``scheme="rect_bivariate_spline"`` 使用 ``scipy.interpolate.RectBivariateSpline`` 插值，需要安装 scipy 库。

.. code-block:: pycon

    >>> from reki.operator.regrid import interpolate_grid
    >>> interpolate_grid(
    ...     field,
    ...     target_grid,
    ...     scheme="rect_bivariate_spline"
    ... )
    <xarray.DataArray (latitude: 1800, longitude: 3600)>
    array([[250.285742, 250.280388, 250.270665, ..., 250.277346, 250.285742,
            250.285742],
           [250.266565, 250.268475, 250.260678, ..., 250.25966 , 250.271709,
            250.271709],
           [250.220353, 250.241045, 250.24047 , ..., 250.220512, 250.235493,
            250.235493],
           ...,
           [228.673176, 229.045389, 229.242601, ..., 229.269594, 229.277293,
            229.277293],
           [228.531412, 228.908711, 229.104475, ..., 229.072642, 229.085329,
            229.085329],
           [228.485742, 228.85362 , 229.042281, ..., 228.990476, 229.005742,
            229.005742]])
    Coordinates:
        time               datetime64[ns] 2021-10-14T12:00:00
        step               timedelta64[ns] 5 days
        valid_time         datetime64[ns] 2021-10-19T12:00:00
        heightAboveGround  int64 2
      * latitude           (latitude) float64 89.95 89.85 89.75 89.65 89.55 ...
      * longitude          (longitude) float64 0.0 0.1 0.2 0.3 0.4 0.5 0.6 0.7 ...