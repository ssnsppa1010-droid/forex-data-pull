# ============================================================
#  Crypto Data Downloader  (WEBSITE version)
#  Source: Binance public data dump (data.binance.vision)
#  No login / API key needed. Enter coin names -> download CSV.
#  Run:  streamlit run crypto_app.py
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import requests, io, zipfile
from datetime import datetime

st.set_page_config(page_title="Crypto Data Downloader",
                   page_icon="🪙", layout="centered")
st.title("Crypto Data Downloader")
st.caption("Binance public data - no login or API key needed. "
           "Enter coins -> pick timeframe -> download CSV.")

# ------------------------------------------------------------
#  CONFIG
# ------------------------------------------------------------
TF = {'1min':'1m', '5min':'5m', '15min':'15m', '30min':'30m',
      '1h':'1h', '2h':'2h', '4h':'4h', '1day':'1d', '1week':'1w'}
BASE = "https://data.binance.vision/data/spot/monthly/klines"

def months(a, b):
    cur = datetime(a.year, a.month, 1)
    while cur <= b:
        yield cur.year, cur.month
        cur = datetime(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)

def fetch(symbol, itv, from_date, to_date, status=None):
    frames = []
    mlist = list(months(from_date, to_date))
    for i, (y, m) in enumerate(mlist, 1):
        if status:
            status.caption(f"{symbol}: downloading {y}-{m:02d}  ({i}/{len(mlist)})")
        url = f"{BASE}/{symbol}/{itv}/{symbol}-{itv}-{y}-{m:02d}.zip"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                continue
            z = zipfile.ZipFile(io.BytesIO(r.content))
            csv = z.read(z.namelist()[0])
            frames.append(pd.read_csv(io.BytesIO(csv), header=None))
        except Exception:
            continue
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)

def clean(raw):
    df = raw.iloc[:, :6].copy()
    df.columns = ['openTime', 'Open', 'High', 'Low', 'Close', 'Volume']
    # drop any header rows
    df = df[pd.to_numeric(df['openTime'], errors='coerce').notna()].copy()
    ot = df['openTime'].astype('int64')
    # normalize mixed timestamp units to milliseconds
    ot = np.where(ot > 1e17, ot // 1_000_000,          # nanoseconds -> ms
         np.where(ot > 1e14, ot // 1000, ot))          # microseconds -> ms
    df['Date'] = pd.to_datetime(ot, unit='ms', utc=True)
    for c in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[c] = pd.to_numeric(df[c])
    df = df.set_index('Date')[['Open', 'High', 'Low', 'Close', 'Volume']].sort_index()
    df = df[~df.index.duplicated(keep='first')]
    return df

# ------------------------------------------------------------
#  UI
# ------------------------------------------------------------
st.subheader("1. Which coins?")
names_raw = st.text_area("Coin names (separate with commas)", placeholder="BTC, ETH, SOL")

c1, c2 = st.columns(2)
quote = c1.selectbox("Quote currency", ["USDT", "FDUSD", "USDC", "BTC", "ETH"])
timeframe = c2.selectbox("Timeframe", list(TF), index=list(TF).index('1day'))

d1, d2 = st.columns(2)
from_date = d1.date_input("From date", value=datetime(2020, 1, 1))
to_date   = d2.date_input("To date",   value=datetime(2025, 12, 31))

st.divider()
run = st.button("Download data", type="primary", use_container_width=True)

# ------------------------------------------------------------
#  RUN
# ------------------------------------------------------------
if run:
    names = [n.strip() for n in names_raw.replace("\n", ",").split(",") if n.strip()]
    if not names:
        st.error("Please enter at least one coin."); st.stop()
    if from_date >= to_date:
        st.error("From date must be before To date."); st.stop()

    f_date = datetime.combine(from_date, datetime.min.time())
    t_date = datetime.combine(to_date, datetime.min.time())
    itv = TF[timeframe]

    results, no_data = {}, []
    prog = st.progress(0.0, text="Fetching data...")
    status = st.empty()
    for i, nm in enumerate(names, 1):
        symbol = f"{nm.upper()}{quote}"
        prog.progress((i - 1) / len(names), text=f"{symbol} ...")
        raw = fetch(symbol, itv, f_date, t_date, status)
        if raw is None or raw.empty:
            no_data.append(symbol); continue
        results[symbol] = clean(raw)
    prog.progress(1.0, text="Done!")
    status.empty()

    if no_data:
        st.warning("No data (check coin name / quote / date range): " + ", ".join(no_data))
    if not results:
        st.error("No data returned."); st.stop()

    st.success(f"{len(results)} file(s) ready!")
    for name, df in results.items():
        with st.expander(f"{name}_{timeframe}.csv -- {len(df)} rows"):
            st.dataframe(df.head(10), use_container_width=True)
            st.download_button(f"Download {name}_{timeframe}.csv",
                               df.to_csv().encode("utf-8"),
                               file_name=f"{name}_{timeframe}.csv",
                               mime="text/csv", key=f"dl_{name}")
    if len(results) > 1:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, df in results.items():
                zf.writestr(f"{name}_{timeframe}.csv", df.to_csv())
        st.download_button("Download all as ZIP", buf.getvalue(),
                           file_name=f"crypto_{timeframe}.zip",
                           mime="application/zip", type="primary",
                           use_container_width=True)
