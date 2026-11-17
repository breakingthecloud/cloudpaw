#!/usr/bin/env bash
# CloudPaw ops EC2 bootstrap (Ubuntu 24.04, x86_64). Idempotent: safe to run again.
# Installs: ROS 2 Jazzy desktop + dev tools, Gazebo (ros_gz) + ros2_control, foxglove_bridge, AWS CLI v2,
# MuJoCo headless rendering libs, and for user 'ubuntu': uv (+ Python 3.12), Node 22 (fnm), pnpm, AgentCore CLI.
# Log: /var/log/cloudpaw-bootstrap.log   Done marker: /var/lib/cloudpaw/bootstrap.done
set -euo pipefail
exec >>/var/log/cloudpaw-bootstrap.log 2>&1
echo "=== bootstrap start $(date -u +%FT%TZ)"
export DEBIAN_FRONTEND=noninteractive
mkdir -p /var/lib/cloudpaw

apt-get update -y
apt-get install -y software-properties-common curl git unzip build-essential python3-venv locales \
  libegl1 libgl1 libosmesa6 libglfw3
locale-gen en_US.UTF-8 && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
add-apt-repository -y universe

# --- ROS 2 Jazzy (official apt source package) ------------------------------------------------------------------
if [ ! -f /etc/apt/sources.list.d/ros2.sources ]; then
  V=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F '"tag_name"' | awk -F'"' '{print $4}')
  CODENAME=$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
  curl -fsSL -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${V}/ros2-apt-source_${V}.${CODENAME}_all.deb"
  dpkg -i /tmp/ros2-apt-source.deb
fi
apt-get update -y
apt-get install -y ros-jazzy-desktop ros-dev-tools ros-jazzy-ros-gz ros-jazzy-gz-ros2-control \
  ros-jazzy-ros2-control ros-jazzy-ros2-controllers ros-jazzy-xacro ros-jazzy-foxglove-bridge
[ -d /etc/ros/rosdep/sources.list.d ] || rosdep init
echo "--- ROS done"

# --- AWS CLI v2 ---------------------------------------------------------------------------------------------------
if ! command -v aws >/dev/null; then
  curl -fsSL -o /tmp/awscliv2.zip https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip
  unzip -q -o /tmp/awscliv2.zip -d /tmp && /tmp/aws/install
fi
echo "--- AWS CLI done"

# --- user tools (ubuntu): uv, Node 22, pnpm, AgentCore CLI ----------------------------------------------------------
sudo -iu ubuntu bash -s <<'USER'
set -euo pipefail
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.12
[ -x "$HOME/.local/share/fnm/fnm" ] || curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell
export PATH="$HOME/.local/share/fnm:$PATH"; eval "$(fnm env --shell bash)"
fnm install 22 && fnm default 22 && fnm use 22
npm install -g pnpm@11
export PNPM_HOME="$HOME/.local/share/pnpm"; export PATH="$PNPM_HOME/bin:$PNPM_HOME:$PATH"; mkdir -p "$PNPM_HOME"
pnpm add -g @aws/agentcore
# Ubuntu's .bashrc returns early in non-interactive shells, so the environment lives in its own file.
cat > ~/.cloudpaw_env <<'RC'
source /opt/ros/jazzy/setup.bash
export PATH="$HOME/.local/bin:$HOME/.local/share/fnm:$PATH"; eval "$(fnm env --shell bash)"
export PNPM_HOME="$HOME/.local/share/pnpm"; export PATH="$PNPM_HOME/bin:$PNPM_HOME:$PATH"
export AWS_REGION=us-east-1 MUJOCO_GL=egl
RC
grep -q "cloudpaw_env" ~/.bashrc || echo 'source ~/.cloudpaw_env  # cloudpaw' >> ~/.bashrc
rosdep update || true
USER
echo "--- user tools done"

{
  echo "date: $(date -u +%FT%TZ)"
  echo "ros: $(dpkg-query -W -f='${Version}' ros-jazzy-desktop)"
  echo "gz: $(dpkg-query -W -f='${Version}' ros-jazzy-ros-gz)"
  echo "aws: $(aws --version 2>&1)"
  sudo -iu ubuntu bash -c 'source ~/.cloudpaw_env; echo "uv: $(uv --version) | node: $(node -v) | pnpm: $(pnpm -v) | agentcore: $(agentcore --version | tail -1)"'
} > /var/lib/cloudpaw/bootstrap.done
echo "=== bootstrap done $(date -u +%FT%TZ)"
