import pyproj # type: ignore
import argparse
import math

from airports import airports # type: ignore

# Command line arguments
parser = argparse.ArgumentParser(
            prog='Route Distance',
            description='Computes the distance between two points on both globe and the AE map')

parser.add_argument("-v", "--verbose", action="store_true", default=False)
# parser.add_argument("--units", choices=['mi', 'km', 'nm'], default='nm')

# The origin and destination arguments can either be the name of an airport (see airports.py) or
# a comma separated lat,lon. However, because coordinates in the south start with a "-" symbol, and
# the minus symbol on the command line denotes a new switch argument, you need to remove the space
# between the switch and the coordinates.
#
# -o sydney		VALID
#
# -d -30,140	INVALID
# -d-30,140		VALID

parser.add_argument('-o', '--orig', required=True, help="Coordinates in the south *CANNOT* be separated by a space. e.g. -o-30,100")
parser.add_argument('-d', '--dest', required=True, help="Coordinates in the south *CANNOT* be separated by a space. e.g. -d-30,100")

args = parser.parse_args()

# Now try to parse the origin and destination from the command line
if args.orig in airports:
	args.lat1,args.lon1 = airports[args.orig]
else:
	# Try to parse it as a float,float
	vals = args.orig.split(",")
	args.lat1,args.lon1 = (float(vals[0]), float(vals[1]))

if args.dest in airports:
	args.lat2,args.lon2 = airports[args.dest]
else:
	# Try to parse it as a float,float
	vals = args.dest.split(",")
	args.lat2,args.lon2 = (float(vals[0]), float(vals[1]))

if (args.verbose):
	print("arguments:", args)

g = pyproj.Geod(ellps="WGS84")
results = {} # All in nautical miles
results["units"] = "nautical miles"

################################################################################

def delta_longitude(lon1, lon2):

	# Returns the difference between the longitudes, where a positive result
	# means lon1 -> lon2 is travelling east.
	diff = lon2 - lon1

	if (diff < -180):
		diff += 360

	return diff

################################################################################

def ae_distance_between(lat1, lon1, lat2, lon2):

	# Calculate the distance for the AE map in NMI

	# Draw a big triangle with one point at the north pole, and the
	# other two points are the given coordinates
	delta_lon = delta_longitude(lon1, lon2)

	side_a = (90 - lat1) * 60
	side_b = (90 - lat2) * 60

	side_c = math.sqrt(side_a**2 + side_b**2 - 2 * side_a * side_b * math.cos(math.radians(delta_lon)))

	return side_c

################################################################################

def ae_azimuth_to(lat1, lon1, lat2, lon2):

	delta_lon = delta_longitude(lon1, lon2)

	side_a = (90 - lat1) * 60
	side_b = ae_distance_between(lat1, lon1, lat2, lon2)
	side_c = (90 - lat2) * 60

	# Rearrange the Law of Cosines to work out the angle
	az = math.degrees(math.acos((side_a**2 + side_b**2 - side_c**2) / (2 * side_a * side_b)))

	if (delta_lon > 0):
		return az
	else:
		return -az

################################################################################

def ae_forward_point(lat, lon, az, dist):

	# Start at lat/lon, and move "dist" nautical miles at an azimuth of "az"
	side_a = (90 - lat) * 60
	side_b = dist

	side_c = math.sqrt(side_a**2 + side_b**2 - 2 * side_a * side_b * math.cos(math.radians(az)))

	new_lat = 90 - (side_c / 60)
	delta_lon = math.degrees(math.asin(side_b / side_c * math.sin(math.radians(az))))

	return new_lat, lon + delta_lon

################################################################################

# Calculate the distance for the globe
az12,az21,dist = g.inv(args.lon1, args.lat1, args.lon2, args.lat2)
results["globe_route"] = dist / 1852

################################################################################

# Calculate the distance for the AE map
results['ae_route'] = ae_distance_between(args.lat1, args.lon1, args.lat2, args.lon2)

################################################################################

# Calculate the distance for the globe route BUT ON THE AE MAP!

# Start at lat1, lat2 and get an azimuth to the destination
old_lat = args.lat1
old_lon = args.lon1

hop_distance = 5000 # metres to travel each hop
ae_dist = 0 # Nautical Miles

az12,az21,dist = g.inv(old_lon, old_lat, args.lon2, args.lat2)

while (dist > hop_distance):
	# Move X metres along the globe route, but then calculate the
	# DISTANCE as if it were on the AE map
	new_lon, new_lat, backaz = g.fwd(old_lon, old_lat, az12, hop_distance)
	ae_dist += ae_distance_between(old_lat, old_lon, new_lat, new_lon)

	old_lat = new_lat
	old_lon = new_lon
	az12,az21,dist = g.inv(old_lon, old_lat, args.lon2, args.lat2)

results['globe_route_on_ae'] = ae_dist

################################################################################

# Calculate the distance for the AE route BUT ON THE GLOBE!
old_lat = args.lat1
old_lon = args.lon1

hop_distance = 3 # Nautical Miles
globe_dist = 0

az12 = ae_azimuth_to(old_lat, old_lon, args.lat2, args.lon2)
dist = ae_distance_between(old_lat, old_lon, args.lat2, args.lon2)

while (dist > hop_distance):
	# Move X nautical miles along the AE route, but then calculate the
	# DISTANCE as if it were on the globe
	new_lat,new_lon = ae_forward_point(old_lat, old_lon, az12, hop_distance)
	tmpaz12,tmpaz21,tmpdist = g.inv(old_lon, old_lat, new_lon, new_lat)
	globe_dist += tmpdist / 1852

	old_lat = new_lat
	old_lon = new_lon
	az12 = ae_azimuth_to(old_lat, old_lon, args.lat2, args.lon2)
	dist = ae_distance_between(old_lat, old_lon, args.lat2, args.lon2)

results['ae_route_on_globe'] = globe_dist

################################################################################

print(results)
