# Trade Object

## Trade

A position freqtrade enters is stored in a `Trade` object - which is persisted to the database.
It's a core concept of freqtrade - and something you'll come across in many sections of the documentation, which will most likely point you to this location.

It will be passed to the strategy in many [strategy callbacks](strategy-callbacks.md). The object passed to the strategy cannot be modified directly. Indirect modifications may occur based on callback results.

## Trade - Available attributes

The following attributes / properties are available for each individual trade - and can be used with `trade.<property>` (e.g. `trade.pair`).

|  Attribute | DataType | Description |
|------------|-------------|-------------|
| `pair` | string | Pair of this trade. |
| `base_currency` | string | Base currency of the trading pair. |
| `stake_currency` | string | Stake/quote currency of the trading pair. |
| `safe_base_currency` | string | Compatibility layer for base currency - falls back to pair split if empty. |
| `safe_quote_currency` | string | Compatibility layer for quote currency - falls back to pair split if empty. |
| `is_open` | boolean | Is the trade currently open, or has it been concluded. |
| `exchange` | string | Exchange where this trade was executed. |
| `open_rate` | float | Rate this trade was entered at (Avg. entry rate in case of trade-adjustments). |
| `open_rate_requested` | float | The rate that was requested when the trade was opened. |
| `open_trade_value` | float | Value of the open trade including fees. |
| `close_rate` | float | Close rate - only set when is_open = False. |
| `close_rate_requested` | float | The close rate that was requested. |
| `safe_close_rate` | float | Close rate or close_rate_requested or 0.0 if neither is available. |
| `stake_amount` | float | Amount in Stake (or Quote) currency. |
| `max_stake_amount` | float | Maximum stake amount that was used in this trade (including DCA orders). |
| `amount` | float | Amount in Asset / Base currency that is currently owned. Will be 0.0 until the initial order fills. |
| `amount_requested` | float | Amount that was originally requested for this trade. |
| `open_date` | datetime | Timestamp when trade was opened **use `open_date_utc` instead** |
| `open_date_utc` | datetime | Timestamp when trade was opened - in UTC. |
| `close_date` | datetime | Timestamp when trade was closed **use `close_date_utc` instead** |
| `close_date_utc` | datetime | Timestamp when trade was closed - in UTC. |
| `close_profit` | float | Relative profit at the time of trade closure. `0.01` == 1% |
| `close_profit_abs` | float | Absolute profit (in stake currency) at the time of trade closure. |
| `realized_profit` | float | Absolute already realized profit (in stake currency) while the trade is still open. |
| `leverage` | float | Leverage used for this trade - defaults to 1.0 in spot markets. |
| `has_no_leverage` | boolean | Returns true if this is a non-leverage, non-short trade. |
| `borrowed` | float | The amount of currency borrowed from the exchange for leverage trades. |
| `enter_tag` | string | Tag provided on entry via the `enter_tag` column in the dataframe. |
| `buy_tag` | string | **Deprecated** - use `enter_tag` instead. |
| `exit_reason` | string | Reason why the trade was exited. |
| `sell_reason` | string | **Deprecated** - use `exit_reason` instead. |
| `exit_order_status` | string | Status of the exit order. |
| `strategy` | string | Strategy name that was used for this trade. |
| `timeframe` | int | Timeframe used for this trade. |
| `is_short` | boolean | True for short trades, False otherwise. |
| `trading_mode` | TradingMode | Trading mode (SPOT, MARGIN, FUTURES). |
| `orders` | Order[] | List of order objects attached to this trade (includes both filled and cancelled orders). |
| `date_last_filled_utc` | datetime | Time of the last filled order. |
| `date_entry_fill_utc` | datetime | Date of the first filled entry order. |
| `entry_side` | "buy" / "sell" | Order Side the trade was entered. |
| `exit_side` | "buy" / "sell" | Order Side that will result in a trade exit / position reduction. |
| `trade_direction` | "long" / "short" | Trade direction in text - long or short. |
| `nr_of_successful_entries` | int | Number of successful (filled) entry orders. |
| `nr_of_successful_exits` | int | Number of successful (filled) exit orders. |
| `nr_of_successful_buys` | int | **Deprecated** - use `nr_of_successful_entries` for short support. |
| `nr_of_successful_sells` | int | **Deprecated** - use `nr_of_successful_exits` for short support. |
| `has_open_orders` | boolean | Has the trade open orders (excluding stoploss orders). |
| `has_open_position` | boolean | True if there is an open position for this trade. |
| `has_open_sl_orders` | boolean | True if there are open stoploss orders for this trade. |
| `open_orders` | Order[] | All open orders for this trade excluding stoploss orders. |
| `open_sl_orders` | Order[] | All open stoploss orders for this trade. |
| `sl_orders` | Order[] | All stoploss orders for this trade (open and closed). |
| `open_orders_ids` | string[] | List of open order IDs (excluding stoploss orders). |

### Fee related attributes

|  Attribute | DataType | Description |
|------------|-------------|-------------|
| `fee_open` | float | Fee rate that was paid for opening the trade. |
| `fee_open_cost` | float | Absolute fee cost that was paid for opening the trade. |
| `fee_open_currency` | string | Currency the open fee was paid in. |
| `fee_close` | float | Fee rate that was paid for closing the trade. |
| `fee_close_cost` | float | Absolute fee cost that was paid for closing the trade. |
| `fee_close_currency` | string | Currency the close fee was paid in. |

### Stop Loss related attributes

|  Attribute | DataType | Description |
|------------|-------------|-------------|
| `stop_loss` | float | Absolute value of the stop loss. |
| `stop_loss_pct` | float | Percentage value of the stop loss. |
| `initial_stop_loss` | float | Absolute value of the initial stop loss. |
| `initial_stop_loss_pct` | float | Percentage value of the initial stop loss. |
| `is_stop_loss_trailing` | boolean | True if the stop loss is trailing. |
| `stoploss_last_update_utc` | datetime | Timestamp of the last stoploss update. |
| `stoploss_or_liquidation` | float | Returns the more restrictive of stoploss or liquidation price. |

### Price tracking attributes

|  Attribute | DataType | Description |
|------------|-------------|-------------|
| `max_rate` | float | Highest price reached during this trade. |
| `min_rate` | float | Lowest price reached during this trade. |

### Futures/Margin trading attributes

|  Attribute | DataType | Description |
|------------|-------------|-------------|
| `liquidation_price` | float | Liquidation price for leveraged trades. |
| `interest_rate` | float | Interest rate for margin trades. |
| `funding_fees` | float | Total funding fees for futures trades. |
| `funding_fee_running` | float | Running funding fees between last filled order and now. |

### Precision attributes

|  Attribute | DataType | Description |
|------------|-------------|-------------|
| `amount_precision` | float | Amount precision for the pair. |
| `price_precision` | float | Price precision for the pair. |
| `precision_mode` | int | Precision mode for amounts. |
| `precision_mode_price` | int | Precision mode for prices. |
| `contract_size` | float | Contract size for futures trading. |

### Trade counters (for canceled orders)

|  Attribute | DataType | Description |
|------------|-------------|-------------|
| `fully_canceled_entry_order_count` | int | Number of fully canceled entry orders. |
| `canceled_exit_order_count` | int | Number of canceled exit orders. |

## Class methods

The following are class methods - which return generic information, and usually result in an explicit query against the database.
They can be used as `Trade.<method>` - e.g. `open_trades = Trade.get_open_trade_count()`

!!! Warning "Backtesting/hyperopt"
    Most methods will work in both backtesting / hyperopt and live/dry modes.
    During backtesting, it's limited to usage in [strategy callbacks](strategy-callbacks.md). Usage in `populate_*()` methods is not supported and will result in wrong results.

### get_trades_proxy

When your strategy needs some information on existing (open or close) trades - it's best to use `Trade.get_trades_proxy()`.

Usage:

``` python
from freqtrade.persistence import Trade
from datetime import timedelta

# ...
trade_hist = Trade.get_trades_proxy(pair='ETH/USDT', is_open=False, open_date=current_date - timedelta(days=2))

```

`get_trades_proxy()` supports the following keyword arguments. All arguments are optional - calling `get_trades_proxy()` without arguments will return a list of all trades in the database.

* `pair` e.g. `pair='ETH/USDT'`
* `is_open` e.g. `is_open=False`
* `open_date` e.g. `open_date=current_date - timedelta(days=2)`
* `close_date` e.g. `close_date=current_date - timedelta(days=5)`

### get_open_trade_count

Get the number of currently open trades

``` python
from freqtrade.persistence import Trade
# ...
open_trades = Trade.get_open_trade_count()
```

### get_total_closed_profit

Retrieve the total profit the bot has generated so far.
Aggregates `close_profit_abs` for all closed trades.

``` python
from freqtrade.persistence import Trade

# ...
profit = Trade.get_total_closed_profit()
```

### total_open_trades_stakes

Retrieve the total stake_amount that's currently in trades.

``` python
from freqtrade.persistence import Trade

# ...
profit = Trade.total_open_trades_stakes()
```

### get_overall_performance

Retrieve the overall performance - similar to the `/performance` telegram command.

``` python
from freqtrade.persistence import Trade

# ...
if self.config['runmode'].value in ('live', 'dry_run'):
    performance = Trade.get_overall_performance()
```

Sample return value: ETH/BTC had 5 trades, with a total profit of 1.5% (ratio of 0.015).

``` json
{"pair": "ETH/BTC", "profit": 0.015, "count": 5}
```

### stoploss_reinitialization

Adjust initial Stoploss to desired stoploss for all open trades.

``` python
from freqtrade.persistence import Trade

# ...
Trade.stoploss_reinitialization(desired_stoploss=-0.1)
```

### get_enter_tag_performance

Returns performance grouped by enter_tag.

``` python
from freqtrade.persistence import Trade

# ...
performance = Trade.get_enter_tag_performance('ETH/USDT')  # or None for all pairs
```

### get_exit_reason_performance

Returns performance grouped by exit_reason.

``` python
from freqtrade.persistence import Trade

# ...
performance = Trade.get_exit_reason_performance('ETH/USDT')  # or None for all pairs
```

### get_mix_tag_performance

Returns performance grouped by enter_tag + exit_reason combination.

``` python
from freqtrade.persistence import Trade

# ...
performance = Trade.get_mix_tag_performance('ETH/USDT')  # or None for all pairs
```

### get_best_pair

Get the best performing pair with closed trades.

``` python
from freqtrade.persistence import Trade

# ...
best_pair = Trade.get_best_pair()
```

### get_trading_volume

Get total trading volume based on orders.

``` python
from freqtrade.persistence import Trade

# ...
volume = Trade.get_trading_volume()
```

## Order Object

An `Order` object represents an order on the exchange (or a simulated order in dry-run mode).
An `Order` object will always be tied to it's corresponding [`Trade`](#trade-object), and only really makes sense in the context of a trade.

### Order - Available attributes

an Order object is typically attached to a trade.
Most properties here can be None as they are dependent on the exchange response.

|  Attribute | DataType | Description |
|------------|-------------|-------------|
| `trade` | Trade | Trade object this order is attached to |
| `ft_trade_id` | int | ID of the trade this order belongs to |
| `ft_pair` | string | Pair this order is for |
| `ft_is_open` | boolean | is the order still open? |
| `ft_amount` | float | Amount in base currency (freqtrade's internal amount) |
| `ft_price` | float | Price the order was placed at (freqtrade's internal price) |
| `ft_order_side` | string | Order side ('buy', 'sell', or 'stoploss') |
| `ft_cancel_reason` | string | Reason why the order was canceled |
| `ft_order_tag` | string | Custom order tag |
| `ft_fee_base` | float | Fee paid in base currency |
| `order_id` | string | Exchange order ID |
| `order_type` | string | Order type as defined on the exchange - usually market, limit or stoploss |
| `status` | string | Status as defined by [ccxt's order structure](https://docs.ccxt.com/#/README?id=order-structure). Usually open, closed, expired, canceled or rejected |
| `symbol` | string | Symbol/pair as defined by the exchange |
| `side` | string | buy or sell |
| `price` | float | Price the order was placed at |
| `average` | float | Average price the order filled at |
| `amount` | float | Amount in base currency |
| `filled` | float | Filled amount (in base currency) (use `safe_filled` instead) |
| `safe_filled` | float | Filled amount (in base currency) - guaranteed to not be None |
| `safe_amount` | float | Amount - falls back to ft_amount if None |
| `safe_price` | float | Price - falls back through average, price, stop_price, ft_price |
| `safe_placement_price` | float | Price at which the order was placed |
| `remaining` | float | Remaining amount (use `safe_remaining` instead) |
| `safe_remaining` | float | Remaining amount - either taken from the exchange or calculated. |
| `safe_cost` | float | Cost of the order - guaranteed to not be None |
| `safe_fee_base` | float | Fee in base currency - guaranteed to not be None |
| `safe_amount_after_fee` | float | Amount after deducting fees |
| `cost` | float | Cost of the order - usually average * filled (*Exchange dependent on futures, may contain the cost with or without leverage and may be in contracts.*) |
| `stop_price` | float | Stop price for stop orders |
| `stake_amount` | float | Stake amount used for this order. *Added in 2023.7.* |
| `stake_amount_filled` | float | Filled Stake amount used for this order. *Added in 2024.11.* |
| `order_date` | datetime | Order creation date **use `order_date_utc` instead** |
| `order_date_utc` | datetime | Order creation date (in UTC) |
| `order_filled_date` | datetime |  Order fill date **use `order_filled_utc` instead** |
| `order_filled_utc` | datetime | Order fill date |
| `order_update_date` | datetime | Last order update date |
| `funding_fee` | float | Funding fee for this order (futures trading) |
