# Backtesting — Tips et garde-fous

## Règles strictes (ne jamais enfreindre)

- 🚫 **Ne jamais faire confiance à un backtest seul**. Sert à vérifier la logique, pas à prédire le live. Toujours valider en walk-forward, puis live avec petit capital. (tips.txt #8, communauté)
- 🚫 **Trailing stops biaisent massivement les backtests**. Sans `--timeframe-detail`, un trailing peut montrer +1300% en BT et seulement +59% avec 5m detail. Ne jamais utiliser le trailing natif — recoder via custom_exit. (tips.txt #10, communauté)
- 🚫 **Toujours `--timeframe-detail 1m` pour BT/hyperopt des stratégies DCA**. Sans ça, fills simulés au prix d'ouverture de bougie → "phantom trades" inexistants en live. Si 1m indispo, 5m minimum mais prévenir que les résultats seront optimistes. (tips.txt #20, CLAUDE.md)
- 🚫 **"Backtesting is not a research tool. Feature importance is."** (Lopez de Prado, 1ère loi). 2ème loi: "Backtesting while researching is like drink driving." 3ème loi: "Every backtest must be reported with all trials involved in its production." (tips.txt #80, Lopez de Prado)
- 🚫 **Pas de pertes dans le backtest = skew négatif caché**. Stratégie qui gagne 90% des trades jusqu'au jour où un event wipe out. Red flag absolue — correspond directement au trap DCA high-winrate. (tips.txt #133, Clenow)
- 🚫 **Transaction cost = bid-ask spread, PAS commissions**. Ta stratégie peut spécifiquement trader les moments où le spread est maximum. Backtester avec un cost fixe en bps rate ce piège. (tips.txt #150, Chan)
- 🚫 **Calibration période A, validation période B DISJOINTES**. Train 2024, valide 2025, rien ne chevauche. Si ça marche pas en holdout, c'est de l'overfitting, point final. 70-80% training / 20-30% holdout strict. (tips.txt #189, Quant 1B)

## Bonnes pratiques (toujours suivre sauf justification explicite)

- ✅ **Min 100 trades pour validation statistique, idéal 500+**. Un BT avec 25 trades sur 3 paires = chance, pas stratégie. (tips.txt #9, communauté)
- ✅ **Baisse de fréquence en walk-forward: vérifier la volatilité avant de conclure overfitting**. Comparer ATR, daily range, volume. Une baisse proportionnelle à la vol = bot fonctionne correctement. (tips.txt #11, communauté)
- ✅ **Le backtest capture les mèches que le live rate**. En BT, ROI vérifié contre high/low de chaque bougie. En live, vérifié toutes les ~20s au prix courant. Les brèves mèches profitables sont capturées en BT mais ratées en live. (tips.txt #12, communauté)
- ✅ **Ordre de traitement diffère**: BT fait DCA-puis-exit, live fait exit-puis-DCA. Quand les deux conditions sont réunies, le BT laisse le DCA "sauver" le trade, le live coupe avant. (tips.txt #13, communauté)
- ✅ **VolumePairList interdit en BT — utilise StaticPairList figée**. Source majeure de divergence BT/live. En BT, toutes les paires sont présentes dès le début, biais de look-ahead. (tips.txt #22, communauté)
- ✅ **"Uncertainty of the past": Monte Carlo sur les params**. Le BT point-estimate est une illusion de précision. Un signal qui devrait pousser à 100% equity n'a statistiquement de quoi pousser qu'à 60/40 ou 80/20. (tips.txt #111, Carver)
- ✅ **Shorting BT gratuit ≠ réalité**. La plupart des engines shortent à n'importe quelle taille sans coût. En réalité quelqu'un doit te prêter, il y a un coût, et on peut te rappeler. Modéliser funding et limites de liquidité même sur perps. (tips.txt #135, Clenow)
- ✅ **Monte Carlo > BT historique pour valider une MÉTHODE**. "Historical practice is not powerful enough to reach a conclusion." Le BT sert à valider UNE stratégie, pas LA méthodologie. (tips.txt #175, Lopez de Prado)

## Conseils avancés (à appliquer selon le contexte)

- 💡 **`custom_stoploss` voit les wicks, `custom_exit` non** — Applicable quand: tu codes un SL custom et veux qu'il soit fiable en BT. Préférer `custom_stoploss` à `custom_exit` pour les stops. (tips.txt #23, communauté)
