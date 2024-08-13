#!/bin/bash

DURATION=60;
usage() { echo "Usage: $0 [-s <45|90>] [-p <string>]" 1>&2; exit 1; }

while getopts ":p:" o; do
    case "${o}" in
        p)
            DURATION=20;
            timeout $DURATION rosbag record -O "$OPTARG" /atracsys/drill_marker/measured_cp /atracsys/drill_marker/registration_error
            echo "Finish data recording!"
            ;;
        *)
            usage
            ;;
    esac
done