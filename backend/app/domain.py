"""Pure reference planner. Production broker decisions run only inside the MQL5 EA."""

from dataclasses import dataclass, replace
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

D = Decimal
ZERO = D(0)


@dataclass(frozen=True)
class Position:
    ticket: str
    symbol: str
    side: str
    volume: D
    entry: D
    sl: D = ZERO
    tp: D = ZERO


@dataclass(frozen=True)
class Market:
    bid: D
    ask: D
    point: D = D("0.01")
    tick: D = D("0.01")
    stops: D = ZERO
    freeze: D = ZERO
    volume_step: D = D("0.01")
    volume_min: D = D("0.01")
    volume_max: D = D("100")


@dataclass(frozen=True)
class Item:
    ticket: str
    code: str
    volume: D
    stop: D = ZERO


@dataclass(frozen=True)
class Plan:
    code: str
    side: str
    total: D
    target: D
    already: D
    planned: D
    items: tuple[Item, ...]
    buy: D = ZERO
    sell: D = ZERO


def threshold(p, m, buffer_points):
    raw = p.entry + (1 if p.side == "BUY" else -1) * buffer_points * m.point
    rounding = ROUND_CEILING if p.side == "BUY" else ROUND_FLOOR
    return (raw / m.tick).to_integral_value(rounding=rounding) * m.tick


def protected(p, stop):
    return p.sl > 0 and (p.sl >= stop if p.side == "BUY" else p.sl <= stop)


def validate_stop(p, m, stop):
    if protected(p, stop):
        return "ALREADY_PROTECTED"
    if stop <= 0:
        return "STOP_LEVEL_INVALID"
    price = m.bid if p.side == "BUY" else m.ask
    distance = price - stop if p.side == "BUY" else stop - price
    if distance <= 0 or distance < m.stops:
        return "SKIPPED_NOT_ENOUGH_DISTANCE"
    if (
        distance <= m.freeze
        or (p.sl and abs(price - p.sl) <= m.freeze)
        or (p.tp and abs(price - p.tp) <= m.freeze)
    ):
        return "FREEZE_LEVEL"
    return "ELIGIBLE"


def plan(positions, market, symbol, side, fraction, action="be", buffer_points=ZERO):
    if action not in ("be", "close") or side not in ("AUTO", "BUY", "SELL", "BOTH"):
        raise ValueError("UNSUPPORTED_COMMAND")
    if not fraction.is_finite() or not 0 < fraction <= 1 or buffer_points < 0:
        raise ValueError("INVALID_PARAMETERS")
    if (
        market.tick <= 0
        or market.point <= 0
        or market.volume_step <= 0
        or market.bid <= 0
        or market.ask < market.bid
    ):
        raise ValueError("INVALID_MARKET")
    rows = [p for p in positions if p.symbol == symbol]
    if len(rows) > 128:
        raise ValueError("TOO_MANY_POSITIONS")
    sides = {p.side for p in rows}
    if action == "be" and side in ("AUTO", "BOTH") and len(sides) > 1:
        return Plan("AMBIGUOUS_SIDE", "AUTO", ZERO, ZERO, ZERO, ZERO, ())
    if side == "AUTO":
        side = next(iter(sides)) if sides else "AUTO"
    if side != "BOTH":
        rows = [p for p in rows if p.side == side]
    total = sum((p.volume for p in rows), ZERO)
    target = total * fraction
    buy = sum((p.volume for p in rows if p.side == "BUY"), ZERO)
    sell = total - buy
    if not rows:
        return Plan("NO_POSITIONS", side, ZERO, ZERO, ZERO, ZERO, ())
    if action == "close":
        rows.sort(
            key=lambda p: (
                (market.bid - p.entry) if p.side == "BUY" else (p.entry - market.ask),
                int(p.ticket),
            )
        )
        items, planned, remaining = [], ZERO, target
        for p in rows:
            if remaining <= 0:
                break
            amount = min(p.volume, remaining, market.volume_max)
            amount = (amount / market.volume_step).to_integral_value(
                rounding=ROUND_FLOOR
            ) * market.volume_step
            if 0 < p.volume - amount < market.volume_min:
                amount = ((p.volume - market.volume_min) / market.volume_step).to_integral_value(
                    rounding=ROUND_FLOOR
                ) * market.volume_step
            if amount < market.volume_min:
                items.append(Item(p.ticket, "VOLUME_CONSTRAINT", ZERO))
                continue
            items.append(Item(p.ticket, "ELIGIBLE", amount))
            planned += amount
            remaining -= amount
        return Plan(
            "OK" if planned else "NO_ELIGIBLE_POSITIONS",
            side,
            total,
            target,
            ZERO,
            planned,
            tuple(items),
            buy,
            sell,
        )
    already = sum(
        (p.volume for p in rows if protected(p, threshold(p, market, buffer_points))), ZERO
    )
    rows.sort(
        key=lambda p: (
            abs((market.bid if p.side == "BUY" else market.ask) - p.entry),
            int(p.ticket),
        )
    )
    items, planned = [], ZERO
    for p in rows:
        stop = threshold(p, market, buffer_points)
        code = validate_stop(p, market, stop)
        if code == "ALREADY_PROTECTED":
            items.append(Item(p.ticket, code, p.volume, stop))
        elif already + planned < target:
            items.append(Item(p.ticket, code, p.volume, stop))
            if code == "ELIGIBLE":
                planned += p.volume
    return Plan(
        "OK" if planned or already >= target else "NO_ELIGIBLE_POSITIONS",
        side,
        total,
        target,
        already,
        planned,
        tuple(items),
        buy,
        sell,
    )


def simulate_execute(positions, market, planned, action, reject=frozenset()):
    current = {p.ticket: p for p in positions}
    results, confirmed = [], ZERO
    for item in planned.items:
        if item.code != "ELIGIBLE":
            results.append(item)
            continue
        p = current.get(item.ticket)
        if not p:
            results.append(replace(item, code="POSITION_DISAPPEARED"))
            continue
        if item.ticket in reject:
            results.append(replace(item, code="BROKER_REJECTED"))
            continue
        if action == "be":
            code = validate_stop(p, market, item.stop)
            if code != "ELIGIBLE":
                results.append(replace(item, code=code))
                continue
            current[p.ticket] = replace(p, sl=item.stop)
        else:
            if p.volume < item.volume:
                results.append(replace(item, code="POSITION_CHANGED"))
                continue
            if p.volume == item.volume:
                del current[p.ticket]
            else:
                current[p.ticket] = replace(p, volume=p.volume - item.volume)
        confirmed += item.volume
        results.append(replace(item, code="CONFIRMED"))
    return list(current.values()), results, confirmed
