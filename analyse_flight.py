import xml.etree.ElementTree as ET 
import argparse
import sys
import math
import time
import pyproj # type: ignore
import urllib
import datetime
import grib_downloader # type: ignore
import matplotlib as mpl # type: ignore

# Command line arguments
parser = argparse.ArgumentParser(
            prog='KML Flight Analyser',
            description='Takes a KML file from FilghtRadar24 and produces a *bEtTeR* KML file')

parser.add_argument("kmlfile") # positional argument
parser.add_argument("--out") # Write to a named KML file
parser.add_argument("-s", "--speed", help="metres per second", default=250) # speed in m/s (250 m/s = 900 km/h = 559 mph)
parser.add_argument("--level", type=int, choices=[300, 250, 200, 150, 50], default=250)
parser.add_argument("--units", choices=['mph', 'kmh', 'mps'], default='mps')

args = parser.parse_args()

# KML Namespace
kml_ns = {'kml' : 'http://www.opengis.net/kml/2.2'}

# Initialise the colour map
cmap = mpl.colors.LinearSegmentedColormap.from_list("cmap", [
		"#FF3F3F", # Red
		"#FFCF00", # Orange
		"#FFFFFF", #  White
		"#003FFF", # Blue
		"#3FFF3F" # Green
	])

# Create a geoid
geod = pyproj.Geod(ellps='WGS84')

######################################################################

def rgba_to_GE_hex(rgba):

	r = min(int(rgba[0] * 256), 255)
	g = min(int(rgba[1] * 256), 255)
	b = min(int(rgba[2] * 256), 255)

	return f"FF{b:02x}{g:02x}{r:02x}"

######################################################################

def kml_header(name):

	return f"""<?xml version="1.0" encoding="UTF-8"?>
	<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
	<Document>
		<name>{name}</name>
		<open>1</open>
		<StyleMap id="m_plane">
			<Pair>
				<key>normal</key>
				<styleUrl>#s_plane</styleUrl>
			</Pair>
			<Pair>
				<key>highlight</key>
				<styleUrl>#s_plane_hl</styleUrl>
			</Pair>
		</StyleMap>
		<Style id="s_plane">
			<IconStyle>
				<scale>1.2</scale>
				<Icon>
					<href>plane.png</href>
				</Icon>
			</IconStyle>
			<LabelStyle>
				<scale>0</scale>
			</LabelStyle>
			<ListStyle>
			</ListStyle>
		</Style>
		<Style id="s_plane_hl">
			<IconStyle>
				<scale>1.2</scale>
				<Icon>
					<href>plane.png</href>
				</Icon>
			</IconStyle>
			<LabelStyle>
				<scale>2.0</scale>
			</LabelStyle>
			<ListStyle>
			</ListStyle>
		</Style>"""

######################################################################

def create_placemark(lat, lon, altitude, wind_impact, heading, name, description):

	# Normalise the longitude for Google Earth
	if (lon > 180):
		lon = lon - 360

	# Cap the magnitude at some value
	cap = 50
	cmap_idx = (max(min(wind_impact, cap), -cap) + cap) / (2 * cap)
	rgba = cmap(cmap_idx)
	ge_color = rgba_to_GE_hex(rgba)

	return f"""
	<Placemark>
	   	<name>{name}</name>
		<description>{description}</description>
		<styleUrl>#m_plane</styleUrl>
		<Style>
			<IconStyle>
				<heading>{heading:.0f}</heading>
				<color>{ge_color}</color>
			</IconStyle>
			<LabelStyle>
			</LabelStyle>
		</Style>
		<Point>
            <altitudeMode>absolute</altitudeMode>
			<coordinates>{lon:.6f},{lat:.6f},{altitude}</coordinates>
		</Point>
	</Placemark>"""

######################################################################

def create_path(path, time_taken):

	path_as_str = " ".join(path)

	td = datetime.timedelta(seconds=round(time_taken, 0))
	time_str = str(td)

	return f"""
	<Placemark>
	   	<name>Predicted Flight Time: {time_str}</name>
		<visibility>1</visibility>
		<LineString>
			<tessellate>1</tessellate>
            <altitudeMode>absolute</altitudeMode>
			<coordinates>
				{path_as_str}
			</coordinates>
		</LineString>
	</Placemark>"""

######################################################################

def kml_footer():

	return f"""
		</Document>
	</kml>
	"""

######################################################################

def calculate_azimuth(u_val, v_val):

	# The y value is actually increasing from SOUTH to NORTH
	azi = 90 - int(math.atan2(v_val, u_val) * 180 / math.pi)
	
	if (azi < 0):
		azi += 360

	return azi

######################################################################

def get_wind(position, ds):

	rounded_start = [int(round(x, 0)) for x in position]

	# Denormalise the longitude for the GRIB table
	if (rounded_start[0] < 0):
		rounded_start[0] = rounded_start[0] + 360

	lats = [int(x) for x in ds.latitude.values]
	lons = [int(x) for x in ds.longitude.values]
	
	lat_idx = lats.index(rounded_start[1])
	lon_idx = lons.index(rounded_start[0])

	wind = ds.isel(latitude=[lat_idx], longitude=[lon_idx])

	u_val = float(wind.u.item(0))
	v_val = float(wind.v.item(0))

	magnitude = math.sqrt(u_val**2 + v_val**2)
	azimuth = calculate_azimuth(u_val, v_val)

	return (magnitude, azimuth)

######################################################################

def get_timestamps_from_route(route):

	# This is simply to extract the date of the flight. Grab the
	# first PlaceMark and get the "when" attribute
	takeoff_ts = None
	landing_ts = None

	for pm in route.findall('kml:Placemark', kml_ns):
		coords = pm.find("kml:Point/kml:coordinates", kml_ns)
		(lon,lat,altitude) = [float(x) for x in coords.text.split(",")]

		when = pm.find("kml:TimeStamp/kml:when", kml_ns)

		# Only concerned with when the plane is in the air
		if (abs(altitude) > 0):
			# What state are we in?
			if (not takeoff_ts):
				takeoff_ts = datetime.datetime.fromisoformat(when.text)

			landing_ts = datetime.datetime.fromisoformat(when.text)
		
	return (takeoff_ts, landing_ts)
	
######################################################################

def parse_trail(trail, ds, fp):

	# Start collecting all the points in the path
	path = []
	time_taken = 0

	folder_str = f"""
		<Folder>
			<name>Points</name>
			<open>0</open>
		"""
	
	print(folder_str, file=fp)

	for segment in trail.findall('kml:Placemark/kml:MultiGeometry/kml:LineString/kml:coordinates', kml_ns):
		points = segment.text.split()

		# Collect the starting point for our LineString later
		path.append(points[0])

		# We should only have two points in each section
		assert(len(points) == 2)

		start_point = [float(x) for x in points[0].split(',')]
		end_point = [float(x) for x in points[1].split(',')]

		# If the start and end points are both on the ground, then skip it
		if (abs(start_point[2] < 1) and (abs(end_point[2] < 1))):
			continue

		# What is the closest wind sample?
		(magnitude, azimuth) = get_wind(start_point, ds)

		# lon/lat; lon/lat
		(az12, az21, dist) = geod.inv(start_point[0], start_point[1], end_point[0], end_point[1])

		head_tail = math.cos(math.radians(abs(azimuth - az12))) * magnitude
		ground_speed = args.speed + head_tail
		segment_time = dist / ground_speed

		time_taken += segment_time

		if (az12 < 0):
			az12 = az12 + 360

		if (args.units == "mph"):
			name = f"{(head_tail * 2.23694):.2f} mph"
			description = f"""
			Wind: {(magnitude * 2.23694):.2f} mph at {azimuth:.0f}°
			Plane: {(ground_speed * 2.23694):.2f} mph at {az12:.0f}°
			"""
		elif (args.units == "kmh"):
			name = f"{(head_tail * 3.6):.2f} kmh"
			description = f"""
			Wind: {(magnitude * 3.6):.2f} kmh at {azimuth:.0f}°
			Plane: {(ground_speed * 3.6):.2f} kmh at {az12:.0f}°
			"""
		else: # Metres per second
			name = f"{head_tail:.2f} m/s"
			description = f"""
			Wind: {magnitude:.2f} m/s at {azimuth:.0f}°
			Plane: {ground_speed:.2f} m/s at {az12:.0f}°
			"""

		print(create_placemark(start_point[1], start_point[0], start_point[2], head_tail, az12, name, description), file=fp)

	# Close out the folder
	print("</Folder>", file=fp)

	# Print out the Path we've collected
	print(create_path(path, time_taken), file=fp)

	return

######################################################################

tree = ET.parse(args.kmlfile)
root = tree.getroot()

route = root.find("kml:Document/kml:Folder[kml:name='Route']", kml_ns)
(takeoff_ts, landing_ts) = get_timestamps_from_route(route)
flight_time = landing_ts - takeoff_ts
print(flight_time)

kmldate = takeoff_ts.strftime("%Y-%m-%d")
print("KML date: " + kmldate, file=sys.stderr)

try:
	ds = grib_downloader.get_dataset(kmldate, args.level)
except urllib.error.HTTPError as e:
	print(e)
	exit()

# Output file
if (args.out):
	fp = open(args.out, "w")
else:
	fp = sys.stdout

flight_number = root.find("kml:Document/kml:name", kml_ns)
name = f"{(flight_number.text)} - {kmldate} - Actual Flight Time: {flight_time}"

print(kml_header(name), file=fp)

trail = root.find("kml:Document/kml:Folder[kml:name='Trail']", kml_ns)
parse_trail(trail, ds, fp)

print(kml_footer(), file=fp)

print("Done!", file=sys.stderr)

