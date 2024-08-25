import xml.etree.ElementTree as ET 
import zipfile
import argparse
import sys
import math
import numpy as np
import grib_downloader # type: ignore
import matplotlib as mpl # type: ignore
import progress.bar # type: ignore

# NetworkLinks
links = [
	{ "minlat": -90, "maxlat": -75, "minlon": 0, "maxlon": 360, "d": [] },

	{ "minlat": -75, "maxlat": -45, "minlon": 0, "maxlon": 90, "d": [] },
	{ "minlat": -75, "maxlat": -45, "minlon": 90, "maxlon": 180, "d": [] },
	{ "minlat": -75, "maxlat": -45, "minlon": 180, "maxlon": 270, "d": [] },
	{ "minlat": -75, "maxlat": -45, "minlon": 270, "maxlon": 360, "d": [] },

	{ "minlat": -45, "maxlat": -15, "minlon": 0, "maxlon": 90, "d": [] },
	{ "minlat": -45, "maxlat": -15, "minlon": 90, "maxlon": 180, "d": [] },
	{ "minlat": -45, "maxlat": -15, "minlon": 180, "maxlon": 270, "d": [] },
	{ "minlat": -45, "maxlat": -15, "minlon": 270, "maxlon": 360, "d": [] },

	{ "minlat": -15, "maxlat": 15, "minlon": 0, "maxlon": 90, "d": [] },
	{ "minlat": -15, "maxlat": 15, "minlon": 90, "maxlon": 180, "d": [] },
	{ "minlat": -15, "maxlat": 15, "minlon": 180, "maxlon": 270, "d": [] },
	{ "minlat": -15, "maxlat": 15, "minlon": 270, "maxlon": 360, "d": [] },

	{ "minlat": 15, "maxlat": 45, "minlon": 0, "maxlon": 90, "d": [] },
	{ "minlat": 15, "maxlat": 45, "minlon": 90, "maxlon": 180, "d": [] },
	{ "minlat": 15, "maxlat": 45, "minlon": 180, "maxlon": 270, "d": [] },
	{ "minlat": 15, "maxlat": 45, "minlon": 270, "maxlon": 360, "d": [] },

	{ "minlat": 45, "maxlat": 75, "minlon": 0, "maxlon": 90, "d": [] },
	{ "minlat": 45, "maxlat": 75, "minlon": 90, "maxlon": 180, "d": [] },
	{ "minlat": 45, "maxlat": 75, "minlon": 180, "maxlon": 270, "d": [] },
	{ "minlat": 45, "maxlat": 75, "minlon": 270, "maxlon": 360, "d": [] },

	{ "minlat": 75, "maxlat": 90, "minlon": 0, "maxlon": 360, "d": [] }
]

# Command line arguments
parser = argparse.ArgumentParser(
            prog='Convert GRIB data to KML PlaceMark file')

parser.add_argument('--date', required=True, help="YYYY-MM-DD") # Date of the GRIB file
parser.add_argument('--out', required=True, help="KML output file name") # Filename of the output file
parser.add_argument("--units", choices=['mph', 'kmh', 'mps'], default='mps')

args = parser.parse_args()

# Initialise the colour map
cmap = mpl.colors.LinearSegmentedColormap.from_list("cmap", [
		"#04091B", # 0
		"#00C2A4", "#2BFB00", # 100, 200
		"#DD7E00", "#F00055", # 300, 400
		"#BA15BA", "#C846C8", # 500, 600
		"#D674D6", "#E4A4E4", # 700, 800
		"#F1D1F1", "#FFFFFF" # 900, 1000
	])

# KML Namespace
kml_ns = {'kml' : 'http://www.opengis.net/kml/2.2'}

######################################################################

def link_map(links):

	arr = np.zeros((180, 360), dtype=np.int8)

	for idx in range(len(links)):
		nw_link = links[idx]
		for lat_idx in range(nw_link["minlat"], nw_link["maxlat"]):
			for lon_idx in range(nw_link["minlon"], nw_link["maxlon"]):
				arr[lat_idx, lon_idx] = idx

	return arr

######################################################################

def kml_header(name):

	return f"""<?xml version="1.0" encoding="UTF-8"?>
	<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
	<Document>
		<name>{name}</name>
		<open>1</open>
		<StyleMap id="m_arrow">
			<Pair>
				<key>normal</key>
				<styleUrl>#s_arrow</styleUrl>
			</Pair>
			<Pair>
				<key>highlight</key>
				<styleUrl>#s_arrow_hl</styleUrl>
			</Pair>
		</StyleMap>
		<Style id="s_arrow">
			<IconStyle>
				<scale>1.2</scale>
				<Icon>
					<href>windarrow.png</href>
				</Icon>
			</IconStyle>
			<LabelStyle>
				<scale>0</scale>
			</LabelStyle>
			<ListStyle>
			</ListStyle>
		</Style>
		<Style id="s_arrow_hl">
			<IconStyle>
				<scale>1.2</scale>
				<Icon>
					<href>windarrow.png</href>
				</Icon>
			</IconStyle>
			<ListStyle>
			</ListStyle>
		</Style>"""

######################################################################

def kml_footer():

	return f"""
		</Document>
	</kml>
	"""

######################################################################

def rgba_to_GE_hex(rgba):

	r = min(int(rgba[0] * 256), 255)
	g = min(int(rgba[1] * 256), 255)
	b = min(int(rgba[2] * 256), 255)

	return f"FF{b:02x}{g:02x}{r:02x}"

######################################################################

def create_placemark(lat, lon, magnitude, azimuth):

	# Normalise the longitude for Google Earth
	if (lon > 180):
		lon = lon - 360

	if (args.units == "mph"):
		name = f"{(magnitude * 2.23694):.2f} mph at {azimuth:.0f}°"
	elif (args.units == "kmh"):
		name = f"{(magnitude * 3.6):.2f} kmh at {azimuth:.0f}°"
	else: # Metres per second
		name = f"{magnitude:.2f} m/s at {azimuth:.0f}°"
	
	# Cap the magnitude at 100
	flt = min(magnitude, 100) / 100
	rgba = cmap(flt)
	ge_color = rgba_to_GE_hex(rgba)

	return f"""
	<Placemark>
	   	<name>{name}</name>
		<styleUrl>#m_arrow</styleUrl>
		<Style>
			<IconStyle>
				<heading>{azimuth:.0f}</heading>
				<color>{ge_color}</color>
			</IconStyle>
		</Style>
		<Point>
			<coordinates>{lon:.0f},{lat:.0f},0</coordinates>
		</Point>
	</Placemark>"""

######################################################################

def calculate_azimuth(u_val, v_val):

	# The y value is actually increasing from SOUTH to NORTH
	azi = 90 - int(math.atan2(v_val, u_val) * 180 / math.pi)
	
	if (azi < 0):
		azi += 360

	return azi

######################################################################

# Create an array with the lookup value for each NetworkLink
link = link_map(links)

ds = grib_downloader.get_dataset(args.date)
arr = ds.to_array()

max_values = len(ds.latitude.values) * len(ds.longitude.values)
bar = progress.bar.Bar("Processing", max=max_values)

for lat_idx in range(len(arr.latitude)):
	for lon_idx in range(len(arr.longitude)):
		
		u_val = arr[0, lat_idx, lon_idx]
		v_val = arr[1, lat_idx, lon_idx]

		this_lat = float(u_val.latitude.values)
		this_lon = float(u_val.longitude.values)

		u_val_ms = u_val.values
		v_val_ms = v_val.values

		magnitude = math.sqrt(u_val_ms**2 + v_val_ms**2)
		azimuth = calculate_azimuth(u_val_ms, v_val_ms)

		link_idx = link[int(this_lat), int(this_lon)]
		links[link_idx]["d"].append(create_placemark(this_lat, this_lon, magnitude, azimuth))

		bar.next()

# Open the master KML file
fp = open("doc.kml", "w")
print(kml_header("Wind: " + args.date), file=fp)

# Print out each Network Link
for idx in range(len(links)):

	nw_link = links[idx]
	linkfilename = f"link{idx:02}.kml"

	# Print the NetworkLink to the master file
	print(f"""
	<NetworkLink>
		<name>{linkfilename}</name>
		<Region>
			<LatLonAltBox>
				<north>{nw_link["maxlat"]}</north>
				<south>{nw_link["minlat"]}</south>
				<east>{nw_link["maxlon"]}</east>
				<west>{nw_link["minlon"]}</west>
			</LatLonAltBox>
		</Region>
		<Link>
			<href>files/{linkfilename}</href>
			<viewRefreshMode>onRegion</viewRefreshMode>
		</Link>
	</NetworkLink>
	""", file=fp)

	# Print each placemark to the child file
	nw_fp = open(f"files/{linkfilename}", "w")
	print(kml_header(str(idx)), file=nw_fp)

	for pm in nw_link["d"]:
		print(pm, file=nw_fp)

	print(kml_footer(), file=nw_fp)
	nw_fp.close()

print(kml_footer(), file=fp)
fp.close()

# Now write ALLLLL these files into a KMZ zip file
with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED) as z:
	z.write("doc.kml")
	z.write("files/windarrow.png")

	for idx in range(len(links)):
		linkfilename = f"link{idx:02}.kml"
		z.write(f"files/{linkfilename}")


print(end='\a', file=sys.stderr) # Beep!!
