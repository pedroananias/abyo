#!/usr/bin/python
# -*- coding: utf-8 -*-

#########################################################################################################################################
# ### ABYO - Algal Bloom Yearly Occurences
# ### Module responsible for extracting Algal Bloom Yearly Occurences in a region of interest
#                
# ### Change History
# - Version 1: Repository creation
#########################################################################################################################################

# Dependencies
# Base
import ee
import numpy as np
import pandas as pd
import hashlib
import PIL
import requests
import os
import joblib
import gc
import sys
import traceback
import math
import os
import random
import copy
import re
import time
import warnings
import geojson
from io import BytesIO
from datetime import datetime as dt
from datetime import timedelta as td

# Matplotlib
import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FormatStrFormatter
from matplotlib import cm
from matplotlib.patches import Rectangle

# Local
from modules import misc, gee

# Warning correction from Pandas
pd.plotting.register_matplotlib_converters()
warnings.filterwarnings("ignore")

# Algal Bloom Yearly Occurences
class Abyo:

  # configuration
  anomaly                     = 1
  dummy                       = -99999
  max_tile_pixels             = 10000000 # if higher, will split the geometry into tiles

  # supports
  dates_timeseries            = [None, None]
  dates_timeseries_interval   = []
  sensor_params               = None

  # sample variables
  sample_total_pixel          = None
  sample_clip                 = None
  sample_lon_lat              = [[0,0],[0,0]]
  splitted_geometry           = []
  years_list                  = None

  # masks
  water_mask                  = None
  
  # collections
  collection                  = None
  collection_water            = None
  collection_yearly           = None

  # attributes used in timeseries
  attributes                  = ['cloud', 'occurrence']

  # dataframes
  df_columns                  = ['pixel', 'index', 'year', 'lat', 'lon']+attributes
  df_timeseries               = None

  # hash
  hash_string                 = "abyo-20200629"

  # constructor
  def __init__(self,
               lat_lon:           str,
               date_start:        dt,
               date_end:          dt,
               sensor:            str           = "landsat578",
               cache_path:        str           = None, 
               force_cache:       bool          = False,
               morph_op:          str           = None,
               morph_op_iters:    int           = 1):
    
    # get sensor parameters
    self.sensor_params  = gee.get_sensor_params(sensor)

    # warning
    print()
    print("Selected sensor: "+self.sensor_params['name'])

    # user defined parameters
    self.geometry                     = gee.get_geometry_from_lat_lon(lat_lon)
    self.lat_lon                      = lat_lon
    self.date_start                   = date_start
    self.date_end                     = date_end
    self.sensor                       = sensor
    self.cache_path                   = cache_path
    self.force_cache                  = force_cache
    self.morph_op                     = morph_op
    self.morph_op_iters               = morph_op_iters

    # creating final sensor collection
    collection, collection_water      = gee.get_sensor_collections(geometry=self.geometry, sensor=self.sensor, dates=[dt.strftime(self.date_start, "%Y-%m-%d"), dt.strftime(self.date_end, "%Y-%m-%d")])

    # check if there is imags to use
    if collection.size().getInfo() > 0:

      # correc time series date start and end
      self.dates_timeseries[0]          = dt.fromtimestamp(collection.filterBounds(self.geometry).sort('system:time_start', True).first().get('system:time_start').getInfo()/1000.0)
      self.dates_timeseries[1]          = dt.fromtimestamp(collection.filterBounds(self.geometry).sort('system:time_start', False).first().get('system:time_start').getInfo()/1000.0)

      # create useful time series
      self.collection                   = collection
      self.collection_water             = collection_water
      self.dates_timeseries_interval    = misc.remove_duplicated_dates([dt.fromtimestamp(d/1000.0).replace(hour=00, minute=00, second=00) for d in self.collection.aggregate_array("system:time_start").getInfo()])

      # build yearly collection for label band
      self.years_list                   = ee.List.sequence(ee.Number(int(self.dates_timeseries[0].strftime("%Y"))), ee.Number(int(self.dates_timeseries[1].strftime("%Y"))))
      self.collection_yearly            = ee.ImageCollection.fromImages(self.years_list.map(lambda y: self.collection.filter(ee.Filter.calendarRange(y, y, 'year')).sum().set('year', y)))
      self.years_list                   = self.years_list.getInfo()

      # preprocessing - water mask extraction
      self.water_mask                   = self.create_water_mask(self.morph_op, self.morph_op_iters)

      # count sample pixels and get sample min max coordinates
      self.sample_clip                  = self.clip_image(ee.Image(abs(self.dummy)))
      self.sample_total_pixel           = gee.get_image_counters(image=self.sample_clip.select("constant"), geometry=self.geometry, scale=self.sensor_params['scale'])["constant"]
      coordinates_min, coordinates_max  = gee.get_image_min_max(image=self.sample_clip, geometry=self.geometry, scale=self.sensor_params['scale'])
      self.sample_lon_lat               = [[float(coordinates_min['latitude']),float(coordinates_min['longitude'])],[float(coordinates_max['latitude']),float(coordinates_max['longitude'])]]

      # split geometry in tiles
      self.splitted_geometry            = self.split_geometry()

      # warning
      print("Statistics: scale="+str(self.sensor_params['scale'])+" meters, pixels="+str(self.sample_total_pixel)+", date_start='"+self.dates_timeseries[0].strftime("%Y-%m-%d")+"', date_end='"+self.dates_timeseries[1].strftime("%Y-%m-%d")+"', tiles='"+str(len(self.splitted_geometry))+"', interval_images='"+str(self.collection.size().getInfo())+"', interval_unique_images='"+str(len(self.dates_timeseries_interval))+"', yearly_images='"+str(self.collection_yearly.size().getInfo())+"', water_mask_images='"+str(self.collection_water.size().getInfo())+"', morph_op='"+str(self.morph_op)+"', morph_op_iters='"+str(self.morph_op_iters)+"'")

    # error, no images found
    else:

      # warning
      print("Error: no images were found within the selected period: date_start='"+self.date_start.strftime("%Y-%m-%d")+"', date_end='"+self.date_end.strftime("%Y-%m-%d")+"'!")
      sys.exit()

    # gargage collect
    gc.collect()


  # create the water mask
  def create_water_mask(self, morph_op: str = None, morph_op_iters: int = 1):

    # water mask
    if self.sensor == "modis":
      water_mask = self.collection_water.mode().select('water_mask').eq(1)
    elif "landsat" in self.sensor:
      water_mask = self.collection_water.mode().select('water').eq(2)
    else:
      water_mask = self.collection_water.mode().select('water').gt(0)

    # morphological operations
    if not morph_op is None and morph_op != '':
      if morph_op   == 'closing':
        water_mask = water_mask.focal_max(kernel=ee.Kernel.square(radius=1), iterations=morph_op_iters).focal_min(kernel=ee.Kernel.circle(radius=1), iterations=morph_op_iters)
      elif morph_op == 'opening':
        water_mask = water_mask.focal_min(kernel=ee.Kernel.square(radius=1), iterations=morph_op_iters).focal_max(kernel=ee.Kernel.circle(radius=1), iterations=morph_op_iters)
      elif morph_op == 'dilation':
        water_mask = water_mask.focal_max(kernel=ee.Kernel.square(radius=1), iterations=morph_op_iters)
      elif morph_op == 'erosion':
        water_mask = water_mask.focal_min(kernel=ee.Kernel.square(radius=1), iterations=morph_op_iters)

    # build image with mask
    if self.sensor == "modis":
      return ee.Image(0).blend(ee.Image(abs(self.dummy)).updateMask(water_mask))
    else:
      return ee.Image(0).blend(ee.Image(abs(self.dummy)).updateMask(water_mask)).eq(abs(self.dummy))


  # clipping image
  def clip_image(self, image: ee.Image, scale: int = None, geometry: ee.Geometry = None):
    geometry = self.geometry if geometry is None else geometry
    scale = self.sensor_params['scale'] if scale is None else scale
    return image.clipToBoundsAndScale(geometry=geometry, scale=scale)


  # applying water mask to indices
  def apply_water_mask(self, image: ee.Image, remove_empty_pixels = False):
    for indice in self.attributes:
        image = gee.apply_mask(image, self.water_mask, indice,  indice+"_water", remove_empty_pixels)
    return image


  # extract image from collection
  def extract_image_from_collection(self, date):
    collection = self.collection.filter(ee.Filter.date(date.strftime("%Y-%m-%d"), (date + td(days=1)).strftime("%Y-%m-%d")))
    if int(collection.size().getInfo()) == 0:
      return None
    return self.apply_water_mask(ee.Image(collection.max()).set('system:id', collection.first().get('system:id').getInfo()), False)
    

  # extract image from yearly collection
  def extract_image_from_collection_yearly(self, year):
    collection = self.collection_yearly.filter(ee.Filter.eq('year', int(year)))
    if int(collection.size().getInfo()) == 0:
      return None
    return self.apply_water_mask(ee.Image(collection.first()), False)


  # split images into tiles
  def split_geometry(self):

    # check total of pixels
    if self.sample_total_pixel > self.max_tile_pixels:

      # total of tiles needed
      tiles = math.ceil(self.sample_total_pixel/self.max_tile_pixels)

      # lat and lons range
      latitudes       = np.linspace(self.sample_lon_lat[0][1], self.sample_lon_lat[1][1], num=tiles+1)
      longitudes      = np.linspace(self.sample_lon_lat[0][0], self.sample_lon_lat[1][0], num=tiles+1)

      # go through all latitudes and longitudes
      geometries = []
      for i, latitude in enumerate(latitudes[:-1]):
        for j, longitude in enumerate(longitudes[:-1]):
          x1 = [i,j]
          x2 = [i+1,j+1]
          geometry = gee.get_geometry_from_lat_lon(str(latitudes[x1[0]])+","+str(longitudes[x1[1]])+","+str(latitudes[x2[0]])+","+str(longitudes[x2[1]]))
          geometries.append(geometry)

      # return all created geometries
      return geometries

    else:
      
      # return single geometry
      return [gee.get_geometry_from_lat_lon(self.lat_lon)]


  # get cache files for datte
  def get_cache_files(self, year: int):
    prefix            = self.hash_string.encode()+self.lat_lon.encode()+self.sensor.encode()+str(self.morph_op).encode()+str(self.morph_op_iters).encode()
    hash_image        = hashlib.md5(prefix+(str(year)+'original').encode())
    hash_timeseries   = hashlib.md5(prefix+(str(self.years_list[0])+str(self.years_list[-1])).encode())
    return [self.cache_path+'/'+hash_image.hexdigest(), self.cache_path+'/'+hash_timeseries.hexdigest()]


  # process a timeseries
  def process_timeseries_data(self, force_cache: bool = False):

    # warning
    print()
    print("Starting time series processing ...")

    # attributes
    df_timeseries  = pd.DataFrame(columns=self.df_columns)

    # check timeseries is already on cache
    cache_files    = self.get_cache_files(year=dt.now().strftime("%Y"))
    try:

      # warning
      print("Trying to extract it from the cache...")

      # warning 2
      if self.force_cache or force_cache:
        print("User selected option 'force_cache'! Forcing building of time series...")
        raise Exception()

      # extract dataframe from cache
      df_timeseries = joblib.load(cache_files[1])
   
    # if do not exist, process normally and save it in the end
    except:

      # warning
      print("Error trying to get it from cache: either doesn't exist or is corrupted! Creating it again...")

      # process all years in time series
      for year in self.years_list:

        # extract pixels from image
        # check if is good image (with pixels)
        df_timeseries_ = self.extract_image_pixels(image=self.extract_image_from_collection_yearly(year=year), year=year)
        if df_timeseries_.size > 0:
          df_timeseries = self.merge_timeseries(df_list=[df_timeseries, df_timeseries_])

      # get only good years
      # fix dataframe index
      if not df_timeseries is None:
        df_timeseries['index'] = range(0,len(df_timeseries))

        # save in cache
        if self.cache_path:
          joblib.dump(df_timeseries, cache_files[1])

    # remove dummies
    for attribute in [a for a in self.attributes if a != 'cloud']:
      df_timeseries = df_timeseries[(df_timeseries[attribute]!=abs(self.dummy))]

    # change cloud values
    df_timeseries.loc[df_timeseries['cloud'] == abs(self.dummy), 'cloud'] = 0.0

    # save modified dataframe to its original variable
    self.df_timeseries = df_timeseries[self.df_columns]

    # garbagge collect
    del df_timeseries
    gc.collect()

    # warning
    print("finished!")


  # merge two or more timeseries
  def merge_timeseries(self, df_list: list):
    df            = pd.concat(df_list, ignore_index=True, sort=False)
    df['index']   = np.arange(start=0, stop=len(df), step=1, dtype=np.int64)
    gc.collect()
    return df.sort_values(by=['year', 'pixel'])


  # extract image's coordinates and pixels values
  def extract_image_pixels(self, image: ee.Image, year: int):

    # warning
    print("Processing year ["+str(year)+"]...")

    # attributes
    lons_lats_attributes     = None
    cache_files              = self.get_cache_files(year)
    df_timeseries            = pd.DataFrame(columns=self.df_columns)

    # trying to find image in cache
    try:

      # warning - user disabled cache
      if self.force_cache:
        raise Exception()

      # extract pixel values from cache
      lons_lats_attributes  = joblib.load(cache_files[0])
      if lons_lats_attributes is None:
        raise Exception()

      # check if image is empty and return empty dataframe
      if len(lons_lats_attributes) == 0:
        return df_timeseries

    # error finding image in cache
    except:

      # image exists
      try:

        # check if image has less cloud than the cloud threshold
        clip = self.clip_image(self.extract_image_from_collection_yearly(year=year))
        
        # go through each tile
        lons_lats_attributes = np.array([], dtype=np.float64).reshape(0, len(self.attributes)+2)
        for i, geometry in enumerate(self.splitted_geometry):
          print("Extracting geometry ("+str(len(lons_lats_attributes))+") "+str(i+1)+" of "+str(len(self.splitted_geometry))+"...")
          geometry_lons_lats_attributes = gee.extract_latitude_longitude_pixel(image=clip, geometry=geometry, bands=[a+"_water" for a in self.attributes], scale=self.sensor_params['scale'])
          lons_lats_attributes = np.concatenate((lons_lats_attributes, geometry_lons_lats_attributes))

        # save in cache
        joblib.dump(lons_lats_attributes, cache_files[0])

      # error in the extraction process
      except:
        
        # warning
        print("Error while extracting pixels from year "+str(year)+": "+str(traceback.format_exc()))

        # reset attributes
        lons_lats_attributes = None

    # check if has attributes to process
    try:

      # check if they are valid
      if lons_lats_attributes is None:
        raise Exception()

      # build dataframe
      extra_attributes        = np.array(list(zip([0]*len(lons_lats_attributes),[0]*len(lons_lats_attributes),[year]*len(lons_lats_attributes))))
      df_timeseries           = pd.DataFrame(data=np.concatenate((extra_attributes, lons_lats_attributes), axis=1), columns=self.df_columns).sort_values(['lat','lon'])
      df_timeseries['pixel']  = range(0,len(df_timeseries))

      # gabagge collect
      del lons_lats_attributes, extra_attributes
      gc.collect()

      # return all pixels in an three pandas format
      return df_timeseries

    # no data do return
    except:

      # show error
      print("Error while extracting pixels from year "+str(year)+":")
      print(traceback.format_exc())

      # remove cache file
      if os.path.exists(cache_files[0]):
        os.remove(cache_files[0])
      
      # clear memory
      del lons_lats_attributes
      gc.collect()

      # return empty dataframe
      return df_timeseries


  # save occurrences plot
  def save_occurrences_plot(self, df: pd.DataFrame, folder: str):

    # warning
    print()
    print("Creating occurrences plot to folder '"+folder+"'...")

    # check if folder exists
    if not os.path.exists(folder):
      os.mkdir(folder)
    
    # years list
    years_list  = df.groupby('year')['year'].agg('mean').values

    # build date string
    str_date    = str(int(min(years_list))) + ' to ' + str(int(max(years_list)))

    # number of columns
    zoom        = 5
    columns     = 6 if len(years_list)>=6 else len(years_list)
    rows        = math.ceil(len(years_list)/columns)
    fig_height  = 16/columns
  
    # axis ticks
    xticks      = np.linspace(self.sample_lon_lat[0][1], self.sample_lon_lat[1][1], num=4)
    yticks      = np.linspace(self.sample_lon_lat[0][0], self.sample_lon_lat[1][0], num=4)

    # colorbar tixks
    colorbar_ticks_max          = math.ceil(int(df['occurrence'].max()/zoom))
    colorbar_ticks              = np.linspace(1, colorbar_ticks_max if colorbar_ticks_max > 1 else 2, num=5, dtype=int)
    colorbar_ticks_labels       = [str(l) for l in colorbar_ticks]
    colorbar_ticks_labels[-1]   = str(colorbar_ticks_labels[-1])+"+"


    ###############
    ### Yearly Occurrences

    # create the plot
    fig = plt.figure(figsize=(20,rows*fig_height), dpi=300)
    fig.suptitle('Algal Bloom Yearly Occurrences  ('+str_date+')', fontsize=14, y=1.04)
    fig.autofmt_xdate()
    plt.rc('xtick',labelsize=6)
    plt.rc('ytick',labelsize=6)

    # go through each year
    for i, year in enumerate(years_list):

      # filter year data
      df_year = df[(df['year'] == year)]

      # add plot
      ax = fig.add_subplot(rows,columns,i+1)
      ax.grid(True, linestyle='dashed', color='#909090', linewidth=0.1)
      ax.title.set_text(str(int(year)))
      s = ax.scatter(df_year['lat'], df_year['lon'], s=0.1, c=df_year['occurrence'], cmap=plt.get_cmap('jet'))
      s.set_clim(colorbar_ticks[0], colorbar_ticks[-1])
      cbar = plt.colorbar(s, cax=make_axes_locatable(ax).append_axes("right", size="5%", pad=0), ticks=colorbar_ticks)
      cbar.ax.set_yticklabels(colorbar_ticks_labels)
      ax.margins(x=0,y=0)
      ax.set_xticks(xticks)
      ax.set_yticks(yticks)
      ax.xaxis.set_major_formatter(FormatStrFormatter('%.2f'))
      ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))

    # save it to file
    plt.subplots_adjust(wspace=0.4, hspace=0.4)
    plt.tight_layout()
    fig.savefig(folder+'/occurrences.png', bbox_inches='tight')


    ###############
    ### Yearly Cloud Occurrences

    # create the plot
    fig = plt.figure(figsize=(20,rows*fig_height), dpi=300)
    fig.suptitle('Algal Bloom Yearly Cloud Occurrences  ('+str_date+')', fontsize=14, y=1.04)
    fig.autofmt_xdate()
    plt.rc('xtick',labelsize=6)
    plt.rc('ytick',labelsize=6)

    # go through each year
    for i, year in enumerate(years_list):

      # filter year data
      df_year = df[(df['year'] == year)]

      # add plot
      ax = fig.add_subplot(rows,columns,i+1)
      ax.grid(True, linestyle='dashed', color='#909090', linewidth=0.1)
      ax.title.set_text(str(int(year)))
      s = ax.scatter(df_year['lat'], df_year['lon'], s=0.1, c=df_year['cloud'], cmap=plt.get_cmap('Greys'))
      s.set_clim(colorbar_ticks[0], colorbar_ticks[-1])
      cbar = plt.colorbar(s, cax=make_axes_locatable(ax).append_axes("right", size="5%", pad=0), ticks=colorbar_ticks)
      cbar.ax.set_yticklabels(colorbar_ticks_labels)
      ax.margins(x=0,y=0)
      ax.set_xticks(xticks)
      ax.set_yticks(yticks)
      ax.xaxis.set_major_formatter(FormatStrFormatter('%.2f'))
      ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))

    # save it to file
    plt.subplots_adjust(wspace=0.4, hspace=0.4)
    plt.tight_layout()
    fig.savefig(folder+'/occurrences_clouds.png', bbox_inches='tight')

    # warning
    print("finished!")


  # save occurrences geojson
  def save_occurrences_geojson(self, df: pd.DataFrame, folder: str):

    # warning
    print()
    print("Saving occurrences to geojson at folder '"+folder+"'...")

    # check if folder exists
    if not os.path.exists(folder):
      os.mkdir(folder)

    # years list
    years_list = df.groupby('year')['year'].agg('mean').values

    # save occurrences data
    for year in years_list:
      features = []
      for index, row in df[df['year']==year].iterrows():
        features.append(geojson.Feature(geometry=geojson.Point((row['lat'], row['lon'])), properties={"occurrence": int(row['occurrence']), "cloud": int(row['cloud']), "year": int(row['year'])}))
      fc = geojson.FeatureCollection(features)
      f = open(folder+"/occurrences_"+str(int(year))+".json","w")
      geojson.dump(fc, f)
      f.close()


  # save a collection in tiff (zip) to folder (time series)
  def save_collection_tiff(self, folder: str, folderName: str):

    # build Google Drive folder name where tiffs will be saved in
    folderName = "abyo_"+str(folderName)+".tiff"
    
    # warning
    print()
    print("Saving image collection in tiff to Folder '"+str(folder)+"' (first try, based on image size) or to your Google Drive at folder '"+str(folderName)+"'...")

    # check if folder exists
    if not os.path.exists(folder):
      os.mkdir(folder)

    # select image attributes to be exported
    attributes = ['occurrence_water', 'cloud_water']

    # go through all the collection
    for date in self.dates_timeseries_interval:

      # get image
      image = self.clip_image(self.extract_image_from_collection(date=date), geometry=self.geometry)

      # check if its landsat merge
      bands = [self.sensor_params['red'], self.sensor_params['green'], self.sensor_params['blue']]+attributes
      if self.sensor_params["sensor"] == "landsat578":
        sensor = image.get(self.sensor_params["property_id"]).getInfo()
        if 'LT05' in sensor:
          bands = [gee.get_sensor_params("landsat5")['red'], gee.get_sensor_params("landsat5")['green'], gee.get_sensor_params("landsat5")['blue']]+attributes
        elif 'LE07' in sensor:
          bands = [gee.get_sensor_params("landsat7")['red'], gee.get_sensor_params("landsat7")['green'], gee.get_sensor_params("landsat7")['blue']]+attributes
        elif 'LC08' in sensor:
          bands = [gee.get_sensor_params("landsat")['red'], gee.get_sensor_params("landsat")['green'], gee.get_sensor_params("landsat")['blue']]+attributes

      # First try, save in local folder
      try:
        print("Trying to save "+date.strftime("%Y-%m-%d")+" GeoTIFF to local folder...")
        image_download_url = image.select(bands).getDownloadUrl({"name": date.strftime("%Y-%m-%d"), "region":self.geometry, "filePerBand": True})
        open(folder+'/'+date.strftime("%Y-%m-%d")+'.zip', 'wb').write(requests.get(image_download_url, allow_redirects=True).content)
        print("finished!")

      # Second try, save in Google Drive
      except:
        print("Error! It was not possible to save GeoTIFF localy. Trying to save it in Google Drive...")
        for band in bands:
          task = ee.batch.Export.image.toDrive(image=image.select(band), folder=folderName, description=date.strftime("%Y-%m-%d")+"_"+str(band), region=self.geometry)
          task.start()
          print(task.status())

    # warning
    print("finished!")
  

  # save a collection in png to folder (time series)
  def save_collection_png(self, folder: str, options: dict = {'min':0, 'max': 3000}):
    
    # warning
    print()
    print("Saving image collection to folder '"+folder+"'...")

    # check if folder exists
    if not os.path.exists(folder):
      os.mkdir(folder)

    # go through all the collection
    for date in self.dates_timeseries_interval:

      # get sensor name
      image_collection = self.collection.filter(ee.Filter.date(date.strftime("%Y-%m-%d"), (date + td(days=1)).strftime("%Y-%m-%d")))

      # check if its landsat merge
      bands = None
      if self.sensor_params["sensor"] == "landsat578":
        sensor = image_collection.first().get(self.sensor_params["property_id"]).getInfo()
        if 'LT05' in sensor:
          bands = [gee.get_sensor_params("landsat5")['red'], gee.get_sensor_params("landsat5")['green'], gee.get_sensor_params("landsat5")['blue']]
        elif 'LE07' in sensor:
          bands = [gee.get_sensor_params("landsat7")['red'], gee.get_sensor_params("landsat7")['green'], gee.get_sensor_params("landsat7")['blue']]
        elif 'LC08' in sensor:
          bands = [gee.get_sensor_params("landsat")['red'], gee.get_sensor_params("landsat")['green'], gee.get_sensor_params("landsat")['blue']]

      # check if folder exists
      path_image = folder+'/'+date.strftime("%Y-%m-%d")
      if not os.path.exists(path_image):
        os.mkdir(path_image)

      # save geometries in folder
      for i, geometry in enumerate(self.splitted_geometry):
        self.save_image(image=self.clip_image(self.extract_image_from_collection(date=date), geometry=geometry), path=path_image+"/"+date.strftime("%Y-%m-%d")+"_"+str(i)+".png", bands=bands, options=options)
    
    # warning
    print("finished!")


  # save a image to file
  def save_image(self, image: ee.Image, path: str, bands: list = None, options: dict = {'min':0, 'max': 3000}):
    
    # warning
    print()
    print("Saving image to file '"+path+"'...")

    # default to RGB bands
    if not bands:
      bands = [self.sensor_params['red'], self.sensor_params['green'], self.sensor_params['blue']]

    # extract imagem from GEE using getThumbUrl function and saving it
    imageIO = PIL.Image.open(BytesIO(requests.get(image.select(bands).getThumbUrl(options), timeout=60).content))
    imageIO.save(path)
    
    # warning
    print("finished!")


  # save a dataset to file
  def save_dataset(self, df: pd.DataFrame, path: str):
    
    # warning
    print()
    print("Saving dataset to file '"+path+"'...")

    # saving dataset to file
    df.to_csv(r''+path, index=False)
    
    # warning
    print("finished!")