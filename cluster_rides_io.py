##
##  Clustering Rides
##  cluster_rides_io.py
##
##  Created by Justin Fung on 2/18/18.
##  Copyright 2018 Justin Fung. All rights reserved.
##
## ====================================================================
# pylint: disable=bad-indentation,bad-continuation,multiple-statements
# pylint: disable=invalid-name

"""
Module for converting an external directory of GPX files to a pandas
dataframe for preprocessing and model training.

Usage:
  Please see the README for how to compile the program and run the model.
"""

from datetime import datetime, timedelta
import math
import os
import re

import xml.etree.ElementTree as ET
import fiona
import pandas as pd
import geopandas as gpd
from geopandas.tools import sjoin
from shapely.geometry import Point


## ====================================================================


routes_directory = os.path.join(os.getcwd(), "routes")
pickled_data_path = os.path.join(os.getcwd(),"data", "rides.pkl")


## ====================================================================


def calculate_initial_compass_bearing(pointA, pointB):
    """
    Calculates the bearing between two points.

    Args:
      pointA: start point as tuple, (lat, lon)
      pointB: end point as tuple, (lat, lon)

    Returns:
      compass_bearing: bearing as float between 0 and 360
    """

    # Calculate initial bearing.
    lat1 = math.radians(pointA[0])
    lat2 = math.radians(pointB[0])

    diffLong = math.radians(pointB[1] - pointA[1])

    x = math.sin(diffLong) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1)
            * math.cos(lat2) * math.cos(diffLong))

    initial_bearing = math.atan2(x, y)

    # Normalize the initial bearing and return.
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360

    return compass_bearing


def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on the earth
    (specified in decimal degrees).

    Args:
      lon1: longitude in decimal degrees
      lat1: lattitude in decimal degrees
      lon2: longitude in decimal degrees
      lat2: lattitude in decimal degrees

    Returns:
      meters: haversine distance as float
    """

    # Convert decimal degrees to radians.
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # Apply Haversine formula.
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (math.sin(dlat/2)**2 +
         math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
    c = 2 * math.asin(math.sqrt(a))

    # Radius of earth in km is 6371, convert to meters and return.
    meters = 6371000 * c

    return meters


def gpx2df(gpx_file):
  """
  Converts one gpx file to a pandas dataframe representing a gpx track.

  Args:
    gpx_file: path to a gpx file

  Returns:
    ride_df: geodataframe holding all breadcrumbs and extracted attrs.
  """

  # Get the name from the file.
  name = gpx_file.split('.')[0]
  route_id = int(re.search("[0-9]+", name).group(0))

  # Set XML namespaces and read in the gpx file.
  ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
  ET.register_namespace("", "http://www.topografix.com/GPX/1/0")
  gpx_path = os.path.join(os.getcwd(), "routes", gpx_file)
  tree = ET.parse(gpx_path)
  namespace = "{http://www.topografix.com/GPX/1/0}"

  # Store the root of the XML tree.
  root = tree.getroot()

  # Retrieve the start time of the route.
  dt_raw = root[0].text
  dt = re.sub("-0[45]{1}:00", "", dt_raw)
  dt_obj = datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S')
  
  #if re.search("-04:00", dt_raw):
  #  dt_obj = dt_obj - timedelta(hours=4)
  #elif re.search("-05:00", dt_raw):
  #  dt_obj = dt_obj - timedelta(hours=5)

  # Time stamps.
  start_time = int(dt_obj.strftime('%H'))
  weekday = dt_obj.weekday()

  # Get the track(s) from the root.
  trks = root.findall(namespace + "trk")

  # Init df to hold cleaned data.
  ride_df = pd.DataFrame()
  crs = {'init': 'epsg:4326'}

  # Combine the breadcrumbs from multi-segment trips into one list.
  breadcrumbs = []
  for track in trks:
    breadcrumbs += track[0].findall(namespace + "trkpt")

  # Init counters and pointers.
  heading = None
  displacement = 0
  prev_pts = (None, None)

  # Loop through all points in the track segment.
  for count, breadcrumb in enumerate(breadcrumbs):

    # Get lat and long attributes.
    lat = float(breadcrumb.get('lat'))
    lon = float(breadcrumb.get('lon'))
    current_pts = (lat, lon)

    # Get type.
    ride_type = breadcrumb[0].text

    # Get displacement.
    if count > 0:
      displacement = haversine(prev_pts[0], prev_pts[1],
                               current_pts[0], current_pts[1])

    # Update heading only if rider has moved.
    if count > 0 and displacement > 30:
      heading = calculate_initial_compass_bearing(prev_pts, current_pts)

    # Init Pandas Series.
    pseries = pd.Series(data=[lat, lon, ride_type, dt_raw,
                              gpx_file, route_id, start_time, weekday,
                              count,
                              heading,
                              displacement],
                        index=['lat', 'lon', 'ride_type', 'datetime_raw',
                               'gpx_file', 'route_id', 'start_time',
                               'day_of_week',
                               'ride_time',
                               'heading', 'displacement'])

    # Append Ride to Dataframe.
    ride_df = ride_df.append(pseries, ignore_index=True)

    # Update previous breadcrumb.
    prev_pts = current_pts

  # Exit.
  return ride_df


def build_X(routes_dir):
  """
  Builds a master dataframe to hold multiple geodataframes, each
  representing a GPX routes.

  Args:
    routes_dir: directory holding GPX routes

  Returns:
    X: master geodataframe
  """

  # Get file names.
  routes = [i for i in os.listdir(routes_dir) if i.startswith('route')]

  # Init empty DF to hold extracts GPX routes.
  X = pd.DataFrame()

  # Loop through the routes and append.
  for i, route in enumerate(routes):

    X = X.append(gpx2df(route))
    print("==================")
    print("==================")
    print("==================")
    print("Cleaned route: ", i)
    print("==================")
    print("==================")
    print("==================")

  # Reset the indexing and return.
  X = X.reset_index(drop=True)
  X['idx'] = range(0, len(X))

  # Pickle the result.
  X.to_pickle(pickled_data_path)

  return


## ====================================================================


def main():
  """
  Builds GeoDataFrame holding extracted GPX routes and returns.
  """

  # Build Pandas Dataframe.
  build_X(routes_directory)

  return


if __name__ == "__main__":
  main()

