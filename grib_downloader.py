# GRIB downloader
#  Takes the date as an argument, and checks to see if data exists for that date
# If not, it downloads it. Returns a GRIB dataset object
import cfgrib # type: ignore
import urllib.request
import urllib.parse
import xarray # type: ignore
import os

# This is where we store the files for each date
DATA_DIR = "data/"

######################################################################

def construct_url(date, level):

	# date is YYYY-MM-DD

	# Convert the YYYY-MM-DD to YYYYMMDD
	urldate = date.replace('-', '')
	level_param = "lev_" + str(level) + "_mb=on"

	# 1.00 degree intervals
	base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_1p00.pl?"

	# Construct a path for that date, cycle and subdirectory
	pathname = "/gfs." + urldate + "/00/atmos"
	filename = "gfs.t00z.pgrb2.1p00.anl"

	# Parameters:
	# UGRD = U-component of wind
	# VGRD = V-component of wind

	world = ["var_UGRD=on", "var_VGRD=on", level_param, \
		"subregion=", "toplat=89", "leftlon=1", \
		"rightlon=360", "bottomlat=-89"]

	url = base_url + "dir=" + urllib.parse.quote(pathname, safe="") + "&" + \
		"file=" + filename + "&" + "&".join(world)

	return url

################################################################################

def get_dataset(date, level):

	# date = "YYYY-MM-DD"
	
	# level = 250, 200, 150, etc. in millibars

	filename = DATA_DIR + date + "_" + str(level) + ".grib"

	if (not os.path.isfile(filename)):
		url = construct_url(date, level)
		try:
			urllib.request.urlretrieve(url, filename)
		except Exception as e:
			print(e, date, level)
			quit()

	return cfgrib.open_dataset(filename)

################################################################################
