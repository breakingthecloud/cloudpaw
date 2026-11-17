#!/usr/bin/env bash
# Build and test the CloudPaw ROS 2 workspace with the SYSTEM Python (ROS 2 Jazzy's).
# uv puts its own python3.12 in ~/.local/bin; if CMake picks it, ament fails with "No module named 'catkin_pkg'".
set -eo pipefail
cd "$(dirname "$0")"
source /opt/ros/jazzy/setup.bash
unset PYTHONPATH_EXTRA
PY=/usr/bin/python3
rm -rf build install log
colcon build --symlink-install --cmake-args -DPython3_EXECUTABLE=$PY -DPYTHON_EXECUTABLE=$PY
colcon test --event-handlers console_direct- --pytest-args -q
colcon test-result --verbose
