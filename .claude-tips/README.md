# .claude-tips/ — Système de garde-fous pour Claude

## Quoi

Ce répertoire contient les règles de trading algorithmique distillées dans `tips.txt` (199 tips, sources : Carver, Clenow, Chan, Lopez de Prado, Beetcoin, Connors, SalsaTekila, Quant 1B, MacroAlf, communauté Freqtrade France), organisées par catégorie pour consultation rapide.

Chaque tip est référencé par son numéro `tips.txt #N` pour traçabilité.

## Pour Claude — comment utiliser ce système

**Avant toute action liée au trading algo** :

1. Identifie le type de demande utilisateur dans la table ci-dessous.
2. Lis les fichiers de tips correspondants AVANT de répondre.
3. Si la demande utilisateur contredit une **règle stricte** (🚫) :
   - Signale-le clairement
   - Cite le tip et sa source (ex: "tips.txt #40")
   - Explique pourquoi c'est problématique
   - Propose une alternative conforme
4. Si l'utilisateur insiste malgré l'avertissement, exécute mais documente l'avertissement dans le code (commentaire) ou dans la réponse.
5. Pour les **bonnes pratiques** (✅) : applique par défaut, justifie si tu t'en écartes.
6. Pour les **conseils avancés** (💡) : évalue si le contexte s'applique avant de proposer.

## Table de correspondance

| Demande utilisateur | Fichiers à consulter |
|---|---|
| "Analyse cette stratégie" | `strategy_evaluation.md`, `risk_management.md` + fichier spécifique au type (mean_reversion / trend_following / machine_learning) |
| "Crée-moi une stratégie" / "Code une stratégie" | `strategy_development.md`, `data_quality.md`, `risk_management.md` + fichier type stratégie |
| "Lance un backtest" / "Analyse ce backtest" | `backtesting.md`, `data_quality.md`, `strategy_evaluation.md` |
| "Lance un hyperopt" / "Choix loss function" | `hyperopt.md`, `backtesting.md`, `data_quality.md`, `psychology.md` |
| "Que penses-tu de mes bots en live" / "Diagnostic live" | `live_trading.md`, `risk_management.md`, `strategy_evaluation.md` |
| "Optimise cette stratégie" | `hyperopt.md`, `strategy_development.md`, `psychology.md` |
| "Ajoute une fonctionnalité au bot" | `strategy_development.md`, `live_trading.md` |
| "Modifie le sizing / DCA / leverage" | `risk_management.md`, fichier type stratégie |
| "Filtre / pairlist / régime de marché" | `market_analysis.md`, `risk_management.md` |
| "Discussion ML / FreqAI" | `machine_learning.md`, `data_quality.md` |
| "Crée une config" / "throttle" / "pricing" / "pairlist" / "timeout" | `live_trading.md` (§ process_throttle_secs, capital & sizing, entry/exit pricing, chaînage pairlist, unfilledtimeout) |
| Question conceptuelle ("pourquoi X marche") | `psychology.md` + fichier thématique |

## Stratégie spécifique (notre cas par défaut)

Le contexte par défaut de ce repo est **DCA mean-reversion (long oversold + short overbought) sur Hyperliquid USDC perps en 15m**. Donc en cas de doute :

- Consulte `mean_reversion.md` plutôt que `trend_following.md`
- Consulte `dca_strategies` (intégré dans `mean_reversion.md`)
- Le `machine_learning.md` est essentiellement pour information — l'utilisateur a décidé de ne PAS utiliser de ML sur 15m (cf. tips.txt #36 et #162)

## Légende

- 🚫 **Règle stricte** : ne jamais enfreindre sans avertissement explicite
- ✅ **Bonne pratique** : suivre par défaut, justifier toute exception
- 💡 **Conseil avancé** : applicable selon le contexte précisé

## Source de vérité

`tips.txt` à la racine du repo reste la source de vérité longue. Les fichiers `.claude-tips/` sont des index actionnables et concis. En cas de divergence, `tips.txt` prime.
