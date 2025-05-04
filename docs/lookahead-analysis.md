# Lookahead analysis

This page explains how to validate your strategy in terms of lookahead bias.

Lookahead bias is the bane of any strategy since it is sometimes very easy to introduce this bias, but can be very hard to detect.

Backtesting initializes all timestamps (loads the whole dataframe into memory) and calculates all indicators at once.
This means that if your indicators or entry/exit signals look into future candles, this will falsify your backtest.

The `lookahead-analysis` command requires historic data to be available.
To learn how to get data for the pairs and exchange you're interested in,
head over to the [Data Downloading](data-download.md) section of the documentation.
`lookahead-analysis` also supports freqai strategies.

This command internally chains backtests and pokes at the strategy to provoke it to show lookahead bias.
This is done by not looking at the strategy code itself, but at changed indicator values and moved entries/exits compared to the full backtest.

`lookahead-analysis` can use the typical options of [Backtesting](backtesting.md), but forces the following options:

- `--cache` is forced to "none".
- `--max-open-trades` is forced to be at least equal to the number of pairs.
- `--dry-run-wallet` is forced to be basically infinite (1 billion).
- `--stake-amount` is forced to be a static 10000 (10k).
- `--enable-protections` is forced to be off.

These are set to avoid users accidentally generating false positives.

## Lookahead-analysis command reference

--8<-- "commands/lookahead-analysis.md"

!!! Note ""
    The above output was reduced to options that `lookahead-analysis` adds on top of regular backtesting commands.

### Introduction

Many strategies - without the programmer knowing - have fallen prey to lookahead bias.
This typically make the strategy backtest look profitable, sometimes to extremes, but this is not realistic as the strategy is "cheating" by looking at data it would not have in dry or live modes.

The reason why strategies can "cheat" is because the freqtrade backtesting process populates the full dataframe including all candle timestamps at the outset.
If the programmer is not careful or oblivious how things work internally (which sometimes can be really hard to find out) then the strategy will look into the future.

This command is made to try to verify the validity in the form of the aforementioned lookahead bias.

### How does the command work?

It will start with a backtest of all pairs to generate a baseline for indicators and entries/exits.
After this initial backtest runs, it will look if the `minimum-trade-amount` is met and if not cancel the lookahead-analysis for this strategy.

If this happens, use a wider timerange to get more trades for the analysis, or use a timerange where more trades occur.

After setting the baseline it will then do additional backtest runs for every entry and exit separately.
When these verification backtests complete, it will compare the indicators at the signal candles (both entry or exit) and report the bias.
After all signals have been verified or falsified a result table will be generated for the user to see.

### What do the columns in the results table mean?

- `filename`: name of the checked strategy file
- `strategy`: checked strategy class name
- `has_bias`: result of the lookahead-analysis. `No` would be good, `Yes` would be bad.
- `total_signals`: number of checked signals (default is 20)
- `biased_entry_signals`: found bias in that many entries
- `biased_exit_signals`: found bias in that many exits
- `biased_indicators`: shows you the indicators themselves that are defined in populate_indicators

You might get false positives in the `biased_exit_signals` if you have biased entry signals paired with those exits.
However, a biased entry will usually result in a biased exit too, even if the exit itself does not produce the bias - especially if your entry and exit conditions use the same biased indicator.

**So, address the bias in the entries first, then address the exits.**

### Caveats

- `lookahead-analysis` can only verify / falsify the trades it calculated and verified.
If the strategy has many different signals / signal types, it's up to you to select appropriate parameters to ensure that all signals have triggered at least once. Signals that are not triggered will not have been verified.
This would lead to a false-negative, i.e. the strategy will be reported as non-biased.
- `lookahead-analysis` has access to the same backtesting options and this can introduce problems.
Please don't use any options like enabling position stacking as this will distort the number of checked signals.
If you decide to do so, then make doubly sure that you won't ever run out of `max_open_trades` slots, and that you have enough capital in the backtest wallet configuration.
- In the results table, the `biased_indicators` column will falsely flag FreqAI target indicators defined in `set_freqai_targets()` as biased.  
**These are not biased and can safely be ignored.**
