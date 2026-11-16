"""Signal: advice from two moving averages (the AIML part).

In plain words:
    Picture an uncle who watches the ledger. He compares today's mood (the
    average of the last few minutes) with this week's mood (the average of
    many more minutes). When today's mood climbs above the week's, he says
    BUY. When it falls below, he says SELL. Otherwise he says HOLD.
    He only gives advice. He never places an order himself.

Technical words:
    SMA(n)      simple moving average: the mean of the last n closing prices.
    crossover   the moment the short SMA moves from below the long SMA to above
                it (BUY), or from above to below (SELL).

Why not linear regression for "up or down"?
    Linear regression predicts a number. "Up or down" is a category. For a
    category the fitting tools are a rule like this crossover, or logistic
    regression. The honest test (see `honest_test`) compares any rule with the
    lazy baseline "always guess the most common answer".
"""


def sma(values, n):
    """Simple moving average of the last n values, or None if there are fewer than n.

    Example:
        >>> sma([1, 2, 3, 4], 2)
        3.5
    """
    if n <= 0 or len(values) < n:
        return None
    window = values[-n:]
    return sum(window) / n


def crossover_signal(closes, short=5, long=15):
    """Return BUY, SELL or HOLD from a list of closing prices (oldest first).

    The rule needs the averages at two moments, the previous minute and this
    minute, because a crossing is a *change*:
        before: short <= long   and   now: short > long   ->  BUY
        before: short >= long   and   now: short < long   ->  SELL
        anything else                                     ->  HOLD

    Returns a dict, so the API can show the numbers behind the advice.
    """
    if long <= short:
        raise ValueError("the long window must be longer than the short one")
    if len(closes) < long + 1:
        return {"advice": "HOLD", "reason": f"need {long + 1} closes, have {len(closes)}",
                "short_now": None, "long_now": None}

    short_before, long_before = sma(closes[:-1], short), sma(closes[:-1], long)
    short_now, long_now = sma(closes, short), sma(closes, long)

    if short_before <= long_before and short_now > long_now:
        advice, reason = "BUY", "short average crossed above the long average"
    elif short_before >= long_before and short_now < long_now:
        advice, reason = "SELL", "short average crossed below the long average"
    else:
        advice, reason = "HOLD", "no fresh crossing this minute"

    return {"advice": advice, "reason": reason,
            "short_now": round(short_now, 6), "long_now": round(long_now, 6)}


def honest_test(closes, short=5, long=15, train_share=0.7):
    """Is the rule any better than lazy guessing? Score it on LATER minutes only.

    In plain words:
        1. Split the minutes by time: the first 70% are "earlier", the rest "later".
           Never shuffle. Shuffling lets the rule peek at the future.
        2. Baseline: from the earlier minutes, find the most common move (up or
           down) and always guess that.
        3. Rule: after each minute in the later part, the short average above the
           long one means "guess up", otherwise "guess down".
        4. Count how often each guess matched the next minute's real move.

    Returns:
        dict with rule accuracy, baseline accuracy and how many minutes were scored.
    """
    moves = [1 if closes[i + 1] > closes[i] else 0 for i in range(len(closes) - 1)]
    split = int(len(moves) * train_share)
    if split < long or len(moves) - split < 5:
        return {"scored_minutes": 0, "rule_accuracy": None, "baseline_accuracy": None,
                "note": "not enough minutes yet"}

    earlier, later_idx = moves[:split], range(split, len(moves))
    common = 1 if sum(earlier) >= len(earlier) / 2 else 0

    rule_right = base_right = 0
    for i in later_idx:
        history = closes[: i + 1]
        guess = 1 if sma(history, short) > sma(history, long) else 0
        rule_right += guess == moves[i]
        base_right += common == moves[i]

    n = len(later_idx)
    return {"scored_minutes": n, "rule_accuracy": round(rule_right / n, 3),
            "baseline_accuracy": round(base_right / n, 3),
            "note": "accuracy on later minutes only; the rule is worth keeping only if it beats the baseline"}
