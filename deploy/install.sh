#!/usr/bin/env bash
set -euo pipefail

repo_url="${COURIER_REPO_URL:-https://github.com/happyhippovip/2026-courier.git}"
branch="${COURIER_BRANCH:-main}"
install_dir="${COURIER_INSTALL_DIR:-/opt/courier}"
state_dir="${COURIER_STATE_DIR:-/var/lib/courier}"
config_dir=/etc/courier

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

if ! id -u courier >/dev/null 2>&1; then
  useradd --system --home-dir "$state_dir" --create-home --shell /usr/sbin/nologin courier
fi

if [[ -d "$install_dir/.git" ]]; then
  git -C "$install_dir" fetch --depth=1 origin "$branch"
  git -C "$install_dir" checkout --detach FETCH_HEAD
elif [[ -e "$install_dir" ]]; then
  echo "$install_dir exists but is not a Courier checkout; refusing to replace it." >&2
  exit 1
else
  git clone --depth=1 --branch "$branch" "$repo_url" "$install_dir"
fi

install -d -o courier -g courier -m 0750 "$state_dir/events" "$state_dir/memory" "$config_dir"
if [[ -e "$install_dir/events" && ! -L "$install_dir/events" ]]; then
  cp -a "$install_dir/events/." "$state_dir/events/"
  rm -rf "$install_dir/events"
fi
ln -sfn "$state_dir/events" "$install_dir/events"
chown -R courier:courier "$state_dir/events" "$state_dir/memory"

chmod 0755 "$install_dir/deploy/run-supervisor.sh"
install -m 0644 "$install_dir/deploy/courier.service" /etc/systemd/system/courier.service
install -d -m 0755 /etc/systemd/journald@courier.conf.d
install -m 0644 "$install_dir/deploy/journald-courier.conf" \
  /etc/systemd/journald@courier.conf.d/20-storage.conf
if [[ ! -e "$config_dir/courier.env" ]]; then
  install -m 0640 -o root -g courier "$install_dir/deploy/env.example" "$config_dir/courier.env"
fi
if [[ ! -e "$config_dir/courier.secrets" ]]; then
  install -m 0600 -o root -g root /dev/null "$config_dir/courier.secrets"
fi

systemctl daemon-reload
systemctl enable courier.service
echo "Courier is installed but not started. Configure $config_dir/courier.env and $config_dir/courier.secrets, then run: systemctl start courier.service"
