import io

import pandas as pd


_CEMC_PARAM_TABLE_CONTENT = """name,unit,description,description_cn,discipline,category,number,typeOfLevel,level,first_level_type,first_level,second_level_type,second_level,stepType,alias
ps,Pa,Surface pressure,地面气压,0.0,3.0,0.0,surface,,1.0,,,,,False
psfc,Pa,Surface pressure,地面气压,0.0,3.0,0.0,surface,,1.0,,,,,True
psl,Pa,Sea level pressure,海平面气压,0.0,3.0,1.0,meanSea,,101.0,,,,,False
pi,,Exner pressure,Exner气压,0.0,3.0,26.0,,,,,,,,False
h,Gpm,Geopotential height,位势高度,0.0,3.0,5.0,,,100.0,,,,,False
zs,Gpm,Terrain ,地形高度,0.0,3.0,5.0,surface,,1.0,,,,,False
t,K,Temperature,温度,0.0,0.0,0.0,,,,,,,,False
t2m,K,Temperature at 2 meters height,2米温度,0.0,0.0,0.0,heightAboveGround,2.0,103.0,2.0,,,,False
ts,K,Surface temperature,地面温度,0.0,0.0,0.0,surface,,1.0,,,,,False
tsfc,K,Surface temperature,地面温度,0.0,0.0,0.0,surface,,1.0,,,,,True
thetaSe,K,Pseudo-equivalent potential temperature,假相当位温,0.0,0.0,3.0,,,,,,,,False
mx2t,K,Maximum of 2 meters high temperature,2米最高温度,0.0,0.0,4.0,heightAboveGround,2.0,103.0,2.0,,,max,False
tmax2m,K,Maximum of 2 meters high temperature,2米最高温度,0.0,0.0,4.0,heightAboveGround,2.0,103.0,2.0,,,max,True
mn2t,K,Minimum of 2 meters high temperature,2米最低温度,0.0,0.0,5.0,heightAboveGround,2.0,103.0,2.0,,,min,False
tmin2m,K,Minimum of 2 meters high temperature,2米最低温度,0.0,0.0,5.0,heightAboveGround,2.0,103.0,2.0,,,min,True
td,K,Dew point,露点温度,0.0,0.0,6.0,,,,,,,,False
td2m,K,2 meters high Dew point,2米露点温度,0.0,0.0,6.0,heightAboveGround,2.0,103.0,2.0,,,,False
ttd,K,Dew point depression,温度露点差,0.0,0.0,7.0,,,,,,,,False
vis,m,Visibility,能见度,0.0,19.0,0.0,surface,,1.0,,,,,False
pli,K,Parcel lifted index(to 500 hpa),气块抬升指数,0.0,7.0,0.0,surface,,1.0,,,,,False
u,m/s,U-component of wind,东西风,0.0,2.0,2.0,,,,,,,,False
u10m,m/s,V-component of wind at 10 meters height,10米东西风,0.0,2.0,2.0,heightAboveGround,10.0,103.0,10.0,,,instant,False
u10mmax#3,m/s,Maximum of u10m during 3 hours,3小时最大10米东西风,0.0,2.0,2.0,heightAboveGround,10.0,103.0,10.0,,,max,False
v,m/s,V-component of wind,南北风,0.0,2.0,3.0,,,,,,,,False
v10m,m/s,V-component of wind at 10 meters height,10米南北风,0.0,2.0,3.0,heightAboveGround,10.0,103.0,10.0,,,instant,False
v10mmax#3,m/s,Maximim of v10m during 3 hours,3小时最大10米南北风,0.0,2.0,3.0,heightAboveGround,10.0,103.0,10.0,,,max,False
w,m/s,Vertical velocity (geometric),等高面垂直速度,0.0,2.0,9.0,,,100.0,,,,,False
wmax#3,m/s,Maximum of w during 3 hours,3小时等高面最大垂直速度,0.0,2.0,9.0,,,100.0,,,,max,False
vor,s-1,Relative vorticity,涡度,0.0,2.0,12.0,,,,,,,,False
div,s-1,Relative divergence,散度,0.0,2.0,13.0,,,,,,,,False
q,kg/kg,Specific humidity,比湿,0.0,1.0,0.0,,,,,,,,False
q2m,kg/kg,Specific humidity at 2 meters height,2米比湿,0.0,1.0,0.0,heightAboveGround,2.0,103.0,2.0,,,,False
rh,%,Relative humidity,相对湿度,0.0,1.0,1.0,,,,,,,,False
rh2m,%,Relative humidity at 2 meters height,2米相对湿度,0.0,1.0,1.0,heightAboveGround,2.0,103.0,2.0,,,,False
pwat,kg/kg,Precipitable water,整层可降水量,0.0,1.0,3.0,atmosphere,,10.0,,,,,False
rain,mm,Total precipitation,总累计降水,0.0,1.0,8.0,surface,,1.0,,,,accum,False
rainnc,mm,Large scale precipitation,大尺度降水,0.0,1.0,9.0,surface,,1.0,,,,accum,False
rainc,mm,Convective precipitation,对流性降水,0.0,1.0,10.0,surface,,1.0,,,,accum,False
sf,m,Snow melt  ,降雪,0.0,1.0,29.0,surface,,1.0,,,,accum,False
snow,m,Snow melt  ,降雪,0.0,1.0,29.0,surface,,1.0,,,,accum,True
sd,m,Snow depth  ,雪深,0.0,1.0,11.0,surface,,1.0,,,,,False
tcc,%,Total cloud cover,总云量,0.0,6.0,1.0,entireAtmosphere,,,,,,,False
lcc,%,Low cloud cover,低云量,0.0,6.0,3.0,entireAtmosphere,,,,,,,False
mcc,%,Medium cloud cover,中云量,0.0,6.0,4.0,entireAtmosphere,,,,,,,False
hcc,%,High cloud cover,高云量,0.0,6.0,5.0,entireAtmosphere,,,,,,,False
bli,K,Best lifted index,最优抬升指数,0.0,7.0,1.0,surface,,,,,,,False
albedo,%,Albedo,反射率,0.0,19.0,1.0,surface,,1.0,,,,,False
st,K,Soil temperature,土壤温度,0.0,0.0,0.0,depthBelowLandLayer,,106.0,,,,,False
st(0-10),,,0-10cm土壤温度,0.0,0.0,0.0,depthBelowLandLayer,,106.0,0.0,106.0,0.1,,False
st(10-40),,,10-40cm土壤温度,0.0,0.0,0.0,depthBelowLandLayer,,106.0,0.1,106.0,0.4,,False
st(40-100),,,40-100cm土壤温度,0.0,0.0,0.0,depthBelowLandLayer,,106.0,0.4,106.0,1.0,,False
st(100-200),,,100-200cm土壤温度,0.0,0.0,0.0,depthBelowLandLayer,,106.0,1.0,106.0,2.0,,False
ro,m,Runoff,径流,0.0,1.0,227.0,,,,,,,,False
znt,m,roughness length,粗糙度,0.0,3.0,228.0,surface,,1.0,,,,,False
gsw,w/m2,Net short wave radiation flux,净短波辐射通量|净太阳辐射通量,0.0,4.0,9.0,,,,,,,,False
ssr,w/m2,Net short wave radiation flux,净短波辐射通量|净太阳辐射通量,0.0,4.0,9.0,,,,,,,,True
glw,w/m2,Net long wave radiation flux,净长波辐射通量|净热辐射通量,0.0,5.0,5.0,,,,,,,,False
str,w/m2,Net long wave radiation flux,净长波辐射通量|净热辐射通量,0.0,5.0,5.0,,,,,,,,True
gswc,w/m2,"Net short wave radiation flux, clear sky",晴空地面净短波辐射通量,0.0,4.0,11.0,surface,,1.0,,,,,False
tsw,w/m2,TOE net short wave radiation flux,大气顶净短波辐射通量,0.0,4.0,9.0,nominalTop,,8.0,,,,accum,False
tswc,w/m2,"TOE net short wave radiation flux, clear sky",晴空大气顶净短波辐射通量,0.0,4.0,11.0,nominalTop,,8.0,,,,,False
slhf,ws/m2,Latent heat net flux,潜热辐射,0.0,0.0,10.0,,,,,,,,False
sshf,ws/m2,Sensible heat net flux,感热辐射,2.0,0.0,24.0,,,,,,,,False
saunaidx,,Sauna index,桑拿指数,0.0,0.0,225.0,,,,,,,,False
kidx,C,K index,K指数,0.0,7.0,2.0,meanSea,,101.0,,,,,False
ki,C,K index,K指数,0.0,7.0,2.0,meanSea,,101.0,,,,,True
k,C,K index,K指数,0.0,7.0,2.0,meanSea,,101.0,,,,,True
qflx,1e-1.g/(cm.hpa.s),Moisture flux,水汽通量,0.0,1.0,224.0,,,,,,,,False
qdiv,1e-7.g/(cm2.hpa.s),Moisture flux divergence,水汽通量散度,0.0,1.0,225.0,,,,,,,,False
qfxsfc,kg/(m2.s),Surface moisture flux,地表水汽通量,0.0,1.0,229.0,surface,,1.0,,,,,False
qfx,kg/(m2.s),Surface moisture flux,地表水汽通量,0.0,1.0,229.0,surface,,1.0,,,,,True
sw,m3/m3,Soil moisture,土壤湿度,0.0,1.0,0.0,depthBelowLandLayer,,106.0,,,,,False
sw(0-10),,,0-10cm土壤湿度,0.0,1.0,0.0,depthBelowLandLayer,,106.0,0.0,106.0,0.1,,False
sw(10-40),,,10-40cm土壤湿度,0.0,1.0,0.0,depthBelowLandLayer,,106.0,0.1,106.0,0.3,,False
sw(40-100),,,40-100cm土壤湿度,0.0,1.0,0.0,depthBelowLandLayer,,106.0,0.3,106.0,0.6,,False
sw(100-200),,,100-200cm土壤湿度,0.0,1.0,0.0,depthBelowLandLayer,,106.0,0.6,106.0,1.0,,False
wess,N/m2,West-east surface wind stress,东西向风应力,0.0,2.0,227.0,surface,,1.0,,,,,False
nsss,N/m2,North-south surface wind stress,南北向风应力,0.0,2.0,228.0,surface,,1.0,,,,,False
sweatidx,,Sweat index,强天气胁迫指数,0.0,7.0,5.0,surface,,1.0,,,,,False
sweat,,Sweat index,强天气胁迫指数,0.0,7.0,5.0,surface,,1.0,,,,,True
qc,kg/kg,Cloud mixing ratio,云水混合比,0.0,1.0,22.0,,,,,,,,False
hfx,w/m2,Surface heat flux,地表热通量,0.0,0.0,24.0,surface,,1.0,,,,accum,False
cin,J/kg,Convective inhibition,对流抑制能量,0.0,7.0,7.0,surface,,1.0,,,,,False
cape,J/kg,Convective available potential energy,对流有效位能,0.0,7.0,6.0,surface,,1.0,,,,,False
pc,Pa,Condensation layer pressure,抬升凝结高度,0.0,1.0,228.0,surface,,1.0,,,,,False
rain5max,mm,5-minutes accumulated precipitation,5分钟最大降水,0.0,1.0,241.0,surface,,1.0,,,,max,False
qr,kg/kg,Rain mixing ratio,雨水混合比,0.0,1.0,24.0,,,,,,,,False
qs,kg/kg,Snow mixing ratio,雪水混合比,0.0,1.0,25.0,,,,,,,,False
qi,kg/kg,Ice mixing ratio,冰水混合比,0.0,1.0,23.0,,,,,,,,False
graupel,kg/kg,Graupel,霰,0.0,1.0,32.0,,,,,,,,False
precitype,,Precipitation type,降水相态,0.0,1.0,19.0,,,,,,,,False
mpv1,1e-6.k/(m2.s.kg),Moist potential vorticity(vertical part),湿位涡垂直分量,0.0,2.0,225.0,,,,,,,,False
mpv2,1e-6.k/(m2.s.kg),Moist potential vorticity(horizontal part),湿位涡水平分量,0.0,2.0,226.0,,,,,,,,False
shr,s-1,Vertical speed shear,垂直风切变,0.0,2.0,25.0,,,,,,,,False
shr(0-1000),,,0-1km垂直风切变,0.0,2.0,25.0,heightAboveGroundLayer,1000.0,103.0,1000.0,103.0,0.0,,False
shr(0-3000),,,0-3km垂直风切变,0.0,2.0,25.0,heightAboveGroundLayer,3000.0,103.0,3000.0,103.0,0.0,,False
shr(0-6000),,,0-6km垂直风切变,0.0,2.0,25.0,heightAboveGroundLayer,6000.0,103.0,6000.0,103.0,0.0,,False
shrmax,m/s,maximum vector of vertical wind shear,最大垂直风切变矢量,0.0,2.0,237.0,,,,,,,,False
shrmax(0-600),,,0-600m最大垂直风切变矢量,0.0,2.0,237.0,heightAboveGroundLayer,600.0,103.0,600.0,103.0,0.0,,False
shrmaxdir,degree,direction of maxium vertical wind shear,最大垂直风切变的方向,0.0,2.0,238.0,,,,,,,,False
shrmaxdir(0-600),,,0-600m最大垂直风切变的方向,0.0,2.0,238.0,heightAboveGroundLayer,600.0,103.0,600.0,103.0,0.0,,False
srh,J/kg,Storm relative helicity,风暴螺旋度,0.0,7.0,8.0,,,,,,,,False
srh(0-1000),,,0-1km垂直风暴螺旋度,0.0,7.0,8.0,heightAboveGroundLayer,1000.0,103.0,1000.0,103.0,0.0,,False
srh(0-3000),,,0-3km垂直风暴螺旋度,0.0,7.0,8.0,heightAboveGroundLayer,3000.0,103.0,3000.0,103.0,0.0,,False
uhmax,m2/s2,Updraught helicity,最大上升螺旋度,0.0,7.0,15.0,,,,,,,max,False
uhmax(2000-5000),,,2-5km最大上升螺旋度,0.0,7.0,15.0,heightAboveGroundLayer,5000.0,103.0,5000.0,103.0,2000.0,max,False
src,,Skin reservoir content  ,表面蓄水池含量,0.0,1.0,226.0,,,,,,,,False
pblh,m,Planet boundary layer height,边界层高度,0.0,3.0,18.0,surface,,1.0,,,,,False
gusw,w/m2,Surface upward short-wave radiation flux(surface),地面向上短波辐射通量,0.0,4.0,8.0,surface,,1.0,,,,,False
gswu,w/m2,Surface upward short-wave radiation flux(surface),地面向上短波辐射通量,0.0,4.0,8.0,surface,,1.0,,,,,True
gulw,w/m2,Surface upward long-wave radiation flux(surface),地面向上长波辐射通量,0.0,5.0,4.0,surface,,1.0,,,,,False
gslu,w/m2,Surface upward long-wave radiation flux(surface),地面向上长波辐射通量,0.0,5.0,4.0,surface,,1.0,,,,,True
tusw,w/m2,Upward short-wave radiation flux(top of atmoshpere),大气顶向上（外）短波辐射通量,0.0,4.0,8.0,nominalTop,,8.0,,,,,False
tulw,w/m2,Upward long-wave radiation flux(top of atmoshpere),大气顶向上（外）长波辐射通量,0.0,5.0,4.0,nominalTop,,8.0,,,,,False
gdlwc,w/m2,"Surface downward long-wave radiation flux, clear sky",地面晴空向下长波辐射通量,0.0,5.0,8.0,surface,,1.0,,,,,False
guswc,w/m2 S,"urface upward short-wave radiation flux, clear sky",地面晴空向上短波辐射通量,0.0,4.0,53.0,surface,,1.0,,,,,False
gulwc,w/m2,"Surface upward long-wave radiation flux, clear sky",地面晴空向上长波辐射通量,0.0,5.0,224.0,surface,,1.0,,,,,False
tuswc,w/m2,"TOE upward short-wave radiation flux, clear sky",大气顶晴空向上短波辐射通量,0.0,4.0,53.0,nominalTop,,8.0,,,,,False
tulwc,w/m2,"TOE upward long-wave radiation flux, clear sky",大气顶晴空向上长波辐射通量,0.0,5.0,224.0,nominalTop,,8.0,,,,,False
btv,K,Radiation bright temperature(vapor channel),辐射亮温（水汽通道）,0.0,4.0,227.0,surface,,,,,,,False
bti,K,Radiation bright temperature(infrared channel),辐射亮温（红外通道）,0.0,4.0,228.0,surface,,,,,,,False
tadv,1.e-6 k/s,Temperature advection,温度平流,0.0,0.0,224.0,,,,,,,,False
t_adv,1.e-6 k/s,Temperature advection,温度平流,0.0,0.0,224.0,,,,,,,,True
tvw,kg/m2,Total column integrated water vapor,总柱状比湿,0.0,1.0,64.0,atmosphere,,10.0,,,,,False
tcw,kg/m2,Total column integrated cloud water,总柱状云水,0.0,1.0,69.0,atmosphere,,10.0,,,,,False
tiw,kg/m2,Total column integrated cloud ice,总柱状云冰,0.0,1.0,70.0,atmosphere,,10.0,,,,,False
voradv,1.e-11/(s2),Relative vorticity advection,涡度平流,0.0,2.0,224.0,,,,,,,,False
vor_adv,1.e-11/(s2),Relative vorticity advection,涡度平流,0.0,2.0,224.0,,,,,,,,True
cc,%,Cloud cover,云量,0.0,6.0,22.0,,,,,,,,False
pip,,Perturbed Exner pressure,Exner气压扰动,0.0,3.0,224.0,,,,,,,,False
thp,,Perturbed potential temperature,位温扰动,0.0,0.0,229.0,,,,,,,,False
ri,,Richardson number,理查森数,0.0,7.0,12.0,,,,,,,,False
risfc,,Richardson number of surface layer,近地面总体理查森数,0.0,7.0,12.0,surface,,1.0,,,,,False
ripbl,,Richardson number of PBL,边界层总体理查森数,0.0,7.0,12.0,,,166.0,,,,,False
qpe,mm,Quantitive precipitation estimate,定量降水估计,0.0,1.0,230.0,,,,,,,,False
rhmax,%,Maximum of rh ,最大相对湿度,0.0,1.0,231.0,,,,,,,,False
rhmax2m,%,Maximum of rh at 2 meters height,2米最大相对湿度,0.0,1.0,231.0,heightAboveGround,2.0,103.0,2.0,,,,False
rhmin,%,Minimum of rh,最小相对湿度,0.0,1.0,232.0,,,,,,,,False
rhmin2m,%,Minimum of rh at 2 meters height,2米最小相对湿度,0.0,1.0,232.0,heightAboveGround,2.0,103.0,2.0,,,,False
rainp,%,Probability of precipitation,降水概率,0.0,1.0,233.0,,,,,,,,False
rainpr,mm,Process precipitation,过程降水量,0.0,1.0,234.0,,,,,,,,False
rainh,mm,Short time heavy precipitation,短时强降水,0.0,1.0,235.0,,,,,,,,False
hail,mm,Hail,冰雹,0.0,1.0,236.0,,,,,,,,False
raint,mm,Precipitation of typhoon,台风降水,0.0,1.0,237.0,,,,,,,,False
light,,Lightning,闪电,0.0,1.0,238.0,,,,,,,,False
htdn,,Number of high temperature days ,高温日数,0.0,0.0,226.0,,,,,,,,False
ata,K,Average temperature anomaly,平均气温距平,0.0,0.0,227.0,,,,,,,,False
tn,K,Minimum of air temperature for NMC medium-term prediction only,最低气温(仅限NMC使用),0.0,0.0,228.0,,,,,,,,False
thunwind,,Thunderstorm wind,雷暴大风,0.0,2.0,229.0,,,,,,,,False
seawave,m,Sea wave,海浪,0.0,2.0,230.0,,,,,,,,False
weph,,Weather phenomenon,天气现象,0.0,2.0,231.0,,,,,,,,False
haze,,Haze,霾,0.0,2.0,232.0,,,,,,,,False
apd,,Condition of air pollution,空气污染条件,0.0,2.0,233.0,,,,,,,,False
fog,,Fog,雾,0.0,2.0,234.0,,,,,,,,False
cdbz,dbz,Composite radar reflectivity,雷达组合反射率,0.0,16.0,224.0,surface,,,,,,,False
cr,dbz,Composite radar reflectivity,雷达组合反射率,0.0,16.0,224.0,surface,,,,,,,True
c_dbz,dbz,Composite radar reflectivity,雷达组合反射率,0.0,16.0,224.0,surface,,,,,,,True
cdbzmax#3,dbz,Maximum of cdbz during 3 hours,3小时最大雷达组合反射率,0.0,16.0,224.0,surface,,,,,,max,False
cr#3,dbz,Maximum of cdbz during 3 hours,3小时最大雷达组合反射率,0.0,16.0,224.0,surface,,,,,,max,True
dbz,dbz,Radar reflectivity,雷达反射率,0.0,16.0,225.0,,,,,,,,False
dbzmax#3,dbz,Maximum of dbz during 3 hours,3小时最大雷达反射率,0.0,16.0,225.0,,,,,,,max,False
dbzmaxh,m,height of maximum of radar reflectivity,最大雷达回波的高度,0.0,16.0,226.0,,,,,,,,False
vi,m2/s,Ventilation Index,通风系数,0.0,2.0,235.0,,,,,,,,False
ht0,m,Height of 0 degree isothermal level,0度层高度,0.0,3.0,225.0,surface,,1.0,,,,,False
ht2,m,Height of -20 degree isothermal level,-20度层高度,0.0,3.0,226.0,surface,,1.0,,,,,False
tti,K,Total totals index,总指数,0.0,7.0,4.0,surface,,1.0,,,,,False
wi,,Wind index,大风指数,0.0,2.0,236.0,surface,,1.0,,,,,False
hi,,Hail index ,冰雹指数,0.0,1.0,239.0,surface,,1.0,,,,,False
hib,m,Height of inversion base ,逆温层底高度,0.0,3.0,227.0,,,,,,,,False
II,oC/hm,Inversion intensity,逆温强度,0.0,1.0,240.0,,,,,,,,False
dcape,J/kg,Down convective available potential energy,下沉有效位能,0.0,7.0,224.0,,,,,,,,False
ssi,,Storm strength index,风暴强度指数,0.0,7.0,225.0,,,,,,,,False
si,K,Showalter index,沙氏指数,0.0,7.0,13.0,surface,,1.0,,,,,False
asi,,Atmospheric stability index,大气稳定度指数,0.0,7.0,226.0,,,,,,,,False
gust,m/s,Wind speed (gust),,0.0,2.0,22.0,,,,,,,,False
cldt,m,cloud top,,0.0,6.0,12.0,,,,,,,,False
cldb,m,cloud base,,0.0,6.0,11.0,,,,,,,,False
ceiling,m,ceiling,,0.0,6.0,13.0,,,,,,,,False
"""


def _get_cemc_param_table() -> pd.DataFrame:
    f = io.StringIO(_CEMC_PARAM_TABLE_CONTENT)
    df = pd.read_table(
        f,
        header=0,
        sep=",",
    )
    return df


CEMC_PARAM_TABLE = _get_cemc_param_table()