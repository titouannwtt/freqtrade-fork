#!/bin/bash

# Automated Freqtrade data download script.
# Downloads candle data from the last 10 days for all configured exchanges.

LOG_FILE="/var/log/freqtrade_download.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

DATE_J10=$(date -d "10 days ago" +%Y%m%d)
TIMERANGE="${DATE_J10}-"

log_message "Starting Freqtrade data download"
log_message "Download period: ${TIMERANGE}"

if [ ! -d "$SCRIPT_DIR/backtest_configs" ]; then
    log_message "ERROR: backtest_configs directory not found in $SCRIPT_DIR"
    exit 1
fi

cd "$SCRIPT_DIR" || {
    log_message "ERROR: cannot cd to $SCRIPT_DIR"
    exit 1
}

if ! command -v freqtrade &> /dev/null; then
    log_message "ERROR: freqtrade is not installed or not in PATH"
    exit 1
fi

declare -a configs=(
    "backtest_configs/futures_bybit_162.json:Bybit Futures"
    "backtest_configs/futures_binance_163.json:Binance Futures"
    "backtest_configs/USDT_binance_408.json:Binance USDT"
    "backtest_configs/BTC_binance_201.json:Binance BTC"
    "backtest_configs/futures_gateio_590.json:Gate.io Futures"
    "backtest_configs/USDT_gateio_2702.json:Gate.io USDT"
)

TIMEFRAMES="15m 1h 1d 4h 2h 5m 30m"

total_downloads=0
successful_downloads=0
failed_downloads=0

for config_info in "${configs[@]}"; do
    config_file="${config_info%:*}"
    config_name="${config_info#*:}"

    log_message "Downloading data for $config_name ($config_file)"

    if [ ! -f "$config_file" ]; then
        log_message "WARNING: config file $config_file not found, skipping"
        ((failed_downloads++))
        continue
    fi

    if freqtrade download-data --config "$config_file" --timerange "$TIMERANGE" --timeframe $TIMEFRAMES >> "$LOG_FILE" 2>&1; then
        log_message "OK: download succeeded for $config_name"
        ((successful_downloads++))
    else
        log_message "FAIL: download failed for $config_name"
        ((failed_downloads++))
    fi

    ((total_downloads++))

    sleep 5
done

log_message "Downloads complete — Total: $total_downloads, OK: $successful_downloads, Failed: $failed_downloads"

if [ -f "$LOG_FILE" ] && [ $(stat -c%s "$LOG_FILE") -gt 10485760 ]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
    log_message "Log file rotated"
fi

log_message "Script finished"

exit 0
