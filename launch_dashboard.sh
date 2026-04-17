#!/bin/bash
# Launch FreqUI dashboard only (no trading, instant startup)
if [ -z "$1" ]; then
    echo "Usage: $0 <config_file.json>"
    exit 1
fi

config_file="$1"

while true
do
    freqtrade webserver --config live_configs/"$config_file"
    echo "Dashboard arrêté. Redémarrage dans 10 secondes..."
    sleep 10
    echo "Redémarrage!"
done
