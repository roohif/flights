import argparse
import math
import grib_downloader # type: ignore

######################################################################

def calculate_azimuth(u_val, v_val):

	# The y value is actually increasing from SOUTH to NORTH
	az = 90 - int(math.atan2(v_val, u_val) * 180 / math.pi)
	
	if (az < 0):
		az += 360

	return az

######################################################################

def get_fastest_wind(date, level, units="mps", minlat=None, maxlat=None):

	ds = grib_downloader.get_dataset(date, level)
	arr = ds.to_array()

	max_values = len(ds.latitude.values) * len(ds.longitude.values)
	max_magnitude = 0

	for lat_idx in range(len(arr.latitude)):
		for lon_idx in range(len(arr.longitude)):
			
			u_val = arr[0, lat_idx, lon_idx]
			v_val = arr[1, lat_idx, lon_idx]

			this_lat = float(u_val.latitude.values)
			this_lon = float(u_val.longitude.values)

			if (minlat):
				if (abs(this_lat) < minlat):
					continue

			if (maxlat):
				if (abs(this_lat) > maxlat):
					continue

			u_val_ms = u_val.values
			v_val_ms = v_val.values

			magnitude = math.sqrt(u_val_ms**2 + v_val_ms**2) # metres per second
			
			if (units == "mph"):
				magnitude *= 2.23694
			elif (units == "kmh"):
				magnitude *= 3.6
			elif (units == "kts"):
				magnitude *= 1.94384

			azimuth = calculate_azimuth(u_val_ms, v_val_ms)

			if (magnitude > max_magnitude):
				max_magnitude = magnitude
				position = f"{azimuth},{this_lat},{this_lon}"

	print(",".join((date, str(level), f"{max_magnitude:.2f}", units, position)))

######################################################################

if __name__ == "__main__":
	# Command line arguments
	parser = argparse.ArgumentParser(
				prog='Fastest wind',
				description='Finds the fastest wind anywhere on earth')

	parser.add_argument('--date', required=True, help="YYYY-MM-DD") # Date of the GRIB file
	parser.add_argument('--level', required=True, type=int, choices=[300, 250, 200, 150, 100, 50], help="hPa") # Atmospheric Level
	parser.add_argument("--units", choices=['mph', 'kmh', 'mps', 'kts'], default='mps')
	parser.add_argument('--minlat', type=float)
	parser.add_argument('--maxlat', type=float)

	args = parser.parse_args()

	# Finally!
	get_fastest_wind(args.date, args.level, args.units, args.minlat, args.maxlat)
