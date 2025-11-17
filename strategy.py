from vibetrading import (
    vibe, get_price, get_futures_ohlcv, get_futures_position,
    my_futures_balance, long, set_leverage, get_perp_open_orders,
    cancel_order, reduce_position, get_current_time
)
import math

# ============================================================================
# CONFIGURATION
# ============================================================================

ASSET = "ASTER"

# Grid geometry
SPACING_PCT = 0.005            # 0.5% between levels
GRID_LEVELS_EACH_SIDE = 40     # 40 levels per side

# Risk management
LEVERAGE = 5
MARGIN_USAGE = 0.85
MIN_NOTIONAL_PER_ORDER_USD = 15

# Behavior
HIBERNATE_OUTSIDE_STEPS = 2
TOLERANCE_FACTOR = 0.50
MAX_ACTIVE_DISTANCE_STEPS = 30

# Take Profit Configuration
ENABLE_EXPLICIT_TP = True
TP_THRESHOLD_PCT = 0.08        # 8% take profit

# Data Configuration
OHLCV_INTERVAL = "15m"         # Use 15-minute candles
OHLCV_LOOKBACK = 96            # 96 candles = 24 hours of 15m data

# ============================================================================
# GLOBAL STATE
# ============================================================================

grid_center_price = None
last_mode = None
last_active_levels_per_side = None
failed_cancel_attempts = {}
entry_price = None
last_execution = None
last_status_log = None

# ============================================================================
# MAIN STRATEGY
# ============================================================================

@vibe(interval="1m")
def aster_long_only_grid():
    """
    Long-only grid strategy for ASTER using 15-minute data.
    Executes every 5 minutes with comprehensive analytics.
    """
    global grid_center_price, last_mode, last_active_levels_per_side, last_execution
    global entry_price, last_status_log

    current_time = get_current_time()
    
    # Frame-skipping: Execute every 5 minutes
    if last_execution and (current_time - last_execution).total_seconds() < 300:
        return
    
    last_execution = current_time
    ts = current_time.strftime('%H:%M:%S')

    # ------------------------------------------------------------------------
    # Snapshot with type conversion
    # ------------------------------------------------------------------------
    try:
        balance_raw = my_futures_balance("USDC")
        
        # Convert balance to float if it's a string
        if isinstance(balance_raw, str):
            balance_usd = float(balance_raw)
        else:
            balance_usd = balance_raw
        
        price = get_price(ASSET)
        position = get_futures_position(ASSET)
        open_orders = get_perp_open_orders(ASSET)
        
        # Validate critical values
        if price is None or price <= 0:
            print(f"❌ Invalid price: {price}, skipping execution")
            return
        
        if balance_usd is None or balance_usd < 0:
            print(f"❌ Invalid balance: {balance_usd}, skipping execution")
            return

        # Status logging
        print(f"[{ts}] {ASSET} ${price:.4f} | Pos: {position:+.6f} | Margin: ${balance_usd:,.0f} | Orders: {len(open_orders)}")
        
    except Exception as e:
        print(f"❌ Error fetching market data: {e}")
        return

    # ------------------------------------------------------------------------
    # Initialize fixed center (first run only) - USE 15m VWAP
    # ------------------------------------------------------------------------
    if grid_center_price is None:
        try:
            recent_data = get_futures_ohlcv(ASSET, OHLCV_INTERVAL, OHLCV_LOOKBACK)
            if len(recent_data) >= 20:
                typical_price = (recent_data['high'] + recent_data['low'] + recent_data['close']) / 3
                vwap = (typical_price * recent_data['volume']).sum() / recent_data['volume'].sum()
                grid_center_price = vwap
                entry_price = grid_center_price

                print("\n" + "="*80)
                print("🎯 LONG-ONLY GRID INITIALIZED (15m Data)")
                print("="*80)
                print(f"Center (fixed): ${grid_center_price:.4f} (15m VWAP)")
                print(f"Current Price: ${price:.4f}")
                print(f"Spacing: {SPACING_PCT*100:.2f}% | Levels/side: {GRID_LEVELS_EACH_SIDE}")
                print(f"⚠️  LONG-ONLY MODE: Only buy orders will be placed")
                print(f"📈 Take Profit: {TP_THRESHOLD_PCT*100:.1f}% gain on long positions")
                print(f"Data: {OHLCV_INTERVAL} timeframe | Lookback: {OHLCV_LOOKBACK} candles")
                print(f"⏱️  Execution: Every 300s (5 min)")
                print("="*80 + "\n")
            else:
                grid_center_price = price
                entry_price = price
                print(f"\n🎯 Grid center: ${grid_center_price:.4f} (fallback)\n")
        except Exception as e:
            print(f"❌ Error initializing grid center: {e}, using current price as fallback")
            grid_center_price = price
            entry_price = price
    
    # Validate grid center
    if grid_center_price is None or grid_center_price <= 0:
        print(f"❌ Invalid grid_center_price: {grid_center_price}, skipping execution")
        return

    # ------------------------------------------------------------------------
    # Derived grid parameters
    # ------------------------------------------------------------------------
    r = 1.0 + SPACING_PCT
    envelope_upper = grid_center_price * (r ** GRID_LEVELS_EACH_SIDE)
    envelope_lower = grid_center_price / (r ** GRID_LEVELS_EACH_SIDE)

    steps_from_center = math.log(price / grid_center_price, r) if price > 0 else 0.0
    outside_steps = abs(steps_from_center) - GRID_LEVELS_EACH_SIDE
    hibernate = outside_steps > HIBERNATE_OUTSIDE_STEPS

    # Log mode transitions
    mode = "hibernate" if hibernate else "active"
    if mode != last_mode:
        print(f"\n{'⏸️' if hibernate else '▶️'}  {mode.upper()} MODE")
        print(f"Price: ${price:.4f} | Envelope: ${envelope_lower:.4f} - ${envelope_upper:.4f}\n")
        last_mode = mode

    # ------------------------------------------------------------------------
    # Margin-aware sizing
    # ------------------------------------------------------------------------
    set_leverage(ASSET, LEVERAGE)

    margin_locked_in_orders = sum(
        float(o.get("price", 0)) * float(o.get("amount", 0)) / LEVERAGE
        for o in open_orders
    )

    position_margin = abs(position * price) / LEVERAGE if abs(position) > 0.0001 else 0

    total_available_margin = balance_usd - margin_locked_in_orders - position_margin
    if total_available_margin < 0:
        total_available_margin = 0

    alloc_margin_usd = total_available_margin * MARGIN_USAGE
    total_notional_usd = alloc_margin_usd * LEVERAGE

    if total_notional_usd <= 0:
        return

    max_affordable_levels_per_side = int(total_notional_usd / (2 * MIN_NOTIONAL_PER_ORDER_USD))
    target_levels = max(1, min(GRID_LEVELS_EACH_SIDE, max_affordable_levels_per_side, MAX_ACTIVE_DISTANCE_STEPS))

    if last_active_levels_per_side is None:
        active_levels_per_side = target_levels
    elif abs(target_levels - last_active_levels_per_side) > 2:
        active_levels_per_side = target_levels
    else:
        active_levels_per_side = last_active_levels_per_side

    if active_levels_per_side < 1:
        print(f"⚠️ Warning: active_levels_per_side={active_levels_per_side}, insufficient margin")
        return

    if last_active_levels_per_side != active_levels_per_side:
        if active_levels_per_side < GRID_LEVELS_EACH_SIDE:
            print(f"\n💰 Grid contracted: {active_levels_per_side}/side (margin limited)\n")
        last_active_levels_per_side = active_levels_per_side

    # ------------------------------------------------------------------------
    # Generate LONG-ONLY grid levels (buy orders only)
    # ------------------------------------------------------------------------
    try:
        # Only generate buy levels (below center)
        long_levels = [grid_center_price / (r ** k) for k in range(1, active_levels_per_side + 1)]
        
        total_active_orders = active_levels_per_side  # Only buy orders
        
        if total_active_orders == 0:
            print(f"⚠️ Warning: total_active_orders is 0, skipping grid generation")
            return
        
        notional_per_order = total_notional_usd / total_active_orders

        long_targets = [{"price": p, "size": notional_per_order / p} for p in long_levels]
        
        if not long_targets:
            print(f"⚠️ Warning: Empty target lists, skipping order management")
            return

    except Exception as e:
        print(f"❌ Error generating grid levels: {e}")
        return

    # ------------------------------------------------------------------------
    # Order management (LONG-ONLY)
    # ------------------------------------------------------------------------
    try:
        manage_long_only_orders(ASSET, price, long_targets, open_orders, hibernate, active_levels_per_side)
    except Exception as e:
        print(f"❌ Error in order management: {e}")

    # ------------------------------------------------------------------------
    # Position management & take profit
    # ------------------------------------------------------------------------
    try:
        manage_position_and_tp(ASSET, price, position, grid_center_price)
    except Exception as e:
        print(f"❌ Error in position management: {e}")

    # ------------------------------------------------------------------------
    # Periodic status report (every 15 minutes)
    # ------------------------------------------------------------------------
    should_log_status = (
        last_status_log is None or
        (current_time - last_status_log).total_seconds() >= 900
    )

    if should_log_status:
        print("\n" + "="*80)
        print(f"📊 {ASSET} GRID REPORT — {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        print(f"💰 Margin: ${balance_usd:.2f} | Position: {position:+.6f} {ASSET}")
        print(f"🎯 Center: ${grid_center_price:.4f} | Active: {active_levels_per_side}/side")
        print(f"📐 Orders: {len(open_orders)} | Mode: {mode}")
        print(f"🟢 LONG-ONLY | Data: {OHLCV_INTERVAL} timeframe | Range: ${envelope_lower:.4f} - ${envelope_upper:.4f}")
        print("="*80 + "\n")
        last_status_log = current_time


# ============================================================================
# ORDER MANAGEMENT (LONG-ONLY)
# ============================================================================

def manage_long_only_orders(asset, current_price, long_targets, open_orders, hibernate, active_levels_per_side):
    """
    Long-only order management - only places buy orders below current price.
    """
    global failed_cancel_attempts, grid_center_price

    tolerance = SPACING_PCT * TOLERANCE_FACTOR

    # Calculate active range boundaries
    r = 1.0 + SPACING_PCT
    max_distance_down = current_price - current_price / (r ** active_levels_per_side)

    # Generate ALL possible grid levels
    all_possible_long_levels = [grid_center_price / (r ** k) for k in range(1, GRID_LEVELS_EACH_SIDE + 1)]

    # Active targets for NEW placements only
    target_buy_prices = [t["price"] for t in long_targets]

    # Classify orders
    misaligned = []
    far_orders = []

    for order in open_orders:
        side = order.get("side", "").lower()
        o_price = float(order.get("price", 0))
        distance = abs(o_price - current_price)

        # LONG-ONLY: Only keep buy orders
        if side != "buy":
            misaligned.append(order)
            continue

        # Check if below current price
        price_buffer = current_price * 0.001
        if o_price >= current_price + price_buffer:
            misaligned.append(order)
            continue

        # Check if aligned to ANY theoretical grid level
        aligned_to_grid = any(abs(o_price - p) / p < tolerance for p in all_possible_long_levels)

        if not aligned_to_grid:
            misaligned.append(order)
            continue

        # Check if within active distance range
        if distance <= max_distance_down:
            pass  # Valid order within active range
        else:
            far_orders.append(order)

    # Clean up failed cancel attempts
    current_order_ids = {o.get("order_id") for o in open_orders}
    failed_cancel_attempts = {oid: count for oid, count in failed_cancel_attempts.items() if oid in current_order_ids}

    # Cancel misaligned orders
    cancelled_count = 0
    for order in misaligned:
        oid = order["order_id"]
        if failed_cancel_attempts.get(oid, 0) < 5:
            try:
                cancel_order(oid)
                failed_cancel_attempts.pop(oid, None)
                cancelled_count += 1
            except Exception as e:
                failed_cancel_attempts[oid] = failed_cancel_attempts.get(oid, 0) + 1

    if cancelled_count > 0:
        print(f"🗑️ Cancelled {cancelled_count} misaligned orders")

    # Calculate missing orders
    missing = []
    if not hibernate:
        existing_buys = {float(o["price"]) for o in open_orders if o.get("side") == "buy"}

        for t in long_targets:
            if t["price"] < current_price and not any(abs(t["price"] - p) / p < tolerance for p in existing_buys):
                missing.append({"price": t["price"], "size": t["size"], "side": "buy",
                               "distance": abs(t["price"] - current_price)})

    # Cancel far orders if needed
    far_cancelled = 0
    if missing and far_orders:
        far_orders.sort(key=lambda x: abs(float(x.get("price", 0)) - current_price), reverse=True)
        cancel_limit = min(5, len(missing))
        for order in far_orders[:cancel_limit]:
            try:
                cancel_order(order["order_id"])
                far_cancelled += 1
            except:
                pass

        if far_cancelled > 0:
            print(f"🗑️ Cancelled {far_cancelled} far orders to free margin")

    # Place missing orders
    if missing:
        missing.sort(key=lambda x: x["distance"])
        placed_count = 0

        for order_spec in missing[:10]:
            try:
                result = long(asset, order_spec["size"], order_spec["price"])

                if result and result.get("order_id"):
                    placed_count += 1
            except Exception as e:
                print(f"❌ Long order failed: {e}")

        if placed_count > 0:
            remaining = len(missing) - placed_count
            print(f"📝 Placed {placed_count} orders | {remaining} gaps remaining")


# ============================================================================
# POSITION MANAGEMENT & TAKE PROFIT
# ============================================================================

def manage_position_and_tp(asset, current_price, position, grid_center):
    """
    Take profit mechanism for long positions.
    """
    if abs(position) < 0.01:
        return

    # Only manage long positions
    if position > 0:
        pnl_pct = (current_price - grid_center) / grid_center

        if ENABLE_EXPLICIT_TP and pnl_pct >= TP_THRESHOLD_PCT:
            tp_amount = abs(position) * 0.5  # Take 50% profit
            reduce_position(asset, tp_amount)
            print(f"💰 TAKE PROFIT: Closed {tp_amount:.6f} {asset} @ ${current_price:.4f}")
            print(f"   Profit: {pnl_pct*100:+.2f}% from grid center ${grid_center:.4f}")