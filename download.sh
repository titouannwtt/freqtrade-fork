#!/bin/bash

# Script de téléchargement automatique des données Freqtrade
# Télécharge les données depuis J-10 jusqu'à aujourd'hui

# Configuration
LOG_FILE="/var/log/freqtrade_download.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Fonction de logging
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Calculer la date J-10 (il y a 10 jours)
DATE_J10=$(date -d "10 days ago" +%Y%m%d)
TIMERANGE="${DATE_J10}-"

log_message "Début du téléchargement des données Freqtrade"
log_message "Période de téléchargement: ${TIMERANGE}"

# Vérifier que le répertoire backtest_configs existe
if [ ! -d "$SCRIPT_DIR/backtest_configs" ]; then
    log_message "ERREUR: Le répertoire backtest_configs n'existe pas dans $SCRIPT_DIR"
    exit 1
fi

# Changer vers le répertoire du script
cd "$SCRIPT_DIR" || {
    log_message "ERREUR: Impossible de changer vers le répertoire $SCRIPT_DIR"
    exit 1
}

# Vérifier que freqtrade est installé
if ! command -v freqtrade &> /dev/null; then
    log_message "ERREUR: freqtrade n'est pas installé ou pas dans le PATH"
    exit 1
fi

# Définir les configurations et leurs noms
declare -a configs=(
    "backtest_configs/futures_bybit.json:Bybit Futures"
    "backtest_configs/futures_binance.json:Binance Futures"
    "backtest_configs/USDT_all_binance.json:Binance USDT"
    "backtest_configs/BTC_all_binance.json:Binance BTC"
    "backtest_configs/futures_gateio.json:Gate.io Futures"
    "backtest_configs/USDT_all_gateio.json:Gate.io USDT"
)

# Timeframes à télécharger
TIMEFRAMES="15m 1h 1d 4h 2h 5m 30m"

# Compteurs pour le résumé
total_downloads=0
successful_downloads=0
failed_downloads=0

# Exécuter les téléchargements
for config_info in "${configs[@]}"; do
    config_file="${config_info%:*}"
    config_name="${config_info#*:}"

    log_message "Téléchargement pour $config_name ($config_file)"

    # Vérifier que le fichier de configuration existe
    if [ ! -f "$config_file" ]; then
        log_message "ATTENTION: Le fichier de configuration $config_file n'existe pas, passage au suivant"
        ((failed_downloads++))
        continue
    fi

    # Exécuter la commande freqtrade
    if freqtrade download-data --config "$config_file" --timerange "$TIMERANGE" --timeframe $TIMEFRAMES >> "$LOG_FILE" 2>&1; then
        log_message "✓ Téléchargement réussi pour $config_name"
        ((successful_downloads++))
    else
        log_message "✗ Échec du téléchargement pour $config_name"
        ((failed_downloads++))
    fi

    ((total_downloads++))

    # Petite pause entre les téléchargements pour éviter la surcharge
    sleep 5
done

# Résumé final
log_message "Téléchargements terminés - Total: $total_downloads, Réussis: $successful_downloads, Échecs: $failed_downloads"

# Rotation des logs si le fichier devient trop gros (>10MB)
if [ -f "$LOG_FILE" ] && [ $(stat -c%s "$LOG_FILE") -gt 10485760 ]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
    log_message "Rotation du fichier de log effectuée"
fi

log_message "Script terminé"

exit 0
