#!/bin/bash 

# THIS DIR
BASEDIR="$( cd "$( dirname "$0" )" && pwd )"

# ARGUMENTS GENERAL
PYTHON=${1:-"python"}
SCRIPT="script.py"
CLEAR="sudo pkill -f /home/pedro/anaconda3"

# ATTRIBUTES
declare -a INDICES=("mndwi" "ndvi" "fai" "sabi" "slope" "mndwi,ndvi" "mndwi,fai" "mndwi,sabi" "mndwi,slope" "ndvi,fai" "ndvi,sabi" "ndvi,slope" "fai,sabi" "fai,slope" "sabi,slope" "mndwi,ndvi,fai" "mndwi,ndvi,sabi" "mndwi,ndvi,slope" "mndwi,fai,sabi" "mndwi,fai,slope" "mndwi,sabi,slope" "ndvi,fai,sabi" "ndvi,fai,slope" "ndvi,sabi,slope" "fai,sabi,slope" "mndwi,ndvi,fai,sabi" "mndwi,ndvi,fai,slope" "mndwi,ndvi,sabi,slope" "mndwi,fai,sabi,slope" "ndvi,fai,sabi,slope" "mndwi,ndvi,fai,sabi,slope") # "mndwi" "ndvi" "fai" "sabi" "slope"

# SHOW BASE DIR
echo "$PYTHON $BASEDIR/$SCRIPT"


############################################################################################
## PERIOD 1
LAT_LON="-48.84725671390528,-22.04547298853004,-47.71712046185493,-23.21347463046867"

# EXECUTIONS
for indice in "${INDICES[@]}"
do
	echo "$PYTHON $BASEDIR/$SCRIPT --lat_lon=$LAT_LON --date_start=1985-01-01 --date_end=2001-12-31 --indice=$indice"
done

############################################################################################


############################################################################################
## PERIOD 2
LAT_LON="-48.84725671390528,-22.04547298853004,-47.71712046185493,-23.21347463046867"

# EXECUTIONS
for indice in "${INDICES[@]}"
do
	echo "$PYTHON $BASEDIR/$SCRIPT --lat_lon=$LAT_LON --date_start=2002-01-01 --date_end=2018-12-31 --indice=$indice"
done

############################################################################################