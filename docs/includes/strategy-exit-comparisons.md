## Exit logic comparisons

Freqtrade allows your strategy to implement different exit logics.
This section aims to compare each different section, helping you to choose the one that best fits your needs.

* **`populate_exit_trend()`** - Vectorized exit logic based on the dataframe  
  ✅ **Use** to define exit conditions based on indicators or other data that can be calculated in a vectorized manner.  
  🚫 **Don't use** to customize exit conditions for each individual trade, or if trade data is necessary to make an exit decision.
* **`custom_exit()`** - Custom exit signal, called for every open trade every iteration until a trade is closed.  
  ✅ **Use** to customize exit conditions for each individual trade, or if trade data is necessary to make an exit decision.
* **`custom_stoploss()`** - Custom stoploss, called for every open trade every iteration until a trade is closed. The value returned here is also used for [stoploss on exchange](stoploss.md#stop-loss-on-exchangefreqtrade).  
  ✅ **Use** to customize the stoploss logic to set a dynamic stoploss based on trade data or other conditions.  
  🚫 **Don't use** to exit a trade immediately based on a specific condition. Use `custom_exit()` for that purpose.  
* **`custom_roi()`** - Custom ROI, called for every open trade every iteration until a trade is closed.  
  ✅ **Use** to customize the minimum ROI threshold to exit a trade dynamically based on profit or other conditions.  
  🚫 **Don't use** to exit a trade immediately based on a specific condition. Use `custom_exit()` for that purpose.  
  🚫 **Don't use** for static roi. Use `minimal_roi` for that purpose instead.  
