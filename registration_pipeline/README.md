# Registration pipeline documentation

Code based-on digital twin project: https://github.com/Rxliang/Twin-S/tree/linux

1. Pivot calibration
2. Touch-base registration 

## Install python packages
Install python packages
```bash
pip install -e .
```

Export path with executables
```bash
PATH=$PATH:~/research/discovery_grant/volumetric_drilling/registration_pipeline/pipelines
```

## 1. Pivot calibration

```bash
pivot_calibration.sh -p pivot_drill2 -s pivot_drill2 -t /atracsys/drill_marker/measured_cp
```

## 2. Touch-base registration 

