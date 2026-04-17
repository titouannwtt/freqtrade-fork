# Freqtrade France - Fork personnalisé

Fork de [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) (v2026.3) orienté **trading algorithmique sur Hyperliquid** avec des stratégies DCA agressives en short et long.

## Freqtrade France

Ce repo est maintenu par **Freqtrade France**, une communauté francophone dédiée au trading algorithmique avec Freqtrade.

- **Blog & Guides** : [buymeacoffee.com/freqtrade_france](https://buymeacoffee.com/freqtrade_france/posts)
- **Membership** : Accès aux stratégies, au Discord et à tout le contenu pour 9 EUR/mois

### Guides disponibles (gratuits)

| Guide | Description |
|-------|-------------|
| [Guide Debutant Complet](https://buymeacoffee.com/freqtrade_france/freqtrade-le-guide-complet-du-bot-de-trading-open-source-installation-et-config) | Installation, setup et premiers pas avec Freqtrade |
| [Freqtrade + Hyperliquid](https://buymeacoffee.com/freqtrade_france/connecter-freqtrade-hyperliquid) | Connecter Freqtrade a Hyperliquid (wallet, API, config) |
| [Fichiers de Configuration](https://buymeacoffee.com/freqtrade_france/fichiers-de-configuration-freqtrade-le-guide-de-rfrence) | Reference complete des fichiers de config |
| [Fichiers de Strategies](https://buymeacoffee.com/freqtrade_france/matriser-les-fichiers-de-stratgies-freqtrade-le-guide-de-rfrence) | Creer et gerer ses strategies |
| [Ordres Limite et Marche](https://buymeacoffee.com/freqtrade_france/les-ordres-limite-et-march-le-guide-complet-pour-freqtrade) | Comprendre les types d'ordres |
| [Backtests](https://buymeacoffee.com/freqtrade_france/les-backtests-freqtrade-le-guide-complet-pour-simuler-et-valider-vos-stratgies) | Simuler et valider ses strategies |
| [Hyperopt & Optimisation](https://buymeacoffee.com/freqtrade_france/hyperopt-et-hyperopt-loss-le-guide-complet-freqtrade-pour-optimiser-tes-stratgies) | Optimiser ses strategies avec le machine learning |
| [Stake Unlimited & Compounding](https://buymeacoffee.com/freqtrade_france/stake-amount-unlimited-le-compounding-qui-peut-tout-rendre-au-march) | Le compounding : avantages et risques |

## Exchanges et reglementation francaise

### Exchanges recommandes (enregistres PSAN/DASP en France)

| Exchange | Spot | Futures | Statut France |
|----------|------|---------|---------------|
| [Binance](https://www.binance.com/) | Oui | Oui | Enregistre PSAN |
| [Kraken](https://kraken.com/) | Oui | Oui | Enregistre PSAN |
| [Bitget](https://www.bitget.com/) | Oui | Oui | Enregistre PSAN |
| [Bybit](https://bybit.com/) | Oui | Oui | Enregistre PSAN |
| [OKX](https://okx.com/) | Oui | Oui | Enregistre PSAN (via MyOKX EEA) |
| [Gate.io](https://www.gate.io/ref/6266643) | Oui | Oui | Enregistre PSAN |
| [Bitvavo](https://bitvavo.com/) | Oui | Non | Enregistre PSAN |

### Hyperliquid (DEX - pas de KYC)

[**Hyperliquid**](https://app.hyperliquid.xyz/join/FR0X) est un DEX (exchange decentralise) qui ne necessite pas de KYC. En tant que DEX, il n'est pas soumis a l'enregistrement PSAN/DASP. C'est l'exchange principal utilise dans ce fork pour le trading futures.

**Lien de parrainage** : [app.hyperliquid.xyz/join/FR0X](https://app.hyperliquid.xyz/join/FR0X)

### Exchanges non-recommandes pour la France

- **HTX** (ex-Huobi) : Non enregistre PSAN, acces restreint pour les residents francais
- **Bitmart** : Non enregistre PSAN

> **Note** : La reglementation evolue. Verifiez toujours le [registre AMF des PSAN](https://www.amf-france.org/fr/espace-professionnels/fintech/mes-relations-avec-lamf/obtenir-un-enregistrement-un-agrement-psan) avant d'utiliser un exchange.

## Modifications custom de ce fork

### 1. Detection des fermetures externes (ADL, fermeture manuelle)

Quand une position est fermee directement sur l'exchange (Auto-Deleveraging Hyperliquid, fermeture manuelle via l'UI), Freqtrade vanilla perd la synchronisation et boucle indefiniment. Ce fork detecte automatiquement ces situations et ferme proprement le trade dans la DB.

### 2. Detection des liquidations Hyperliquid

Surveillance active des evenements de liquidation via l'API Hyperliquid. Si une position est liquidee, le trade est ferme avec le bon prix et une notification est envoyee.

### 3. TrendRegularityFilter (plugin pairlist)

Filtre custom qui exclut les paires avec une tendance haussiere reguliere (R2 eleve sur regression lineaire du prix). Utile pour les strategies short : evite de shorter des coins en tendance haussiere forte.

## Structure du repo

```
live_configs/              # Configs des bots (1 fichier JSON par bot)
user_data/strategies/      # Strategies custom (.py) + params hyperopt (.json)
database/                  # Bases SQLite des trades (1 par bot)
freqtrade/freqtradebot.py  # Coeur du bot (+ handler external close)
freqtrade/exchange/        # Adaptateurs exchange (hyperliquid.py modifie)
freqtrade/plugins/pairlist/ # Filtres pairlist (TrendRegularityFilter.py)
launch_bot.sh              # Script de lancement avec auto-restart
```

## Lancer un bot

```bash
# Dans un screen
screen -S mon-bot
./launch_bot.sh mon_bot.json

# Le bot redemarre automatiquement en cas de crash (60s de grace)
```

## Disclaimer

Ce logiciel est a usage educatif uniquement. Ne risquez pas d'argent que vous ne pouvez pas vous permettre de perdre. LES AUTEURS N'ASSUMENT AUCUNE RESPONSABILITE POUR VOS RESULTATS DE TRADING.

---

Base sur [Freqtrade](https://www.freqtrade.io) - Bot de trading crypto open source | [Documentation officielle](https://www.freqtrade.io/en/stable/)
