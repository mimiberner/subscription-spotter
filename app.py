"""
app.py
------
Subscription Spotter: upload a bank statement (CSV) and see your
subscriptions and how much you would save by cancelling some of them.

Run it with:   streamlit run app.py
Then open the link it shows (usually http://localhost:8501).

The detection rules live in subscriptions.py. This file is only the
user interface: upload -> choose columns -> show results -> savings.
"""

import altair as alt
import pandas as pd
import streamlit as st

from subscriptions import clean_statement, find_subscriptions, yearly_savings

SAMPLE_FILE = "sample_data/sample_statement.csv"

st.set_page_config(page_title="Subscription Spotter", page_icon="🔍")
st.title("🔍 Subscription Spotter")
st.write(
    "Upload a bank statement and find the payments that repeat every week, "
    "month or year (Netflix, gym, apps...). Then see how much you would save "
    "by cancelling the ones you don't need."
)
st.caption("🔒 Your file is only used during this session. It is not saved anywhere.")

# ---- 1. Get the data --------------------------------------------------------
st.header("1. Your bank statement")
uploaded = st.file_uploader("Upload a CSV file exported from your online bank", type="csv")
use_sample = st.checkbox("Or try it with our fake sample statement", value=uploaded is None)

if uploaded is not None and not use_sample:
    # sep=None lets pandas guess if the file uses commas or semicolons
    raw = pd.read_csv(uploaded, sep=None, engine="python")
elif use_sample:
    raw = pd.read_csv(SAMPLE_FILE)
else:
    st.info("Upload a file or tick the sample box to start.")
    st.stop()

with st.expander(f"Preview ({len(raw)} rows)"):
    st.dataframe(raw.head(10), width="stretch")


# ---- 2. Which column is which? ----------------------------------------------
def guess(words):
    """Pick the first column whose name contains one of these words."""
    for i, col in enumerate(raw.columns):
        if any(w in str(col).lower() for w in words):
            return i
    return 0


st.header("2. Which column is which?")
c1, c2, c3 = st.columns(3)
date_col = c1.selectbox("Date", raw.columns, index=guess(["date", "fecha"]))
text_col = c2.selectbox("Description", raw.columns, index=guess(["desc", "concept", "text"]))
amount_col = c3.selectbox("Amount", raw.columns, index=guess(["amount", "importe", "cantidad"]))
expenses_positive = st.checkbox("My bank shows payments as positive numbers")

try:
    statement = clean_statement(raw, date_col, text_col, amount_col, expenses_positive)
except (ValueError, TypeError):
    st.error("Could not read the amounts. Check that the Amount column contains numbers.")
    st.stop()

# ---- 3. Results ---------------------------------------------------------------
subs = find_subscriptions(statement)

st.header("3. Recurring payments found")
if subs.empty:
    st.warning("No recurring payments found. Try a longer statement (at least 3 months).")
    st.stop()

# Big recurring payments (rent, loans) are usually not subscriptions.
# We pre-select them here, but the user can change it.
BIG = 200
not_subs = st.multiselect(
    "Not a subscription? Remove it from the totals",
    subs["Merchant"].tolist(),
    default=subs.loc[subs["Amount (€)"] > BIG, "Merchant"].tolist(),
    help=f"Payments above €{BIG} (like rent) are removed automatically. You can change this.",
)
active = subs[(subs["Status"] == "Active") & (~subs["Merchant"].isin(not_subs))]
k1, k2, k3 = st.columns(3)
k1.metric("Active subscriptions", len(active))
k2.metric("Per month", f"€{active['Monthly cost (€)'].sum():,.2f}")
k3.metric("Per year", f"€{active['Yearly cost (€)'].sum():,.2f}")

st.dataframe(subs, width="stretch", hide_index=True)
st.caption("'Price changed' = the amount was not always the same.")

chart = (
    alt.Chart(active)
    .mark_bar()
    .encode(
        x=alt.X("Yearly cost (€):Q"),
        y=alt.Y("Merchant:N", sort="-x", title=None),
        tooltip=["Merchant", "Frequency", "Amount (€)", "Yearly cost (€)"],
    )
)
st.altair_chart(chart, width="stretch")

# ---- 4. Savings ---------------------------------------------------------------
st.header("4. What would you cancel?")
to_cancel = st.multiselect("Choose subscriptions to cancel", active["Merchant"].tolist())
saving = yearly_savings(active, to_cancel)
if to_cancel:
    st.success(f"You would save **€{saving / 12:,.2f} per month**, or **€{saving:,.2f} per year**.")
else:
    st.write("Pick one or more above to see your savings.")

with st.expander("How does it work? / Limitations"):
    st.write(
        "A payment counts as recurring when the **same shop** appears at least 3 times "
        "(2 for yearly), for **about the same amount** (within 10%), at **regular "
        "intervals** (weekly, monthly, quarterly or yearly).\n\n"
        "- Needs at least ~3 months of data (1 year+ to find yearly payments).\n"
        "- Shop names are simplified automatically; very different descriptions for "
        "the same shop may be counted separately.\n"
        "- Subscriptions with changing amounts (e.g. phone bills) may be missed.\n"
        "- Every bank's CSV is different; you may need to choose the columns by hand."
    )
