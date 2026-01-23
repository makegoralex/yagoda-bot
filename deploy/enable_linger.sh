#!/usr/bin/env bash
set -euo pipefail

sudo loginctl enable-linger "$USER"

loginctl show-user "$USER" -p Linger
