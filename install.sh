#!/usr/bin/env bash
set -e

UV="$(which uv)"
SVC_DIR="${SVC_DIR:-$HOME/.config/systemd/user}"

$UV sync

mkdir -p "$SVC_DIR"

for svc in systemd/*.service; do
  $UV run jinja -u strict \
    -D PROJECT_DIR "$PWD" \
    -D UV "$UV" \
    "$svc" > "$SVC_DIR/$(basename "$svc")"
  echo "Installed" "$SVC_DIR/$(basename "$svc")"
done

systemctl --user daemon-reexec
systemctl --user daemon-reload

for svc in systemd/*.service; do
  echo "Enabling $(basename "$svc") ..."
  systemctl --user unmask "$(basename "$svc")" 2>/dev/null || true
  systemctl --user reenable "$(basename "$svc")"
  echo "Starting $(basename "$svc") ..."
  systemctl --user start "$(basename "$svc")"
done

loginctl enable-linger "$USER"

# shellcheck disable=SC2046
systemctl --user status $(cd systemd && ls)
