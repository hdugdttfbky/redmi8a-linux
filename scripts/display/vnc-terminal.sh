#!/bin/sh
# Terminal shown on the real panel at boot; doubles as an info screen.
# Landscape desktop is 1520x720 -> 120 columns fit comfortably.
exec /usr/bin/xterm \
  -geometry 120x38+8+8 \
  -bg '#101820' -fg '#dbe9f7' \
  -title 'Redmi 8A - System Info' \
  -e /bin/sh /usr/local/bin/system-info.sh
