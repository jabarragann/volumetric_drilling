usage() {
    echo "Usage: $0 -p <path> -s <saveName> -t <topic>"
    echo "  -p <path>       Path to the bag file without extension"
    echo "  -s <saveName>   Name to save the output pivot calibration file"
    echo "  -t <topic>      Ros topic with marker pose "
    echo
    echo "Example: $0 -p /path/to/file -s output_name -t /some_topic"
    exit 1
}

while getopts p:s:t: flag
do
    case "${flag}" in
        p) path=${OPTARG};;
        s) saveName=${OPTARG};;
        t) topic=${OPTARG};;
    esac
done

# Check if all required arguments are provided
if [ -z "$path" ] || [ -z "$saveName" ] || [ -z "$topic" ]; then
    echo "Error: Missing required parameters."
    usage
fi

# # Data collection
# ./recordAll.sh -p "$path";

# Bag to csv
#Pointer tool topic: /atracsys/Pointer/measured_cp
#Surgical Drill topic: /atracsys/Surgical_Drill/measured_cp 
set -x
tf_to_csv.py --bag "./$path".bag --tf_target_frame "$topic"; 

# Pivot calibration
sksurgery_pivot_calibration.py -i "$path".csv -s "$saveName" -c ./../registration_pipeline/config/ransac_config.json;
