import cfgrib # type: ignore
from os import listdir

# This is where we store the files for each date
DATA_DIR = "data/"

for f in listdir(DATA_DIR):
    if f.endswith(".grib"):
        ds = cfgrib.open_dataset(DATA_DIR + f)
        print(f, ds.coords['isobaricInhPa'].values)
        
