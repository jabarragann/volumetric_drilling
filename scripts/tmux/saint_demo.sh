#!/usr/bin/env bash
# Open a tmux session with two side-by-side panes. Each pane sources the given ROS
# workspace setup file, then has its command typed in but not run. Run it from
# the repo root:
#
#   bash scripts/tmux/saint_demo.sh <path/to/install/setup.bash|setup.zsh>
#
# Left pane: the simulator. Right pane: sample Atracsys data.
# Press Enter in each pane to run its command (start ambf first).
# Switch panes with Ctrl+b and the arrow keys; detach with Ctrl+b d.

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <path/to/install/setup.bash|setup.zsh>" >&2
    exit 1
fi
if [[ ! -f "$1" ]]; then
    echo "Setup file not found: $1" >&2
    exit 1
fi
SETUP="$(realpath "$1")"

# Open the panes with the shell that matches the setup file.
case "$SETUP" in
    *.zsh) PANE_SHELL=zsh ;;
    *.bash) PANE_SHELL=bash ;;
    *) echo "Expected a setup.bash or setup.zsh file: $SETUP" >&2; exit 1 ;;
esac

SESSION=saint_demo

AMBF_PANE="$(tmux new-session -d -P -F '#{pane_id}' -s "$SESSION" -c "$PWD" "$PANE_SHELL")"
tmux send-keys -t "$AMBF_PANE" "source '$SETUP'" Enter
tmux send-keys -t "$AMBF_PANE" "ambf_simulator --launch_file launch.yaml -l 6,8,13 --mute true --nt 1 --tf_list resources/ros2_test_assets/phantom01/motions/tf_config.yaml --cpf resources/ros2_test_assets/main_camera_info.yaml"

# Vertical split: second pane to the right.
ATRACSYS_PANE="$(tmux split-window -h -P -F '#{pane_id}' -t "$AMBF_PANE" -c "$PWD" "$PANE_SHELL")"
tmux send-keys -t "$ATRACSYS_PANE" "source '$SETUP'" Enter
tmux send-keys -t "$ATRACSYS_PANE" "python scripts/ros2_tools/publish_recorded_data_ros2.py"

tmux select-pane -t "$AMBF_PANE"
tmux attach -t "$SESSION"
