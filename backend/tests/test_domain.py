from dataclasses import replace

import pytest
from app.domain import (
    D,
    Market,
    Position,
    plan,
    protected,
    simulate_execute,
    threshold,
    validate_stop,
)
from app.telegram import parse_command
from fastapi import HTTPException

M = Market(D(110), D("110.2"), stops=D("0.2"))


def pos(ticket, volume="0.1", entry="100", side="BUY", sl="0", tp="130"):
    return Position(str(ticket), "XAUUSD", side, D(volume), D(entry), D(sl), D(tp))


@pytest.mark.parametrize("text", ["/be gold", "/be XAUUSD 100", "/be gold all", "/close gold"])
def test_default_all(text):
    assert parse_command(text)[1].target_fraction == 1


@pytest.mark.parametrize("pct", ["0", "-1", "101", "nan", "inf", "1e9999", "five", "50 extra"])
def test_bad_percentage(pct):
    with pytest.raises(HTTPException):
        parse_command("/be gold " + pct)


def test_equal_layers_closest_first():
    p = plan([pos(i, entry=str(100 + i)) for i in range(1, 7)], M, "XAUUSD", "AUTO", D("0.5"))
    assert p.planned == D("0.3")
    assert [i.ticket for i in p.items] == ["6", "5", "4"]


def test_unequal_overshoot_and_existing_protection():
    rows = [pos(1, "0.2", sl="105"), pos(2, "0.7", entry="106"), pos(3, "0.1")]
    p = plan(rows, M, "XAUUSD", "AUTO", D("0.5"))
    assert p.already == D("0.2") and p.planned == D("0.7")
    final, _, confirmed = simulate_execute(rows, M, p, "be")
    assert confirmed == D("0.7")
    assert final[0].sl == 105 and all(p.tp == 130 for p in final)
    assert plan(final, M, "XAUUSD", "AUTO", D("0.5")).planned == 0


def test_sell_and_tick_normalization():
    m = replace(M, tick=D("0.25"))
    p = pos(1, entry="120.13", side="SELL", tp="90")
    stop = threshold(p, m, D(3))
    assert stop == D(120)
    assert validate_stop(p, m, stop) == "ELIGIBLE"
    assert validate_stop(replace(p, sl=D(119)), m, stop) == "ALREADY_PROTECTED"


def test_ambiguous_side_and_exact_symbol():
    rows = [pos(1), pos(2, side="SELL", entry="120")]
    assert plan(rows, M, "XAUUSD", "AUTO", D(1)).code == "AMBIGUOUS_SIDE"
    assert plan(rows, M, "gold", "AUTO", D(1)).code == "NO_POSITIONS"
    assert plan(rows, M, "XAUUSD", "BUY", D(1)).total == D("0.1")


@pytest.mark.parametrize(
    "entry,freeze,code",
    [
        ("109.9", "0", "SKIPPED_NOT_ENOUGH_DISTANCE"),
        ("109", "1", "FREEZE_LEVEL"),
        ("111", "0", "SKIPPED_NOT_ENOUGH_DISTANCE"),
    ],
)
def test_distance(entry, freeze, code):
    p = pos(1, entry=entry)
    assert validate_stop(p, replace(M, freeze=D(freeze)), D(entry)) == code


def test_disappeared_and_rejected():
    rows = [pos(1), pos(2)]
    p = plan(rows, M, "XAUUSD", "BUY", D(1))
    _, results, confirmed = simulate_execute(rows[1:], M, p, "be", frozenset({"2"}))
    assert confirmed == 0
    assert {i.code for i in results} == {"POSITION_DISAPPEARED", "BROKER_REJECTED"}


def test_manual_improvement_during_execution():
    row = pos(1)
    p = plan([row], M, "XAUUSD", "BUY", D(1))
    final, _, count = simulate_execute([replace(row, sl=D(108), tp=D(140))], M, p, "be")
    assert count == 0 and final[0].sl == 108 and final[0].tp == 140


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_stop_monotonicity_many_states(side):
    for entry in range(95, 125):
        for sl in range(0, 130, 3):
            p = pos(1, entry=str(entry), side=side, sl=str(sl))
            stop = threshold(p, M, D(2))
            if validate_stop(p, M, stop) == "ELIGIBLE":
                assert p.sl == 0 or (stop >= p.sl if side == "BUY" else stop <= p.sl)
                assert not protected(p, stop)


def test_close_gross_mixed_worst_price_per_lot():
    rows = [pos(1, "0.4", "100"), pos(2, "0.3", "114"), pos(3, "0.3", "108", "SELL")]
    p = plan(rows, M, "XAUUSD", "BOTH", D("0.5"), "close")
    assert p.total == 1 and p.target == D("0.5")
    assert [(i.ticket, i.volume) for i in p.items] == [("2", D("0.3")), ("3", D("0.2"))]
    final, _, confirmed = simulate_execute(rows, M, p, "close")
    assert confirmed == D("0.5") and sum(p.volume for p in final) == D("0.5")


def test_close_rounds_down_no_overshoot_or_dust():
    p = plan([pos(1, "0.03")], M, "XAUUSD", "BOTH", D("0.5"), "close")
    assert p.planned == D("0.01")
    m = replace(M, volume_min=D("0.02"))
    p = plan([pos(1, "0.03")], m, "XAUUSD", "BOTH", D("0.9"), "close")
    assert p.planned == 0
