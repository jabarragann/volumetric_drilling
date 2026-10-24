# Data recorder

Records the stereo microscope video and the Atracsys ROS topics in one session, using the `record` tool from [dvrk_data](https://github.com/jhu-dvrk/dvrk_data) (no code in this folder, only configuration).

The recorder is one more client of `video_source` (see [Video pipeline](../../README.md#video-pipeline)), so it runs at the same time as AMBF and the viewer.

- `saint_record.json`: recorder configuration (video input + ROS topics).

## Dependencies

`dvrk_data` and the Atracsys packages are pinned to tested commits in [`vcs/external_tools.vcs`](../../vcs/external_tools.vcs). From `saint_ws/src`:

```
vcs import < saint/volumetric_drilling_saint/vcs/external_tools.vcs
sudo apt install libgtkmm-3.0-dev libjsoncpp-dev gstreamer1.0-plugins-ugly   # GUI, config, x264enc
```

Build from the workspace root (`saint_ws`), not from inside a package folder:

```
colcon build --packages-select dvrk_data
```

## Sample recording

Each command in its own terminal, with the workspace sourced:

```
# 1. Video source (must be running before the recorder)
ros2 run simulation_assisted_navigation_framework video_source

# 2. Atracsys tracker publishing the /atracsys/* topics (your usual launch)

# 3. Recorder. Sessions are written relative to the current directory.
mkdir -p ~/saint_data && cd ~/saint_data
ros2 run dvrk_data record -c ~/saint/saint_ws/src/saint/volumetric_drilling_saint/plugin/data_recorder/saint_record.json
```

Start and stop with the **Record** button in the GUI, or by topic:

```
ros2 topic pub --once /record/record std_msgs/msg/Bool "{data: true}"    # start
ros2 topic pub --once /record/record std_msgs/msg/Bool "{data: false}"   # stop
```

Close the window (or Ctrl+C) to finalize the session, then check it:

```
ls ~/saint_data/<YYYYmmdd_HHMMSS>/
ros2 bag info ~/saint_data/<YYYYmmdd_HHMMSS>/rosbag
```

## Output

```
<data_directory>/<YYYYmmdd_HHMMSS>/
├── stereo_microscope.mp4    # side-by-side video, left | right (H.264)
├── stereo_microscope.json   # per-frame timestamps (sidecar)
├── rosbag/                  # MCAP bag with the ROS topics
└── index.json               # session summary
```

`data_directory` in the config is relative to the directory the recorder is launched from, and `~` is not expanded. Use an absolute path to always record to the same place.

## Replay

Replays a session into SAINT as if it were live: `ros2 bag play` publishes the Atracsys topics and `/clock`, and `video_replay` serves the video on the same socket as `video_source`, sending each frame when `/clock` reaches the frame's `recorder_reception_ns`. Bag topics and frames are both stamped by the recorder with `CLOCK_REALTIME`, so they stay in sync without any offset.

Stop `video_source` first (both serve the `camera` socket), then start AMBF as usual and, in two terminals:

```
ros2 run simulation_assisted_navigation_framework video_replay --session ~/saint_data/<YYYYmmdd_HHMMSS>
ros2 bag play ~/saint_data/<YYYYmmdd_HHMMSS>/rosbag --clock 100
```

Or both at once (playback is then controlled with the `/rosbag2_player/*` services instead of the keyboard):

```
ros2 launch simulation_assisted_navigation_framework replay.launch.py session:=<session_dir> [rate:=0.5] [start_offset:=30] [loop:=true]
```

The video follows everything the bag player does:

| Bag player | Video |
| --- | --- |
| `--rate`, arrow keys | plays faster/slower |
| space, `/rosbag2_player/pause`, `toggle_paused` | holds the current frame |
| `--start-offset`, `/rosbag2_player/seek`, `--loop` | jumps to the matching frame |

`--clock 100` publishes `/clock` at 100 Hz, so a frame is shown at most 10 ms late. `--offset-ms` shifts the video against the bag (positive: later), e.g. to compensate a measured video latency (see below). Only the first video segment of a stream is replayed.

## Synchronization (not implemented yet)

Video and ROS data are **not synchronized at capture time**. What exists today:

- **Video:** each frame in the sidecar JSON has `cpu.realtime.recorder_reception_ns`, which is when the *recorder* received the frame (`CLOCK_REALTIME`). The capture-time fields (`left_source_ns`, `right_source_ns`) are `null`, because `video_source` does not attach them.
- **ROS:** bag messages are stamped when the *recorder* receives them (also `CLOCK_REALTIME`). `PoseStamped` topics also carry the tracker's own `header.stamp`.
- Both use the same clock, so they can be aligned offline by nearest timestamp. No alignment tool is provided.

Limitations:

1. **Unknown video latency.** Reception time is later than capture time by the whole pipeline: Decklink buffering, deinterlacing, side-by-side composition and the unixfd transfer. Estimated at tens of milliseconds, not measured, and with some jitter.
2. **Interlaced video.** Each 1080i frame combines two fields captured about 17 ms apart, so a frame has no single exact capture time.
3. **ROS transport latency.** Reception stamps include DDS delivery delay. `Float64` and `IntervalStatistics` topics have no header, so this cannot be corrected for them.
4. **Clocks across machines.** If the tracker runs on another computer, its `header.stamp` is only comparable when both clocks are synchronized (chrony/NTP).

How to solve them:

1. **Capture timestamps in `video_source`.** Add a pad probe on each `decklinkvideosrc` that converts the buffer's capture time to `CLOCK_REALTIME` and attaches it with dvrk_data's `DataCollectionFrameTimestamps` metadata (`include/dvrk_data/cpu_timestamp_meta.hpp`). The recorder already reads this metadata over unixfd and would fill `left_source_ns`/`right_source_ns`. This fixes limitation 1.
2. **Measure the remaining offset.** Measure the latency with a visible event, for example with `dvrk_data`'s `video_latency` tool, and set `estimated_latency` (seconds) in `saint_record.json`. This is useful even without step 1.
3. **Use `header.stamp`** instead of bag reception time for `PoseStamped` topics when aligning. This reduces limitation 3.
4. **Progressive video.** Switch the camera to 1080p output if it supports it. This removes limitation 2.
