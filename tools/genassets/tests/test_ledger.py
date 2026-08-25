"""Tests for the spend cap.

The cap guards the only part of this project that costs real money, and it had
no tests at all. It also counted CALLS, which cannot bound spend: one Veo video
call and one flash text call both counted as 1, while differing by orders of
magnitude in price.
"""
from __future__ import annotations

import pytest

from genassets.gemini import Ledger, LedgerError, Models, SpendCapExceeded


def test_estimated_cost_varies_by_model():
    """A cap that treats every model as equal is not a cap on spend."""
    led = Ledger()
    assert led.cost_of(Models.VIDEO) > led.cost_of(Models.IMAGE)
    assert led.cost_of(Models.IMAGE) > led.cost_of(Models.TEXT)


def test_an_unknown_model_is_charged_the_most_expensive_rate():
    """A new model pin must not cost 0.00 and slip past the budget silently."""
    led = Ledger()
    assert led.cost_of("some-model-shipped-next-year") >= led.cost_of(Models.VIDEO)


def test_spend_accumulates_across_calls():
    led = Ledger(max_usd=100.0)
    led.record(Models.IMAGE, "generateContent", 1.0, 10)
    led.record(Models.IMAGE, "generateContent", 1.0, 10)
    assert led.spent == pytest.approx(2 * led.cost_of(Models.IMAGE))


def test_check_refuses_before_the_call_that_would_break_the_budget():
    """BEFORE, not after. Refusing afterwards means already having paid."""
    led = Ledger(max_usd=1.0)
    # Fill the budget to just under the cap.
    while led.spent + led.cost_of(Models.IMAGE) <= 1.0:
        led.record(Models.IMAGE, "generateContent", 1.0, 10)

    before = led.spent
    with pytest.raises(SpendCapExceeded):
        led.check(Models.IMAGE)
    assert led.spent == before, "check() must not itself spend anything"


def test_an_affordable_call_is_allowed():
    led = Ledger(max_usd=100.0)
    led.check(Models.IMAGE)  # must not raise


def test_a_single_call_over_the_whole_budget_is_refused():
    led = Ledger(max_usd=0.0001)
    with pytest.raises(SpendCapExceeded):
        led.check(Models.VIDEO)


def test_call_count_still_guards_a_runaway_loop():
    """Cheap models could loop forever inside a generous budget."""
    led = Ledger(max_usd=1_000_000.0, max_calls=3)
    for _ in range(3):
        led.record(Models.TEXT, "generateContent", 0.1, 10)
    with pytest.raises(SpendCapExceeded):
        led.check(Models.TEXT)


def test_spend_persists_across_processes(tmp_path):
    """An in-memory budget resets every run, so it caps nothing cumulative."""
    path = tmp_path / "ledger.json"

    first = Ledger(max_usd=100.0, path=path)
    first.record(Models.IMAGE, "generateContent", 1.0, 10)
    spent = first.spent
    assert spent > 0

    second = Ledger(max_usd=100.0, path=path)
    assert second.spent == pytest.approx(spent)
    assert second.count == 1


def test_a_persisted_budget_is_enforced_in_a_later_process(tmp_path):
    path = tmp_path / "ledger.json"

    first = Ledger(max_usd=100.0, path=path)
    while first.spent + first.cost_of(Models.IMAGE) <= 1.0:
        first.record(Models.IMAGE, "generateContent", 1.0, 10)

    # A fresh process with a 1.00 cap must inherit what was already spent.
    later = Ledger(max_usd=1.0, path=path)
    with pytest.raises(SpendCapExceeded):
        later.check(Models.IMAGE)


def test_a_corrupt_ledger_file_does_not_silently_reset_the_budget(tmp_path):
    """Truncating the file must not be a way to get a fresh budget by accident."""
    path = tmp_path / "ledger.json"
    path.write_text("{not json", encoding="utf-8")
    # Specifically LedgerError. `Exception` would also be satisfied by a
    # TypeError from a signature change, which is not the behaviour under test.
    with pytest.raises(LedgerError):
        Ledger(max_usd=1.0, path=path)


def test_summary_reports_money(tmp_path):
    led = Ledger(max_usd=10.0)
    led.record(Models.IMAGE, "generateContent", 1.0, 10)
    assert "$" in led.summary()


# --------------------------------------------------------------- shared client
# `agent/tools.py` constructed `GeminiClient()` fresh at every call site, so each
# call got its own empty ledger. Both limits were therefore per-call: a cap of
# 100 was really a cap of 1, applied 100 times, and nothing accumulated.

def test_shared_client_reuses_one_ledger(monkeypatch, tmp_path):
    import genassets.gemini as g

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GENASSETS_LEDGER", str(tmp_path / "ledger.json"))
    g.reset_client()

    first = g.client()
    second = g.client()
    assert first is second, "every call site must share one budget"
    assert first.ledger.path is not None, "the shared ledger must persist"


def test_shared_client_ledger_survives_a_reset(monkeypatch, tmp_path):
    import genassets.gemini as g

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GENASSETS_LEDGER", str(tmp_path / "ledger.json"))
    g.reset_client()

    g.client().ledger.record(Models.IMAGE, "generateContent", 1.0, 10)
    spent = g.client().ledger.spent

    # Simulates the next process: the in-memory object is gone, the file is not.
    g.reset_client()
    assert g.client().ledger.spent == pytest.approx(spent)
