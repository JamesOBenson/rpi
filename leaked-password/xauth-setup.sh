#!/bin/bash
# Add a random MIT-MAGIC-COOKIE-1 for display :0 into rpi's Xauthority
cookie=$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')
xauth -f /home/rpi/.Xauthority add :0 MIT-MAGIC-COOKIE-1 "$cookie"
xauth -f /home/rpi/.Xauthority list