"""
Tests that check the detection rules (including code written with AI help).

Run them with:   python -m pytest
"""

import pandas as pd

import io

from subscriptions import (clean_statement, find_subscriptions, merchant_name,
                           parse_amount, read_statement_file, upcoming_charges,
                           yearly_savings)


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


# ---- Messy real-world bank files ------------------------------------------
# Looks like a typical Spanish bank export: title lines on top, semicolons,
# comma decimals, Spanish column names and accents saved in latin-1.
SPANISH_CSV = """Banco Ejemplo S.A.
Cuenta: ES00 **** **** 1234
Movimientos del 01/01/2026 al 30/04/2026

Fecha;Concepto;Importe;Saldo
05/01/2026;RECIBO GIMNASIO ÁGUILA;-35,00;1.000,00
12/01/2026;Compra Café Ñandú;-4,50;995,50
05/02/2026;RECIBO GIMNASIO ÁGUILA;-35,00;960,50
05/03/2026;RECIBO GIMNASIO ÁGUILA;-35,00;925,50
05/04/2026;RECIBO GIMNASIO ÁGUILA;-35,00;890,50
""".encode("latin-1")


def test_reads_spanish_bank_csv_with_title_lines():
    raw = read_statement_file(SPANISH_CSV, "movimientos.csv")
    assert list(raw.columns) == ["Fecha", "Concepto", "Importe", "Saldo"]
    assert len(raw) == 5
    subs = find_subscriptions(clean_statement(raw, "Fecha", "Concepto", "Importe"))
    assert list(subs["Merchant"]) == ["Gimnasio Águila"]
    assert subs.loc[0, "Amount (€)"] == 35.0


def test_dates_in_both_formats():
    from subscriptions import parse_dates
    d = parse_dates(pd.Series(["2026-01-03", "03/01/2026", "2026-01-03 00:00:00"]))
    assert all(x == pd.Timestamp("2026-01-03") for x in d)


def test_reads_excel_file():
    df = pd.DataFrame({"Date": ["2026-01-03", "2026-02-03", "2026-03-03"],
                       "Description": ["NETFLIX"] * 3, "Amount": [-13.99] * 3})
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    raw = read_statement_file(buffer.getvalue(), "statement.xlsx")
    subs = find_subscriptions(clean_statement(raw, "Date", "Description", "Amount"))
    assert list(subs["Merchant"]) == ["Netflix"]


def test_upcoming_charges_next_30_days():
    soon = upcoming_charges(SUBS, today="2026-11-12", days=30)
    names = set(soon["Merchant"])
    assert "Netflix Amsterdam" in names       # next charge early December
    assert "Disney Plus" not in names         # cancelled, no next charge
    assert "Amazon Prime" not in names        # next charge is in 2027
