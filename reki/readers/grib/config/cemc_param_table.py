import io

import pandas as pd


_CEMC_PARAM_TABLE_CONTENT = """name,unit,description,description_cn,discipline,category,number,typeOfLevel,level,first_level_type,first_level,second_level_type,second_level,stepType,alias
ps,Pa,Surface pressure,地面气压,0,3,0,surface,,1,,,,,FALSE
psfc,Pa,Surface pressure,地面气压,0,3,0,surface,,1,,,,,TRUE
psl,Pa,Sea level pressure,海平面气压,0,3,1,meanSea,,101,,,,,FALSE
pi,,Exner pressure,Exner气压,0,3,26,,,,,,,,FALSE
h,Gpm,Geopotential height,位势高度,0,3,5,,,100,,,,,FALSE
zs,Gpm,Terrain ,地形高度,0,3,5,surface,,1,,,,,FALSE
t,K,Temperature,温度,0,0,0,,,,,,,,FALSE
t2m,K,Temperature at 2 meters height,2米温度,0,0,0,heightAboveGround,2,103,2,,,,FALSE
ts,K,Surface temperature,地面温度,0,0,0,surface,,1,,,,,FALSE
tsfc,K,Surface temperature,地面温度,0,0,0,surface,,1,,,,,TRUE
thetaSe,K,Pseudo-equivalent potential temperature,假相当位温,0,0,3,,,,,,,,FALSE
mx2t,K,Maximum of 2 meters high temperature,2米最高温度,0,0,4,heightAboveGround,2,103,2,,,max,FALSE
tmax2m,K,Maximum of 2 meters high temperature,2米最高温度,0,0,4,heightAboveGround,2,103,2,,,max,TRUE
mn2t,K,Minimum of 2 meters high temperature,2米最低温度,0,0,5,heightAboveGround,2,103,2,,,min,FALSE
tmin2m,K,Minimum of 2 meters high temperature,2米最低温度,0,0,5,heightAboveGround,2,103,2,,,min,TRUE
td,K,Dew point,露点温度,0,0,6,,,,,,,,FALSE
td2m,K,2 meters high Dew point,2米露点温度,0,0,6,heightAboveGround,2,103,2,,,,FALSE
ttd,K,Dew point depression,温度露点差,0,0,7,,,,,,,,FALSE
vis,m,Visibility,能见度,0,19,0,surface,,1,,,,,FALSE
pli,K,Parcel lifted index(to 500 hpa),气块抬升指数,0,7,0,surface,,1,,,,,FALSE
u,m/s,U-component of wind,东西风,0,2,2,,,,,,,,FALSE
u10m,m/s,V-component of wind at 10 meters height,10米东西风,0,2,2,heightAboveGround,10,103,10,,,instant,FALSE
u10mmax#1,m/s,Maximum of u10m during 1 hours,输出间隔内最大10米东西风,0,2,2,heightAboveGround,10,103,10,,,max,FALSE
u10mmax#3,m/s,Maximum of u10m during 3 hours,3小时最大10米东西风,0,2,2,heightAboveGround,10,103,10,,,max,FALSE
u10mmax,m/s,Maximum of u10m,最大10米东西风,0,2,2,heightAboveGround,10,103,10,,,max,FALSE
v,m/s,V-component of wind,南北风,0,2,3,,,,,,,,FALSE
v10m,m/s,V-component of wind at 10 meters height,10米南北风,0,2,3,heightAboveGround,10,103,10,,,instant,FALSE
v10mmax#1,m/s,Maximim of v10m during 1 hours,输出间隔内10米南北风,0,2,3,heightAboveGround,10,103,10,,,max,FALSE
v10mmax#3,m/s,Maximim of v10m during 3 hours,3小时最大10米南北风,0,2,3,heightAboveGround,10,103,10,,,max,FALSE
v10mmax,m/s,Maximim of v10m,最大10米南北风,0,2,3,heightAboveGround,10,103,10,,,max,FALSE
w,m/s,Vertical velocity (geometric),等高面垂直速度,0,2,9,,,100,,,,,FALSE
wmax#1,m/s,Maximum of w during 1 hours,1小时等高面最大垂直速度,0,2,9,,,100,,,,max,FALSE
wmax#3,m/s,Maximum of w during 3 hours,3小时等高面最大垂直速度,0,2,9,,,100,,,,max,FALSE
wmax,m/s,Maximum of w,等高面最大垂直速度,0,2,9,,,100,,,,max,FALSE
vor,s-1,Relative vorticity,涡度,0,2,12,,,,,,,,FALSE
div,s-1,Relative divergence,散度,0,2,13,,,,,,,,FALSE
q,kg/kg,Specific humidity,比湿,0,1,0,,,,,,,,FALSE
q2m,kg/kg,Specific humidity at 2 meters height,2米比湿,0,1,0,heightAboveGround,2,103,2,,,,FALSE
rh,%,Relative humidity,相对湿度,0,1,1,,,,,,,,FALSE
rh2m,%,Relative humidity at 2 meters height,2米相对湿度,0,1,1,heightAboveGround,2,103,2,,,,FALSE
pwat,kg/kg,Precipitable water,整层可降水量,0,1,3,atmosphere,,10,,,,,FALSE
rain,mm,Total precipitation,总累计降水,0,1,8,surface,,1,,,,accum,FALSE
rainnc,mm,Large scale precipitation,大尺度降水,0,1,9,surface,,1,,,,accum,FALSE
rainc,mm,Convective precipitation,对流性降水,0,1,10,surface,,1,,,,accum,FALSE
sf,m,Snow melt  ,降雪,0,1,29,surface,,1,,,,accum,FALSE
snow,m,Snow melt  ,降雪,0,1,29,surface,,1,,,,accum,TRUE
sd,m,Snow depth  ,雪深,0,1,11,surface,,1,,,,,FALSE
tcc,%,Total cloud cover,总云量,0,6,1,entireAtmosphere,,,,,,,FALSE
lcc,%,Low cloud cover,低云量,0,6,3,entireAtmosphere,,,,,,,FALSE
mcc,%,Medium cloud cover,中云量,0,6,4,entireAtmosphere,,,,,,,FALSE
hcc,%,High cloud cover,高云量,0,6,5,entireAtmosphere,,,,,,,FALSE
bli,K,Best lifted index,最优抬升指数,0,7,1,surface,,,,,,,FALSE
albedo,%,Albedo,反射率,0,19,1,surface,,1,,,,,FALSE
st,K,Soil temperature,土壤温度,0,0,0,depthBelowLandLayer,,106,,,,,FALSE
st(0-10),,,0-10cm土壤温度,0,0,0,depthBelowLandLayer,,106,0,106,0.1,,FALSE
st(10-40),,,10-40cm土壤温度,0,0,0,depthBelowLandLayer,,106,0.1,106,0.4,,FALSE
st(40-100),,,40-100cm土壤温度,0,0,0,depthBelowLandLayer,,106,0.4,106,1,,FALSE
st(100-200),,,100-200cm土壤温度,0,0,0,depthBelowLandLayer,,106,1,106,2,,FALSE
ro,m,Runoff,径流,0,1,227,,,,,,,,FALSE
znt,m,roughness length,粗糙度,0,3,228,surface,,1,,,,,FALSE
gsw,w/m2,Net short wave radiation flux,净短波辐射通量|净太阳辐射通量,0,4,9,,,,,,,,FALSE
ssr,w/m2,Net short wave radiation flux,净短波辐射通量|净太阳辐射通量,0,4,9,,,,,,,,TRUE
glw,w/m2,Net long wave radiation flux,净长波辐射通量|净热辐射通量,0,5,5,,,,,,,,FALSE
str,w/m2,Net long wave radiation flux,净长波辐射通量|净热辐射通量,0,5,5,,,,,,,,TRUE
gswc,w/m2,"Net short wave radiation flux, clear sky",晴空地面净短波辐射通量,0,4,11,surface,,1,,,,,FALSE
tsw,w/m2,TOE net short wave radiation flux,大气顶净短波辐射通量,0,4,9,nominalTop,,8,,,,accum,FALSE
tswc,w/m2,"TOE net short wave radiation flux, clear sky",晴空大气顶净短波辐射通量,0,4,11,nominalTop,,8,,,,,FALSE
slhf,ws/m2,Latent heat net flux,潜热辐射,0,0,10,,,,,,,,FALSE
sshf,ws/m2,Sensible heat net flux,感热辐射,2,0,24,,,,,,,,FALSE
saunaidx,,Sauna index,桑拿指数,0,0,225,,,,,,,,FALSE
kidx,C,K index,K指数,0,7,2,meanSea,,101,,,,,FALSE
ki,C,K index,K指数,0,7,2,meanSea,,101,,,,,TRUE
k,C,K index,K指数,0,7,2,meanSea,,101,,,,,TRUE
qflx,1e-1.g/(cm.hpa.s),Moisture flux,水汽通量,0,1,224,,,,,,,,FALSE
qdiv,1e-7.g/(cm2.hpa.s),Moisture flux divergence,水汽通量散度,0,1,225,,,,,,,,FALSE
qfxsfc,kg/(m2.s),Surface moisture flux,地表水汽通量,0,1,229,surface,,1,,,,,FALSE
qfx,kg/(m2.s),Surface moisture flux,地表水汽通量,0,1,229,surface,,1,,,,,TRUE
sw,m3/m3,Soil moisture,土壤湿度,0,1,0,depthBelowLandLayer,,106,,,,,FALSE
sw(0-10),,,0-10cm土壤湿度,0,1,0,depthBelowLandLayer,,106,0,106,0.1,,FALSE
sw(10-40),,,10-40cm土壤湿度,0,1,0,depthBelowLandLayer,,106,0.1,106,0.4,,FALSE
sw(40-100),,,40-100cm土壤湿度,0,1,0,depthBelowLandLayer,,106,0.4,106,1,,FALSE
sw(100-200),,,100-200cm土壤湿度,0,1,0,depthBelowLandLayer,,106,1,106,2,,FALSE
wess,N/m2,West-east surface wind stress,东西向风应力,0,2,227,surface,,1,,,,,FALSE
nsss,N/m2,North-south surface wind stress,南北向风应力,0,2,228,surface,,1,,,,,FALSE
sweatidx,,Sweat index,强天气胁迫指数,0,7,5,surface,,1,,,,,FALSE
sweat,,Sweat index,强天气胁迫指数,0,7,5,surface,,1,,,,,TRUE
qc,kg/kg,Cloud mixing ratio,云水混合比,0,1,22,,,,,,,,FALSE
hfx,w/m2,Surface heat flux,地表热通量,0,0,24,surface,,1,,,,accum,FALSE
cin,J/kg,Convective inhibition,对流抑制能量,0,7,7,surface,,1,,,,,FALSE
cape,J/kg,Convective available potential energy,对流有效位能,0,7,6,surface,,1,,,,,FALSE
pc,Pa,Condensation layer pressure,抬升凝结高度,0,1,228,surface,,1,,,,,FALSE
rain5max,mm,5-minutes accumulated precipitation,5分钟最大降水,0,1,241,surface,,1,,,,max,FALSE
qr,kg/kg,Rain mixing ratio,雨水混合比,0,1,24,,,,,,,,FALSE
qs,kg/kg,Snow mixing ratio,雪水混合比,0,1,25,,,,,,,,FALSE
qi,kg/kg,Ice mixing ratio,冰水混合比,0,1,23,,,,,,,,FALSE
graupel,kg/kg,Graupel,霰,0,1,32,,,,,,,,FALSE
precitype,,Precipitation type,降水相态,0,1,19,,,,,,,,FALSE
mpv1,1e-6.k/(m2.s.kg),Moist potential vorticity(vertical part),湿位涡垂直分量,0,2,225,,,,,,,,FALSE
mpv2,1e-6.k/(m2.s.kg),Moist potential vorticity(horizontal part),湿位涡水平分量,0,2,226,,,,,,,,FALSE
shr,s-1,Vertical speed shear,垂直风切变,0,2,25,,,,,,,,FALSE
shr(0-1000),,,0-1km垂直风切变,0,2,25,heightAboveGroundLayer,1000,103,1000,103,0,,FALSE
shr(0-3000),,,0-3km垂直风切变,0,2,25,heightAboveGroundLayer,3000,103,3000,103,0,,FALSE
shr(0-6000),,,0-6km垂直风切变,0,2,25,heightAboveGroundLayer,6000,103,6000,103,0,,FALSE
shrmax,m/s,maximum vector of vertical wind shear,最大垂直风切变矢量,0,2,237,,,,,,,,FALSE
shrmax(0-600),,,0-600m最大垂直风切变矢量,0,2,237,heightAboveGroundLayer,600,103,600,103,0,,FALSE
shrmaxdir,degree,direction of maxium vertical wind shear,最大垂直风切变的方向,0,2,238,,,,,,,,FALSE
shrmaxdir(0-600),,,0-600m最大垂直风切变的方向,0,2,238,heightAboveGroundLayer,600,103,600,103,0,,FALSE
srh,J/kg,Storm relative helicity,风暴螺旋度,0,7,8,,,,,,,,FALSE
srh(0-1000),,,0-1km垂直风暴螺旋度,0,7,8,heightAboveGroundLayer,1000,103,1000,103,0,,FALSE
srh(0-3000),,,0-3km垂直风暴螺旋度,0,7,8,heightAboveGroundLayer,3000,103,3000,103,0,,FALSE
uhmax,m2/s2,Updraught helicity,最大上升螺旋度,0,7,15,,,,,,,max,FALSE
uhmax(2000-5000),,,2-5km最大上升螺旋度,0,7,15,heightAboveGroundLayer,5000,103,5000,103,2000,max,FALSE
src,,Skin reservoir content  ,表面蓄水池含量,0,1,226,,,,,,,,FALSE
pblh,m,Planet boundary layer height,边界层高度,0,3,18,surface,,1,,,,,FALSE
gusw,w/m2,Surface upward short-wave radiation flux(surface),地面向上短波辐射通量,0,4,8,surface,,1,,,,,FALSE
gswu,w/m2,Surface upward short-wave radiation flux(surface),地面向上短波辐射通量,0,4,8,surface,,1,,,,,TRUE
gulw,w/m2,Surface upward long-wave radiation flux(surface),地面向上长波辐射通量,0,5,4,surface,,1,,,,,FALSE
gslu,w/m2,Surface upward long-wave radiation flux(surface),地面向上长波辐射通量,0,5,4,surface,,1,,,,,TRUE
tusw,w/m2,Upward short-wave radiation flux(top of atmoshpere),大气顶向上（外）短波辐射通量,0,4,8,nominalTop,,8,,,,,FALSE
tulw,w/m2,Upward long-wave radiation flux(top of atmoshpere),大气顶向上（外）长波辐射通量,0,5,4,nominalTop,,8,,,,,FALSE
gdlwc,w/m2,"Surface downward long-wave radiation flux, clear sky",地面晴空向下长波辐射通量,0,5,8,surface,,1,,,,,FALSE
guswc,w/m2 S,"urface upward short-wave radiation flux, clear sky",地面晴空向上短波辐射通量,0,4,53,surface,,1,,,,,FALSE
gulwc,w/m2,"Surface upward long-wave radiation flux, clear sky",地面晴空向上长波辐射通量,0,5,224,surface,,1,,,,,FALSE
tuswc,w/m2,"TOE upward short-wave radiation flux, clear sky",大气顶晴空向上短波辐射通量,0,4,53,nominalTop,,8,,,,,FALSE
tulwc,w/m2,"TOE upward long-wave radiation flux, clear sky",大气顶晴空向上长波辐射通量,0,5,224,nominalTop,,8,,,,,FALSE
btv,K,Radiation bright temperature(vapor channel),卫星水汽通道模拟亮温,0,4,227,surface,,,,,,,FALSE
bti,K,Radiation bright temperature(infrared channel),卫星红外通道模拟亮温,0,4,228,surface,,,,,,,FALSE
tadv,1.e-6 k/s,Temperature advection,温度平流,0,0,224,,,,,,,,FALSE
t_adv,1.e-6 k/s,Temperature advection,温度平流,0,0,224,,,,,,,,TRUE
tvw,kg/m2,Total column integrated water vapor,总柱状比湿,0,1,64,atmosphere,,10,,,,,FALSE
tcw,kg/m2,Total column integrated cloud water,总柱状云水,0,1,69,atmosphere,,10,,,,,FALSE
tiw,kg/m2,Total column integrated cloud ice,总柱状云冰,0,1,70,atmosphere,,10,,,,,FALSE
voradv,1.e-11/(s2),Relative vorticity advection,涡度平流,0,2,224,,,,,,,,FALSE
vor_adv,1.e-11/(s2),Relative vorticity advection,涡度平流,0,2,224,,,,,,,,TRUE
cc,%,Cloud cover,云量,0,6,22,,,,,,,,FALSE
pip,,Perturbed Exner pressure,Exner气压扰动,0,3,224,,,,,,,,FALSE
thp,,Perturbed potential temperature,位温扰动,0,0,229,,,,,,,,FALSE
ri,,Richardson number,理查森数,0,7,12,,,,,,,,FALSE
risfc,,Richardson number of surface layer,近地面总体理查森数,0,7,12,surface,,1,,,,,FALSE
ripbl,,Richardson number of PBL,边界层总体理查森数,0,7,12,,,166,,,,,FALSE
qpe,mm,Quantitive precipitation estimate,定量降水估计,0,1,230,,,,,,,,FALSE
rhmax,%,Maximum of rh ,最大相对湿度,0,1,231,,,,,,,,FALSE
rhmax2m,%,Maximum of rh at 2 meters height,2米最大相对湿度,0,1,231,heightAboveGround,2,103,2,,,,FALSE
rhmin,%,Minimum of rh,最小相对湿度,0,1,232,,,,,,,,FALSE
rhmin2m,%,Minimum of rh at 2 meters height,2米最小相对湿度,0,1,232,heightAboveGround,2,103,2,,,,FALSE
rainp,%,Probability of precipitation,降水概率,0,1,233,,,,,,,,FALSE
rainpr,mm,Process precipitation,过程降水量,0,1,234,,,,,,,,FALSE
rainh,mm,Short time heavy precipitation,短时强降水,0,1,235,,,,,,,,FALSE
hail,mm,Hail,冰雹,0,1,236,,,,,,,,FALSE
raint,mm,Precipitation of typhoon,台风降水,0,1,237,,,,,,,,FALSE
light,,Lightning,雷电概率,0,1,238,,,,,,,,FALSE
htdn,,Number of high temperature days ,高温日数,0,0,226,,,,,,,,FALSE
ata,K,Average temperature anomaly,平均气温距平,0,0,227,,,,,,,,FALSE
tn,K,Minimum of air temperature for NMC medium-term prediction only,最低气温(仅限NMC使用),0,0,228,,,,,,,,FALSE
thunwind,,Thunderstorm wind,雷暴大风,0,2,229,,,,,,,,FALSE
seawave,m,Sea wave,海浪,0,2,230,,,,,,,,FALSE
weph,,Weather phenomenon,天气现象,0,2,231,,,,,,,,FALSE
haze,,Haze,霾,0,2,232,,,,,,,,FALSE
apd,,Condition of air pollution,空气污染条件,0,2,233,,,,,,,,FALSE
fog,,Fog,雾,0,2,234,,,,,,,,FALSE
cdbz,dbz,Composite radar reflectivity,雷达组合反射率,0,16,224,surface,,,,,,,FALSE
cr,dbz,Composite radar reflectivity,雷达组合反射率,0,16,224,surface,,,,,,,TRUE
c_dbz,dbz,Composite radar reflectivity,雷达组合反射率,0,16,224,surface,,,,,,,TRUE
cdbzmax#1,dbz,Maximum of cdbz during 1 hours,输出间隔内最大雷达组合反射率,0,16,224,surface,,,,,,max,FALSE
cdbzmax#3,dbz,Maximum of cdbz during 3 hours,3小时最大雷达组合反射率,0,16,224,surface,,,,,,max,FALSE
cr#3,dbz,Maximum of cdbz during 3 hours,3小时最大雷达组合反射率,0,16,224,surface,,,,,,max,TRUE
dbz,dbz,Radar reflectivity,雷达反射率,0,16,225,,,,,,,,FALSE
dbzmax#3,dbz,Maximum of dbz during 3 hours,3小时最大雷达反射率,0,16,225,,,,,,,max,FALSE
dbzmaxh,m,height of maximum of radar reflectivity,最大雷达回波的高度,0,16,226,,,,,,,,FALSE
echotop,m,radar echo top,雷达回波顶,0,16,3,,,,,,,,FALSE
vi,m2/s,Ventilation Index,通风系数,0,2,235,,,,,,,,FALSE
ht0,m,Height of 0 degree isothermal level,0度层高度,0,3,225,surface,,1,,,,,FALSE
ht2,m,Height of -20 degree isothermal level,-20度层高度,0,3,226,surface,,1,,,,,FALSE
tti,K,Total totals index,总指数,0,7,4,surface,,1,,,,,FALSE
wi,,Wind index,大风指数,0,2,236,surface,,1,,,,,FALSE
hi,,Hail index ,冰雹指数,0,1,239,surface,,1,,,,,FALSE
hib,m,Height of inversion base ,逆温层底高度,0,3,227,,,,,,,,FALSE
II,oC/hm,Inversion intensity,逆温强度,0,1,240,,,,,,,,FALSE
dcape,J/kg,Down convective available potential energy,下沉对流有效位能,0,7,224,,,,,,,,FALSE
ssi,,Storm strength index,风暴强度指数,0,7,225,,,,,,,,FALSE
si,K,Showalter index,沙氏指数,0,7,13,surface,,1,,,,,FALSE
asi,,Atmospheric stability index,大气稳定度指数,0,7,226,,,,,,,,FALSE
gust,m/s,Wind speed (gust),阵风风速,0,2,22,,,,,,,,FALSE
cldt,m,cloud top,云顶高度,0,6,12,,,,,,,,FALSE
cldb,m,cloud base,云底高度,0,6,11,,,,,,,,FALSE
ceiling,m,ceiling,云幂高度,0,6,13,,,,,,,,FALSE
fogh,m,height of fog top,雾顶高度,0,19,224,surface,,1,,,,,FALSE
fogod,,fog optical,光学厚度,0,19,225,surface,,1,,,,,FALSE
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