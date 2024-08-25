import cfgrib # type: ignore
from fastest_wind import get_fastest_wind
from os import listdir, system

# This is where we store the files for each date
DATA_DIR = "data/"

print("date,level,speed,units,azimuth,latitude,longitude")

for f in listdir(DATA_DIR):
	if f.endswith(".grib"):
		ds = cfgrib.open_dataset(DATA_DIR + f)

		level = int(ds.coords['isobaricInhPa'].values)
		ts = str(ds.coords['time'].values)
		date = ts[0:10]

		if (level == 250):
			get_fastest_wind(date, level, units="kts", minlat=35, maxlat=60)

		if (level == 200):
			get_fastest_wind(date, level, units="kts", minlat=35, maxlat=60)
			get_fastest_wind(date, level, units="kts", minlat=25, maxlat=35)

		if (level == 150):
			get_fastest_wind(date, level, units="kts", minlat=25, maxlat=35)
