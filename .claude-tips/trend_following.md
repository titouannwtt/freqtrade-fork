# Trend Following / Momentum — Tips et garde-fous

> **Rappel contexte** : nos stratégies actives ne sont PAS du trend-following pur (cf. mean_reversion.md). Ce fichier sert de référence si on veut ajouter une brique trend-following pour diversifier (#158).

## Règles strictes (ne jamais enfreindre)

- 🚫 **"Cut losses early, let profits run" = inverse exact du biais humain**. Le cerveau veut prouver qu'il a raison → take profit vite + hold losses. Si les marchés trendent, c'est l'inverse qu'il faut faire (Carver testé sur 31 futures: surperforme sur 27/31). "Couper les pertes rapidement" peut être un exit temporel (max hold) ou retournement d'indicateur (MA crossover inverse), pas forcément un SL serré. Compatible avec mean_reversion.md selon le type d'exit. (tips.txt #124, Carver)
- 🚫 **Trend-following: 70% de trades perdants est NORMAL**. Win rate élevé en trend-following est SUSPECT — la stratégie est mathématiquement construite autour de peu de gros gagnants payant beaucoup de petits perdants. (Inverse pour mean-rev où high winrate est attendu.) (tips.txt #128, Clenow)
- 🚫 **"Trend following doesn't work on stocks. Momentum does."** Sur futures, la diversification fait tout (gold/soybeans/bonds/equities décorrélés). Sur stocks, 500 signaux long = portefeuille beta pur déguisé. Sur crypto c'est PIRE ENCORE (tout corrélé à BTC) — nécessite ranking relatif vs BTC + filtre régime marché. (tips.txt #131, Clenow)

## Bonnes pratiques (toujours suivre sauf justification explicite)

- ✅ **Momentum = pente de régression exponentielle annualisée × R²**. Formule simple et non-optimisable, sur 90 jours. Filtre: MA(200) sur l'index pour ne pas acheter en bear. Disqualifier les actions sous leur MA(100) ou avec gap > 15%. (tips.txt #74, Clenow)
- ✅ **Le momentum fonctionne parce que les investisseurs chassent les gagnants et abandonnent les perdants — biais comportemental persistant**. Ce n'est pas un artefact statistique, c'est de la psychologie humaine. Tant que la nature humaine ne change pas, le momentum fonctionnera. (tips.txt #75, Clenow)
- ✅ **Momentum ≠ trend following — concepts proches mais distincts**. Trend following: futures, fort levier, grande diversification (50-100 instruments décorrélés). Momentum: actions sans levier, basé sur ranking relatif. Profils de risque très différents. (tips.txt #90, Clenow)
- ✅ **Le crowding ne tue PAS le momentum/trend following — il l'alimente**. "People say strategies only work because everybody follows it, or only because nobody knows. Both can't be true." Le S&P 500 lui-même est un index momentum: les actions y entrent parce que leur prix a monté. (tips.txt #94, Clenow)
- ✅ **Momentum sur les actions: il faut un univers suffisamment large (min. 200-500 actions liquides)**. En crypto, même avec 100 pairs, l'univers est dominé par la corrélation à BTC — une stratégie momentum crypto-pure ne reproduit pas les conditions de Clenow. Si momentum crypto: uniquement en mode "ranking relatif vs BTC". (tips.txt #104, Clenow)
- ✅ **Baseline minimale 12-month momentum**: prix aujourd'hui > prix il y a 1 an → long, sinon short. "Mon plus grand regret est de ne pas avoir rendu le modèle encore plus simple. Juste 12-month momentum, deux data points." Cette baseline surperforme souvent les modèles complexes. Équivalent crypto: prix aujourd'hui > prix il y a 90 jours (cycles ~4x plus courts). Si ton modèle ne bat pas ça, problème. (tips.txt #136, Clenow)
- ✅ **Momentum crashes APRÈS chaque crise = pattern historique**. "Momentum strategies have a drawdown in the aftermath of a crisis. It's been that way for the last hundred years." Pas un bug, c'est le pattern. Anticiper. (tips.txt #160, Chan)

## Conseils avancés (à appliquer selon le contexte)

- 💡 **Momentum = slope × R² moyennée sur 125j ET 250j** — Applicable quand: actions equities long-only. Lisse les artefacts d'une seule window et capture trends court ET long terme. En crypto, adapter en 25j+50j ou 50j+100j (vol crypto ~5x celle des actions). Extension de #74. (tips.txt #125, Clenow)
