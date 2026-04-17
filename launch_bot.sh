if [ -z "$1" ]; then
    echo "Usage: $0 <config_file.json>"
    echo "The config file should exist in live_configs/"
    exit 1
fi

config_file="$1"

while true
do
    freqtrade trade --config live_configs/"$config_file"
    echo "Vous avez 60 secondes pour faire ctrl + c pour couper le serveur"
    echo "restart dans:"
    for i in 60 50 40 30 20 10
    do
        echo "$i..."
        sleep 10
    done
    echo "Redemarrage!"
done
