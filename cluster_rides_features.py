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

Dependencies:
  Requires Python Google Maps API client.
"""

from datetime import datetime
import os
import math

import pandas as pd
import googlemaps


## ====================================================================

API_KEY = ""

routes_directory = os.path.join(os.getcwd(), "routes")
pickled_data_path = os.path.join(os.getcwd(),"data", "rides.pkl")

TIME_BETWEEN_GPX_POINTS = 15.0

## ====================================================================


def get_directions(start, end):
  """
  Takes a start and end location as coordinates and returns time and 
  distance of best route using Google Maps API.

  args:
    start: (lat, lon) as a tuple
    end: (lat, lon) as a tuple

  returns:
    seconds: est. fastest time in seconds as int
    meters: est. fastest ride distance in meters as int
  """
  # Construct a query and return result.
  result = gmaps.directions(", ".join(map(str, start)),
                            ", ".join(map(str, end)),
                            mode="walking",
                            departure_time=datetime.now())
  
  # Extract time and distance.
  seconds = result[0]['legs'][0]['duration']['value']
  meters = result[0]['legs'][0]['distance']['value']

  # Return.
  return seconds, meters


def destination_ahead(heading, current_point, end_point):
  """
  Takes a current location, an end location, and a heading and
  returns a boolean True/False if the destination falls in the
  half plane "in front" of the current heading.

  Args:
    heading: current heading in range (0,360) as float
    current_point: tuple representing current location
    end_point: tuple representing destination

  Returns:
    is_ahead: boolean
  """

  # Length in decimal degrees
  buffer_amount = 0.01

  # Get the point on the rider's left hand side.
  if heading - 90 < 0:
    ortho_left = 360 - abs(heading - 90)
  else:
    ortho_left = heading - 90

  new_lat_left = current_point[0] + math.sin(math.radians(90-ortho_left)) * buffer_amount
  new_lon_left = current_point[1] + math.cos(math.radians(90-ortho_left)) * buffer_amount

  point_left = (new_lat_left, new_lon_left)

  # Get the point on the rider's right hand side.
  if heading + 90 > 360:
    ortho_right = (heading + 90) - 360
  else:
    ortho_right = (heading + 90)

  new_lat_right = current_point[0] + math.sin(math.radians(90-ortho_right)) * buffer_amount
  new_lon_right = current_point[1] + math.cos(math.radians(90-ortho_right)) * buffer_amount

  point_right = (new_lat_right, new_lon_right)

  # Get the outer product of the final destination on the halfplane.
  d = (end_point[1]-point_left[1]) * (point_right[0]-point_left[0]) - \
      (end_point[0]-point_left[0]) * (point_right[1]-point_left[1])

  # Return true if outer product is positive, else false.
  if d >= 0:
    return False
  else:
    return True


def haversine(lat1, lon1, lat2, lon2):


def remove_bad_locks(dataframe):
  """
  Removes trackpoints for events in which a rider did not properly
  lock a bike back up.

  Args:
    dataframe: pandas df view

  Returns:
    clean_dataframe: the cleaned view.
  """

  # Reverse Dataframe into new view.
  reversed_df = dataframe.iloc[::-1]

  # Init boolean to mark end of iteration.
  in_motion = False

  # Iterate through new view.
  for idx, trk_pt in reversed_df.iterrows():

    # Check for bike not in motion and drop track_pt from view.
    if trk_pt.displacement < 30:
      reversed_df.drop(idx, inplace=True)
    else:
      break

  # Re-reverse dataframe view and return.
  clean_dataframe = reversed_df.iloc[::-1]

  return clean_dataframe


## ====================================================================


def main():
  """
  Builds GeoDataFrame holding extracted GPX routes and returns.
  """

  # Init list to hold results.
  metrics = []

  # Loop through rides.
  routes = data.route_id.unique()

  for route in routes:

    # Store current view.
    current_route = data[data.route_id == route]

    # Remove bad lock events.
    current_route = remove_bad_locks(current_route)

    # Get start and end lat/lon.
    start = (current_route.iloc[0].lat,
             current_route.iloc[0].lon)
    end = (current_route.iloc[len(current_route)-1].lat,
           current_route.iloc[len(current_route)-1].lon)

    # Get actual time.
    actual_time = current_route.ride_time.max(axis=0) * \
                  TIME_BETWEEN_GPX_POINTS

    # Init metrics for the loop.
    actual_dist = 0
    inride_stops = 0
    inride = False
    dwell_time = 0
    current_displacement = 0
    prev_displacement = 10000000000
    towards_dest_time = 0
    current_crowflies = 0
    prev_crowflies = 0


    # Loop and skip first point.
    for idx, track_pt in current_route.iloc[1:].iterrows():

      # Set pointers.
      current_displacement = track_pt.displacement
      current_crowflies = haversine(start[0], start[1], track_pt.lat, track_pt.lon)

      # Increase trip distance.
      actual_dist += current_displacement

      # If we have gone from riding to not riding, increment stops.
      if current_displacement < 30 and \
         prev_displacement < 30 and inride == True:
        inride_stops += 1
        inride = False
      
      # If we are not in a ride, and are now moving again...
      if current_displacement >= 30 and \
         prev_displacement >= 30 and \
         inride == False:
        inride = True

      # Increment dwell time.
      if current_displacement <= 30:
        dwell_time += 1
      
      # Increment towards_dest_time.
      if current_displacement > 30 and track_pt.heading is not None:
        if current_crowflies >= previous_crowflies:
          towards_dest_time += 1

      # Reassign pointer.
      prev_displacement = current_displacement
      previous_crowflies = current_crowflies

    # Correct number of stops for the end of the ride.
    if inride == False:
      inride_stops -= 1

    # Multiply simple counts by time to get total times.
    dwell_time = dwell_time * TIME_BETWEEN_GPX_POINTS
    towards_dest_time = towards_dest_time * TIME_BETWEEN_GPX_POINTS
    inride_time = actual_time - dwell_time

    # Get Google biking directions time and distance.
    optimal_time, optimal_dist = get_directions(start, end)


    # Append to metrics.
    metrics.append((route,
                    optimal_dist,
                    actual_dist,
                    optimal_time,
                    actual_time,
                    dwell_time,
                    towards_dest_time,
                    inride_time,
                    inride_stops))

    # Convert to a dataframe and format.
    out_df = pd.DataFrame(metrics)
    out_df = out_df.rename(index=str, columns={0: "route_id",
                                               1: "opt_dist",
                                               2: "actu_dist",
                                               3: "opt_time",
                                               4: "actu_time",
                                               5: "dwell_time",
                                               6: "todest_time",
                                               7: "inride_time",
                                               8: "num_stops"})

    out_df["stops_bool"] = np.where(out_df["num_stops"] > 0, 1, 0)
    out_df["dist_ratio"] = out_df.opt_dist / out_df.actu_dist
    out_df["time_ratio"] = out_df.opt_time / out_df.actu_time
    out_df["dwell_ratio"] = out_df.dwell_time / out_df.actu_time
    out_df["todest_ratio"] = out_df.todest_time / out_df.inride_time
    out_df["inride_mph"] = 2.23694 * (out_df.actu_dist / out_df.inride_time)

    # Write out.
    out_df.to_csv("data/metrics4.csv")
    out_df.to_pickle("data/metrics4.pkl")


if __name__ == "__main__":
  
  # Init connection to Google Maps database.
  gmaps = googlemaps.Client(key=API_KEY)

  # Main.
  main()

