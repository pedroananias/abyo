# Algal Bloom Yearly Occurrence

Module responsable for extracting Algal Bloom Yearly Occurences in a region of interest based on images from Google Earth Engine API



### Dependencies

- Python 3.7.7 64-bit ou superior
- Modules: oauth2client earthengine-api matplotlib pandas numpy requests pillow natsort geojson argparse logging hashlib joblib gctraceback warnings



### Attention, before running:

Before running the script and after installing the libraries, you must authenticate with the Google Earth Engine API using the following command:

```
earthengine authenticate
```



### How to execute the default script?

python /path/to/abyo/script.py --lat_lon=-48.84725671390528,-22.04547298853004,-47.71712046185493,-23.21347463046867 --name=bbhr --date_start=1985-01-01 --date_end=1018-12-31




### What are the results?

The script will generate annual results of occurrence of algae and clouds blooming in the inserted study area. Therefore, a folder located in 'data' is created and named based on the date and version of the script executed. Example: /path/to/abyo/data/20200701_111426[v=V1-bbhr,date_start=1985-01-01,date_end=2018-12-31]

The following results are generated:

- timeseries.csv (Annual time series of pixels, latitude, longitude, sum of the Slope and labels and occurrences of algae bloom (based on the threshold of the Slope algorithm) and clouds)
- occurrences.png (Graphs of occurrences separated annually from algal blooms)
- occurrences_clouds.png (Graphs of occurrences separated annually from clouds)
- occurrences.json (GeoJSON of occurrences with parameters (occurrence, cloud and year) that can be imported into QGIS and filtered)



### Exporting GeoTIFFs to Google Drive

When using the 'save_collection_tiff' function, a folder called 'abyo.data.tiff' will be created in the Google Drive of the user who authenticated. Daily images used in the composition of the annual time series are saved. These images will be separated by the following bands: Red, Green, Blue and Label (-1 = cloud, 0 = regular and 1 = anomaly). However, after running the Abyo script, images are likely to take a while to be inserted into Drive due to processing time. It is necessary to wait approximately 1 day until they are all available, depending on the size of the study area.



### Example

```
# Import
import ee
from modules import abyo

# Initialize Google Earth Engine
ee.Initialize()

# folder where to save results
folder = "/path/to/desired/folder"

# create algorithm object
abyo = abyo.Abyo(lat_lon="-48.84725671390528,-22.04547298853004,-47.71712046185493,-23.21347463046867",
                date_start=dt.strptime("1985-01-01", "%Y-%m-%d"),
                date_end=dt.strptime("2018-12-31", "%Y-%m-%d"),
                sensor="landsat578",
                cache_path=folder, 
                force_cache=False)

# creating yearly timeseries
abyo.process_timeseries_data()

# save timeseries in csv file
abyo.save_dataset(df=abyo.df_timeseries, path=folder+'/timeseries.csv')

# save ocurrences plot (yearly and clouds)
abyo.save_occurrences_plot(df=abyo.df_timeseries, folder=folder)

# save geojson occurrences
abyo.save_occurrences_geojson(df=abyo.df_timeseries, folder=folder)

# save daily images to Google Drive
abyo.save_collection_tiff()
```