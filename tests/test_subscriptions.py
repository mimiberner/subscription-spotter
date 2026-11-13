"""
Tests that check the detection rules (including code written with AI help).

Run them with:   python -m pytest
"""

import pandas as pd

from subscriptions import (clean_statement, find_subscriptions, merchant_name,
                           parse_amount, yearly_savings)


def load_sample():
    raw = pd.read_csv("sample_data/sample_statement.csv")
    return clean_statement(raw, "Date", "Description", "Amount")


SUBS = find_subscriptions(load_sample())
FOUND = set(SUBS["Merchant"])


def test_amounts_in_spanish_and_english_format():
    assert parse_amount("-13,99") == -13.99
    assert parse_amount("1.234,56") == 1234.56
    assert parse_amount("1,234.56") == 1234.56
    assert parse_amount("€ 9,99") == 9.99


def test_merchant_name_ignores_reference_numbers():
    assert merchant_name("NETFLIX.COM 4829174 AMSTERDAM") == merchant_name("NETFLIX.COM 551203 AMSTERDAM")
    assert merchant_name("CARD PURCHASE SPOTIFY P123456") == "spotify"


def test_finds_all_subscriptions_in_sample():
    for name in ["Netflix Amsterdam", "Spotify", "Basic Fit", "Apple Icloud",
                 "Duolingo", "Amazon Prime", "Disney Plus"]:
        assert name in FOUND


def test_ignores_irregular_shopping_and_income():
    assert "Mercadona Marbella" not in FOUND   # amount changes every time
    assert "Uber Trip" not in FOUND            # irregular
    assert "Salary Acme" not in FOUND          # money coming IN


def test_detects_frequencies():
    freq = dict(zip(SUBS["Merchant"], SUBS["Frequency"]))
    assert freq["Duolingo"] == "Weekly"
    assert freq["Netflix Amsterdam"] == "Monthly"
    assert freq["Amazon Prime"] == "Yearly"


def test_cancelled_subscription_is_marked():
    status = dict(zip(SUBS["Merchant"], SUBS["Status"]))
    assert status["Disney Plus"] == "Possibly cancelled"
    assert status["Netflix Amsterdam"] == "Active"


def test_price_increase_still_detected():
    row = SUBS[SUBS["Merchant"] == "Spotify"].iloc[0]
    assert row["Price changed"]
    assert row["Amount (€)"] == 11.99          # shows the latest price


def test_savings_calculation():
    # Netflix 13.99 per month -> 167.88 per year
    assert yearly_savings(SUBS, ["Netflix Amsterdam"]) == 167.88
    assert yearly_savings(SUBS, []) == 0


def test_positive_expenses_option():
    raw = pd.DataFrame({"d": ["01/01/2026", "01/02/2026", "01/03/2026"],
                        "t": ["GYM", "GYM", "GYM"], "a": ["30,00", "30,00", "30,00"]})
    subs = find_subscriptions(clean_statement(raw, "d", "t", "a", expenses_positive=True))
    assert list(subs["Merchant"]) == ["Gym"]
