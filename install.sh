#!/usr/bin/env bash
set -e

UV="$(which uv)"
SVC_DIR="${SVC_DIR:-$HOME/.config/systemd/user}"

$UV sync

mkdir -p "$SVC_DIR"

for svc in systemd/*.service; do
  jinja -u strict \
    -D PROJECT_DIR "$PWD" \
    -D UV "$UV" \
    "$svc" > "$SVC_DIR/$(basename "$svc")"
done

systemctl --user daemon-reexec
systemctl --user daemon-reload
systemctl --user enable dht-sensor.service
loginctl enable-linger "$USER"

# shellcheck disable=SC2046
systemctl --user status $(cd systemd && ls)
