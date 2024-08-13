while getopts p:s:t: flag
do
    case "${flag}" in
        p) path=${OPTARG};;
        s) saveName=${OPTARG};;
        t) topic=${OPTARG};;
    esac
done
# # Data collection
# ./recordAll.sh -p "$path";

# Bag to csv
#Pointer tool topic: /atracsys/Pointer/measured_cp
#Surgical Drill topic: /atracsys/Surgical_Drill/measured_cp 
set -x
tf_to_csv.py --bag "./$path".bag --tf_target_frame "$topic"; 

# Pivot calibration
sksurgery_pivot_calibration.py -i "$path".csv -s "$saveName" -c ./../registration_pipeline/config/ransac_config.json;
