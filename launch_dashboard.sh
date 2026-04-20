#!/bin/bash
# Auto-restart loop for FreqUI in webserver-only mode (no trading).

if [ -z "$1" ]; then
    echo "Usage: $0 <config_file.json>"
    exit 1
fi

config_file="$1"

while true
do
    freqtrade webserver --config live_configs/"$config_file"
    echo "Dashboard stopped. Restarting in 10 seconds..."
    sleep 10
    echo "Restarting!"
done
