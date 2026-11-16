"""The crossover rule and the honest test."""
from engine.signals import crossover_signal, honest_test, sma


def test_sma():
    assert sma([1, 2, 3, 4], 2) == 3.5
    assert sma([1, 2], 3) is None


def test_not_enough_data_is_hold():
    assert crossover_signal([1, 2, 3], 5, 15)["advice"] == "HOLD"


def test_cross_up_is_buy():
    closes = [10.0] * 15 + [9.0] + [12.0]   # short average jumps above the long one at the last minute
    assert crossover_signal(closes, 2, 5)["advice"] == "BUY"


def test_cross_down_is_sell():
    closes = [10.0] * 15 + [11.0] + [7.0]
    assert crossover_signal(closes, 2, 5)["advice"] == "SELL"


def test_flat_market_is_hold():
    assert crossover_signal([10.0] * 30, 5, 15)["advice"] == "HOLD"


def test_honest_test_scores_later_minutes_only():
    closes = [100 + (i % 7) for i in range(80)]
    r = honest_test(closes, 5, 15)
    assert r["scored_minutes"] == len(closes) - 1 - int((len(closes) - 1) * 0.7)
    assert 0 <= r["rule_accuracy"] <= 1 and 0 <= r["baseline_accuracy"] <= 1
