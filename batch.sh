#!/bin/bash 

# THIS DIR
BASEDIR="$( cd "$( dirname "$0" )" && pwd )"

# ARGUMENTS GENERAL
PYTHON=${1:-"python"}
SCRIPT="script.py"
CLEAR="sudo pkill -f /home/pedro/anaconda3"

# ATTRIBUTES
declare -a MIN_OCCS=(4)

# SHOW BASE DIR
echo "$PYTHON $BASEDIR/$SCRIPT"


############################################################################################
## YEARS
LAT_LON="-48.56620427006758,-22.457495449468666,-47.9777042099919,-22.80261692472655"

# EXECUTIONS
for year in {1985..2020}
do
	for min_occ in "${MIN_OCCS[@]}"
	do
		eval "$PYTHON $BASEDIR/$SCRIPT --lat_lon=$LAT_LON --date_start=$year-01-01 --date_end=$year-03-31 --date_start2=$year-10-01 --date_end2=$year-12-31 --min_occurrence=$min_occ --shapefile=users/pedroananias/bruno/bbhr"
	done
done
############################################################################################