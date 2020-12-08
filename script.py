#!/usr/bin/python
# -*- coding: utf-8 -*-

#########################################################################################################################################
# ### ABYO - Algal Bloom Yearly Occurences
# ### Script responsible for executing Algal Bloom Yearly Occurences in a region of interest
#                
# ### Change History
# - Version 1: Repository creation
# - Version 2: Fixed cloud/cloud shadow pixel calculation for Landsat 5,7 and 8
# - Version 3: Fixes to produce relative frequency ratio instead of raw number of occurrencies
# - Version 4: Changed to enable mappig from Modis images and indices FAI and NDVI
#########################################################################################################################################

# ### Version
version = "V4"



# ### Module imports

# Main
import ee
import pandas as pd
import math
import requests
import time
import warnings
import os
import sys
import argparse
import logging
import traceback

# Sub
from datetime import datetime as dt
from datetime import timedelta

# Extras modules
from modules import misc, gee, abyo


# ### Script args parsing

# starting arg parser
parser = argparse.ArgumentParser(description=version)

# create arguments
parser.add_argument('--lat_lon', dest='lat_lon', action='store', default="-48.84725671390528,-22.04547298853004,-47.71712046185493,-23.21347463046867",
                   help="Two diagnal points (Latitude 1, Longitude 1, Latitude 2, Longitude 2) of the study area")
parser.add_argument('--date_start', dest='date_start', action='store', default="1985-01-01",
                   help="Date to start time series")
parser.add_argument('--date_end', dest='date_end', action='store', default="2001-12-31",
                   help="Date to end time series")
parser.add_argument('--name', dest='name', action='store', default="bbhr",
                   help="Place where to save generated files")
parser.add_argument('--sensor', dest='sensor', action='store', default="landsat578",
                   help="Define which sensor will be used")
parser.add_argument('--indice', dest='indice', action='store', default="slope",
                   help="Define which indice will be used to determine algal blooms (NDVI, FAI, SABI or SLOPE")
parser.add_argument('--indice_threshold', dest='indice_threshold', action='store', type=float, default=-0.05,
                   help="Define which indice threshold will be used to determine algal blooms (NDVI>=-0.15, FAI>=-0.004, SABI>=-0.10 and SLOPE>=-0.05")
parser.add_argument('--force_cache', dest='force_cache', action='store_true',
                   help="Force cache reseting to prevent image errors")

# parsing arguments
args = parser.parse_args()




# ### Start

try:

  # Start script time counter
  start_time = time.time()

  # Google Earth Engine API initialization
  ee.Initialize()



  # ### Working directory

  # Data path
  folderRoot = os.path.dirname(os.path.realpath(__file__))+'/data'
  if not os.path.exists(folderRoot):
    os.mkdir(folderRoot)

  # Images path
  folderCache = os.path.dirname(os.path.realpath(__file__))+'/cache'
  if not os.path.exists(folderCache):
    os.mkdir(folderCache)


  
  # ### ABYO execution

  # folder to save results from algorithm at
  folder = folderRoot+'/'+dt.now().strftime("%Y%m%d_%H%M%S")+'[v='+str(version)+'-'+str(args.name)+',dstart='+str(args.date_start)+',dend='+str(args.date_end)+',i='+str(args.indice)+',it='+str(args.indice_threshold)+']'
  if not os.path.exists(folder):
    os.mkdir(folder)

  # create algorithm
  abyo = abyo.Abyo(lat_lon=args.lat_lon,
                   date_start=dt.strptime(args.date_start, "%Y-%m-%d"),
                   date_end=dt.strptime(args.date_end, "%Y-%m-%d"),
                   sensor=args.sensor,
                   cache_path=folderCache, 
                   force_cache=args.force_cache,
                   indice=args.indice,
                   indice_threshold=args.indice_threshold)

  # preprocessing
  abyo.process_timeseries_data()

  # save timeseries in csv file
  abyo.save_dataset(df=abyo.df_timeseries, path=folder+'/timeseries.csv')

  # create plot
  abyo.save_occurrences_plot(df=abyo.df_timeseries, folder=folder)

  # save geojson occurrences and clouds
  abyo.save_occurrences_geojson(df=abyo.df_timeseries, folder=folder+"/geojson")

  # save images to Local Folder (first try, based on image size) or to your Google Drive
  #abyo.save_collection_tiff(folder=folder+"/tiff", folderName=args.name+"_"+version, rgb=False)

  # ### Script termination notice
  script_time_all = time.time() - start_time
  debug = "***** Script execution completed successfully (-- %s seconds --) *****" %(script_time_all)
  print()
  print(debug)

except:

    # ### Script execution error warning

    # Execution
    print()
    print()
    debug = "***** Error on script execution: "+str(traceback.format_exc())
    print(debug)

    # Removes the folder created initially with the result of execution
    script_time_all = time.time() - start_time
    debug = "***** Script execution could not be completed (-- %s seconds --) *****" %(script_time_all)
    print(debug)
