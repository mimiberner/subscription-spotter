# 🔍 Subscription Spotter

Upload a bank statement (CSV) and the app finds your **recurring charges**:
Netflix, gym, apps, yearly memberships. It shows what they cost per month and
per year, and **how much you would save by cancelling** the ones you choose.

**Course:** Software Engineering, EADA, G1, Prof. Jordi Torras
**Team:** Elena, Mimi, Adam, Dani, Macijek

**Live demo:** https://subscription-spotter-jwks4ccfopthj2bqsm4n6g.streamlit.app/

---

## The problem and why it is useful

Small subscriptions are easy to forget: a free trial that turned into a
payment, an app you stopped using, a price that went up quietly. Each one is
only a few euros, but together they add up to hundreds of euros a year. Bank
apps show a long list of transactions, not a summary of what repeats.
Subscription Spotter gives that summary in a few seconds.

## How it works

The rules are in `subscriptions.py`. There is no machine learning, only clear
rules that we can explain and test.

1. **Read the file.** CSV or Excel (.xlsx). The app handles messy bank
   exports: title lines above the table (it looks for the row with "Date" or
   "Fecha"), `,` or `;` separators, Spanish accents, dates like `03/01/2026`
   or `2026-01-03`, and amounts like `-13,99`, `1.234,56` or `-13.99`.
2. **Keep only money going out** (negative amounts).
3. **Clean the shop name**, so `NETFLIX.COM 4829174 AMSTERDAM` and
   `NETFLIX.COM 551203 AMSTERDAM` count as the same shop. The app uses
   lowercase, removes reference numbers and filler words like "card
   purchase", and keeps the first 2 words.
4. **Check each shop against 3 rules.**
   - It appears at least **3 times** (2 for yearly payments).
   - The **amount is about the same** (80% of payments within 10% of the usual amount).
   - The **time between payments is regular**: weekly (6–8 days), monthly
     (26–35), quarterly (85–97) or yearly (330–400). At least 75% of the gaps
     must fit.
5. **Show the results.** For each match it shows frequency, cost per month and
   per year, the next expected charge, and whether it looks **cancelled** (no
   charge for 1.5× the usual gap) or had a **price change**.
6. **Show next charges.** It lists the next charge of each subscription in the
   following 30 days, so the user knows what to cancel first.
7. **Calculate savings.** The user picks what to cancel and sees the savings.
8. **Download.** The list can be downloaded as a CSV file.

Large recurring payments (over €200, like rent) are removed from the totals by
default, because they repeat but are not subscriptions. The user can change this.

## Results on our sample statement

`sample_data/sample_statement.csv` is a **fake** statement (373 transactions,
Nov 2025 – Nov 2026) made by `make_sample_data.py`. No real bank data is used.

- The app finds all 7 subscriptions we put in, including the **weekly**
  Duolingo charge, the **yearly** Amazon Prime charge, Spotify's **price
  increase** (€10.99 → €11.99), and Disney+ as **possibly cancelled**.
- It correctly **ignores** supermarket shopping, restaurants, Uber, Zara and
  salary income.
- Active subscriptions cost **€78.24/month (€938.90/year)**.

## Project structure

```
subscription-spotter/
├── app.py                 # the web app (Streamlit): upload, results, savings
├── subscriptions.py       # the detection rules
├── make_sample_data.py    # creates the fake sample statement
├── sample_data/
│   └── sample_statement.csv
├── tests/
│   └── test_subscriptions.py   # 13 automatic tests
├── requirements.txt
└── README.md
```

## How to run it

**Option A: online.** Open the live demo link above.

**Option B: on your own computer** (needs Python 3.10+):

```bash
pip install -r requirements.txt
streamlit run app.py
```

Your browser then opens at `http://localhost:8501`. Tick "try it with our fake
sample statement", or upload a CSV or Excel file exported from your bank.

**Run the tests:**

```bash
python -m pytest
```

## How we used AI coding tools

- We used an AI assistant (Claude) to write the first version of the
  detection rules, the Streamlit app, the sample data and the tests.
- **We reviewed the code** and changed what did not work well. For example:
  - Rent was detected as a subscription and made the totals look huge
    (€1,028/month instead of €78). We added a rule that removes large payments
    from the totals, with an option for the user to change it.
  - Streamlit warned that a setting (`use_container_width`) will stop working
    soon, so we replaced it.
  - On the first deploy the app crashed (`FileNotFoundError`) because the
    sample data and tests had been uploaded outside their folders. We moved
    them into `sample_data/` and `tests/` on GitHub.
  - When we added Excel and Spanish-bank support, our new tests found **two
    bugs** in the AI's code: dates like `2026-01-03` were read as 1 March
    instead of 3 January, and accents were removed from shop names
    ("Águila" became "guila"). We fixed both.
- **We tested the code** with `pytest` (13 tests). The tests check number
  and date formats, shop-name cleaning, that all 7 sample subscriptions are
  found, that groceries and salary are ignored, weekly/monthly/yearly
  detection, the cancelled flag, the price change, savings, next charges, a
  messy Spanish bank CSV and an Excel file.

## How we collaborated on GitHub

- Public repository, `main` branch.
- Each member uploaded their own part as commits. - Mimi and Elena shared the development work
  equally: the detection rules, the web app, the sample data, the tests,
  the README and the deployment. Each of them uploaded and edited files,
  as the commit history shows.
- Adam, Dani and Macijek took part in presenting the project.

## Limitations

- Needs at least ~3 months of data (more than a year to find yearly payments).
- Brand-new subscriptions with fewer than 3 charges are not found yet
  (for example, a free trial that just turned into a payment).
- Subscriptions whose amount changes a lot (e.g. phone or electricity bills)
  can be missed.
- If a bank writes the same shop in very different ways, it may be counted twice.
- Every bank's export looks different. We tested with sample files built
  like Spanish bank exports, but not with every bank. The user may need to
  choose the columns by hand.
- Privacy: files are processed in memory only. Still, users should prefer the
  sample file or remove personal details before uploading.

## Ideas for the future

- Warn when a free trial turns into a payment (needs a different rule,
  because there are only 1–2 charges).
- Group shops whose names are written very differently by the bank.
- Show the results in a calendar view.
