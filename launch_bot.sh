#!/bin/bash
# Auto-restart loop for a Freqtrade trading bot.
# Press Ctrl+C during the 60s countdown to stop completely.

if [ -z "$1" ]; then
    echo "Usage: $0 <config_file.json>"
    echo "The config file should exist in live_configs/"
    exit 1
fi

config_file="$1"

while true
do
    freqtrade trade --config live_configs/"$config_file"
    echo "You have 60 seconds to press Ctrl+C to stop the bot."
    echo "Restarting in:"
    for i in 60 50 40 30 20 10
    do
        echo "$i..."
        sleep 10
    done
    echo "Restarting!"
done
