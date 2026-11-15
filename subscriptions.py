"""
subscriptions.py
----------------
The "brain" of the app: finds recurring charges (subscriptions) in a bank
statement. No machine learning, just clear rules we can explain.

A payment counts as a subscription when ALL of these are true:
  1. It goes OUT of the account (negative amount).
  2. The same shop/merchant appears several times
     (at least 3 times, or 2 times for yearly payments).
  3. The amount is (almost) always the same: within 10% of the usual amount.
  4. The time between payments is regular: about every week, month,
     3 months or year.
"""

import io
import re

import pandas as pd

# How many days apart payments are for each frequency, and how many
# times per month that frequency happens (used to compute monthly cost).
FREQUENCIES = {
    #  name        (min days, max days, payments per month)
    "Weekly":    (6, 8, 52 / 12),
    "Monthly":   (26, 35, 1),
    "Quarterly": (85, 97, 1 / 3),
    "Yearly":    (330, 400, 1 / 12),
}

# Words banks add to descriptions that say nothing about the shop
FILLER_WORDS = {
    "card", "purchase", "payment", "debit", "direct", "pos", "online",
    "compra", "pago", "tarjeta", "recibo", "adeudo", "www", "com", "bill",
}


# ---------------------------------------------------------------------------
# Step A: read and clean the bank statement
# ---------------------------------------------------------------------------
HEADER_WORDS = ("date", "fecha")  # how we recognise the header row


def read_statement_file(data, filename):
    """
    Read a bank file (CSV or Excel) into a table.

    Real bank exports are messy, so we handle three common problems:
      - Excel files (.xlsx): many Spanish banks export these instead of CSV.
      - Spanish characters (á, ñ...) saved in an old encoding (latin-1).
      - Extra rows at the top (bank name, account number...) before the
        real table starts. We look for the first row that contains the
        word "date" or "fecha" and use that row as the column names.
    """
    if filename.lower().endswith((".xlsx", ".xls")):
        raw = pd.read_excel(io.BytesIO(data), header=None, dtype=str)
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        # sep=None lets pandas guess if the file uses commas or semicolons.
        # We skip the bank's title lines first, so the guess is correct.
        lines = text.splitlines()
        start = next((i for i, line in enumerate(lines[:30])
                      if any(w in line.lower() for w in HEADER_WORDS)), 0)
        raw = pd.read_csv(io.StringIO("\n".join(lines[start:])), sep=None,
                          engine="python", header=None, dtype=str)

    # Find the header row (first row with "date" or "fecha" in it)
    header_row = 0
    for i in range(min(30, len(raw))):
        cells = " ".join(str(c).lower() for c in raw.iloc[i].tolist())
        if any(w in cells for w in HEADER_WORDS):
            header_row = i
            break
    table = raw.iloc[header_row + 1:].copy()
    table.columns = [str(c).strip() for c in raw.iloc[header_row]]
    table = table.dropna(how="all")            # drop empty rows
    return table.reset_index(drop=True)


def parse_amount(value):
    """
    Turn text like '-13.99', '-13,99', '1.234,56' or '€ 9,99' into a number.
    Spanish banks use a comma for decimals, so we handle both styles.
    """
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("€", "").replace("EUR", "").replace(" ", "").strip()
    if text in ("", "nan", "None", "-"):
        return float("nan")
    if "," in text and "." in text:
        # whichever comes last is the decimal separator
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")   # 1.234,56
        else:
            text = text.replace(",", "")                     # 1,234.56
    elif "," in text:
        text = text.replace(",", ".")                        # 13,99
    return float(text)


def parse_dates(values):
    """
    Read dates in both styles banks use:
      - '2026-01-03'  (year first, e.g. from Excel)  -> 3 January 2026
      - '03/01/2026'  (day first, Spanish/European)  -> 3 January 2026
    """
    text = values.astype(str).str.strip()
    year_first = text.str.match(r"^\d{4}-\d{2}-\d{2}")
    dates = pd.to_datetime(text.where(~year_first), dayfirst=True, format="mixed", errors="coerce")
    dates[year_first] = pd.to_datetime(text[year_first].str[:10], format="%Y-%m-%d", errors="coerce")
    return dates


def clean_statement(df, date_col, text_col, amount_col, expenses_positive=False):
    """
    Return a tidy table with three columns: date, description, amount.
    Expenses become negative numbers (if the bank shows them as positive,
    set expenses_positive=True).
    """
    out = pd.DataFrame({
        "date": parse_dates(df[date_col]),
        "description": df[text_col].astype(str),
        "amount": df[amount_col].apply(parse_amount),
    })
    if expenses_positive:
        out["amount"] = -out["amount"]
    out = out.dropna(subset=["date", "amount"])
    return out.sort_values("date").reset_index(drop=True)


def merchant_name(description):
    """
    Make one short name per shop, so that
    'NETFLIX.COM 4829174 AMSTERDAM' and 'NETFLIX.COM 551203 AMSTERDAM'
    both become 'netflix amsterdam'.
    Steps: lowercase -> punctuation to spaces -> remove words with digits
    (reference numbers) -> remove filler words -> keep the first 2 words.
    """
    # \w keeps letters with accents (á, ñ...); "_" is removed too
    text = re.sub(r"[^\w ]|_", " ", description.lower())
    words = [w for w in text.split() if not any(c.isdigit() for c in w)]
    words = [w for w in words if w not in FILLER_WORDS]
    return " ".join(words[:2]) if words else "unknown"


# ---------------------------------------------------------------------------
# Step B: find the subscriptions
# ---------------------------------------------------------------------------
def classify_interval(days):
    """Which frequency matches this typical gap in days? None if no match."""
    for name, (low, high, _) in FREQUENCIES.items():
        if low <= days <= high:
            return name
    return None


def find_subscriptions(statement, today=None):
    """
    Look at each merchant separately and keep the ones that follow the rules.
    Returns a table with one row per subscription found.
    """
    expenses = statement[statement["amount"] < 0].copy()
    expenses["merchant"] = expenses["description"].apply(merchant_name)
    if today is None:
        today = statement["date"].max()

    found = []
    for merchant, group in expenses.groupby("merchant"):
        group = group.sort_values("date")
        if len(group) < 2:
            continue

        # Rule 4: regular time between payments
        gaps = group["date"].diff().dt.days.dropna()
        typical_gap = gaps.median()
        frequency = classify_interval(typical_gap)
        if frequency is None:
            continue
        if frequency != "Yearly" and len(group) < 3:
            continue
        low, high, per_month = FREQUENCIES[frequency]
        share_regular = ((gaps >= low) & (gaps <= high)).mean()
        if share_regular < 0.75:          # at least 75% of gaps must be regular
            continue

        # Rule 3: (almost) the same amount every time
        amounts = group["amount"].abs()
        usual = amounts.median()
        share_same = ((amounts - usual).abs() <= 0.10 * usual).mean()
        if share_same < 0.8:              # at least 80% within 10%
            continue

        latest_amount = amounts.iloc[-1]
        last_date = group["date"].iloc[-1]
        next_date = last_date + pd.Timedelta(days=round(typical_gap))
        # If we are well past the next expected date, it was probably cancelled
        active = (today - last_date).days <= typical_gap * 1.5

        found.append({
            "Merchant": merchant.title(),
            "Frequency": frequency,
            "Amount (€)": round(latest_amount, 2),
            "Monthly cost (€)": round(latest_amount * per_month, 2),
            "Yearly cost (€)": round(latest_amount * per_month * 12, 2),
            "Times charged": len(group),
            "Last charge": last_date.date(),
            "Next expected": next_date.date() if active else None,
            "Status": "Active" if active else "Possibly cancelled",
            "Price changed": bool(amounts.round(2).nunique() > 1),
        })

    columns = ["Merchant", "Frequency", "Amount (€)", "Monthly cost (€)", "Yearly cost (€)",
               "Times charged", "Last charge", "Next expected", "Status", "Price changed"]
    result = pd.DataFrame(found, columns=columns)
    return result.sort_values("Yearly cost (€)", ascending=False).reset_index(drop=True)


def upcoming_charges(subscriptions, today, days=30):
    """Active subscriptions expected to charge in the next `days` days."""
    today = pd.Timestamp(today)
    nxt = pd.to_datetime(subscriptions["Next expected"])
    soon = subscriptions[(subscriptions["Status"] == "Active")
                         & (nxt >= today) & (nxt <= today + pd.Timedelta(days=days))]
    soon = soon.assign(**{"Next expected": nxt[soon.index].dt.date})
    return soon.sort_values("Next expected")[["Next expected", "Merchant", "Amount (€)"]]


def yearly_savings(subscriptions, to_cancel):
    """How much you save per year by cancelling the chosen merchants."""
    chosen = subscriptions[subscriptions["Merchant"].isin(to_cancel)]
    return round(chosen["Yearly cost (€)"].sum(), 2)
