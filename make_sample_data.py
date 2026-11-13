"""
make_sample_data.py
-------------------
Creates a FAKE bank statement (sample_data/sample_statement.csv) so the app
can be demonstrated without using anyone's real bank data.

Run it with:   python make_sample_data.py
"""

import random
from datetime import date, timedelta

import pandas as pd

random.seed(7)  # same "random" data every time
START, END = date(2025, 11, 1), date(2026, 11, 12)
rows = []


def add(day, text, amount):
    if START <= day <= END:
        rows.append({"Date": day.strftime("%d/%m/%Y"), "Description": text, "Amount": round(amount, 2)})


def ref():
    return str(random.randint(100000, 999999))


def monthly(day_of_month):
    """Yield one date per month on (about) this day."""
    y, m = START.year, START.month
    while date(y, m, 1) <= END:
        yield date(y, m, min(day_of_month, 28)) + timedelta(days=random.choice([0, 0, 1, 2]))
        m += 1
        if m == 13:
            y, m = y + 1, 1


# --- Subscriptions (the things the app should find) ------------------------
for d in monthly(3):
    add(d, f"NETFLIX.COM {ref()} AMSTERDAM", -13.99)
for d in monthly(11):
    price = -10.99 if d < date(2026, 6, 1) else -11.99      # price went up in June
    add(d, f"CARD PURCHASE SPOTIFY P{ref()}", price)
for d in monthly(1):
    add(d, f"RECIBO BASIC-FIT MARBELLA {ref()}", -29.99)
for d in monthly(20):
    add(d, f"APPLE.COM/BILL ICLOUD {ref()}", -2.99)
for d in monthly(15):
    if d < date(2026, 5, 1):                                  # cancelled in spring
        add(d, f"DISNEY PLUS {ref()}", -8.99)
add(date(2025, 11, 22), f"AMAZON PRIME ANNUAL {ref()}", -49.90)  # yearly
add(date(2026, 11, 2), f"AMAZON PRIME ANNUAL {ref()}", -49.90)
d = date(2025, 11, 4)
while d <= END:                                               # weekly language app
    add(d, f"DUOLINGO {ref()}", -3.49)
    d += timedelta(days=7)

# --- Normal life (the app should IGNORE these) -----------------------------
for d in monthly(1):
    add(d, "RENT TRANSFER PISO", -950.00)                     # recurring, but not a subscription
    add(d + timedelta(days=26), "SALARY ACME SL", 2400.00)    # income
d = START
while d <= END:
    if random.random() < 0.35:
        add(d, f"MERCADONA {ref()} MARBELLA", -random.uniform(12, 95))
    if random.random() < 0.12:
        add(d, f"UBER TRIP {ref()}", -random.uniform(6, 25))
    if random.random() < 0.10:
        add(d, random.choice(["RESTAURANTE LA PLAYA", "BAR EL PUERTO", "CAFE CENTRAL"]), -random.uniform(8, 60))
    d += timedelta(days=1)
for _ in range(4):
    add(START + timedelta(days=random.randint(0, 370)), f"ZARA {ref()}", -random.uniform(20, 120))

df = pd.DataFrame(rows)
df["_d"] = pd.to_datetime(df["Date"], dayfirst=True)
df = df.sort_values("_d").drop(columns="_d")
df.to_csv("sample_data/sample_statement.csv", index=False)
print(f"Wrote {len(df)} transactions to sample_data/sample_statement.csv")
