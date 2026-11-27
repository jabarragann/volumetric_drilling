# Tests to check system

From root execute the following two commands in separate terminals.

```
ambf_simulator --launch_file launch.yaml \
               -l 6,8,13 --mute true --nt 1 \
               --tf_list resources/ros2_test_assets/phantom01/motions/tf_config.yaml \
               --cpf resources/ros2_test_assets/main_camera_info.yaml
```

Sample atracsys data
```
python scripts/ros2_tools/publish_recorded_data_ros2.py
```
