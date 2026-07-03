# ============================================================
#  Crypto & Global Stocks Data Downloader  (WEBSITE version)
#  No login / API key needed.
#    - Crypto        -> Binance public dump (data.binance.vision)
#    - Foreign Stocks-> Dukascopy (US / UK / Japan / Germany ... major stocks)
#  Note: Indian NSE stocks are NOT here (use the Angel/Fyers app for those).
#  Run:  streamlit run crypto_app.py
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import requests, io, zipfile
from datetime import datetime

st.set_page_config(page_title="Crypto & Global Stocks Downloader",
                   page_icon="🌐", layout="centered")
st.title("Crypto & Global Stocks Data Downloader")
st.caption("Free public data - no login or API key needed.")

# ============================================================
#  SOURCE 1 : BINANCE (crypto)
# ============================================================
BINANCE_TF = {'1min':'1m', '5min':'5m', '15min':'15m', '30min':'30m',
              '1h':'1h', '2h':'2h', '4h':'4h', '1day':'1d', '1week':'1w'}
BINANCE_BASE = "https://data.binance.vision/data/spot/monthly/klines"

def months(a, b):
    cur = datetime(a.year, a.month, 1)
    while cur <= b:
        yield cur.year, cur.month
        cur = datetime(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)

def binance_fetch(symbol, itv, from_date, to_date, status=None):
    frames = []
    mlist = list(months(from_date, to_date))
    for i, (y, m) in enumerate(mlist, 1):
        if status:
            status.caption(f"{symbol}: downloading {y}-{m:02d}  ({i}/{len(mlist)})")
        url = f"{BINANCE_BASE}/{symbol}/{itv}/{symbol}-{itv}-{y}-{m:02d}.zip"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                continue
            z = zipfile.ZipFile(io.BytesIO(r.content))
            frames.append(pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=None))
        except Exception:
            continue
    if not frames:
        return None
    return binance_clean(pd.concat(frames, ignore_index=True))

def binance_clean(raw):
    df = raw.iloc[:, :6].copy()
    df.columns = ['openTime', 'Open', 'High', 'Low', 'Close', 'Volume']
    df = df[pd.to_numeric(df['openTime'], errors='coerce').notna()].copy()
    ot = df['openTime'].astype('int64')
    ot = np.where(ot > 1e17, ot // 1_000_000,
         np.where(ot > 1e14, ot // 1000, ot))
    df['Date'] = pd.to_datetime(ot, unit='ms', utc=True)
    for c in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[c] = pd.to_numeric(df[c])
    df = df.set_index('Date')[['Open', 'High', 'Low', 'Close', 'Volume']].sort_index()
    return df[~df.index.duplicated(keep='first')]

# ============================================================
#  SOURCE 2 : DUKASCOPY (foreign / global stocks)
# ============================================================
DUKA_MARKETS = ["US", "UK", "JAPAN", "GERMANY", "FRANCE", "ITALY",
                "NETHERLANDS", "SPAIN", "SWITZERLAND"]
DUKA_TF_NAMES = {'1min':'INTERVAL_MIN_1', '5min':'INTERVAL_MIN_5',
                 '15min':'INTERVAL_MIN_15', '30min':'INTERVAL_MIN_30',
                 '1h':'INTERVAL_HOUR_1', '4h':'INTERVAL_HOUR_4',
                 '1day':'INTERVAL_DAY_1', '1week':'INTERVAL_WEEK_1'}

def duka_fetch(ticker, market, timeframe, from_date, to_date):
    """Returns a cleaned df, None (no data), or 'NOSYM' (ticker not on Dukascopy)."""
    import dukascopy_python
    from dukascopy_python import instruments as I
    interval = getattr(dukascopy_python, DUKA_TF_NAMES[timeframe])
    t = ticker.strip().upper()

    inst = None
    for cur in ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "HKD"]:
        cand = f"INSTRUMENT_{market}_{t}_{market}_{cur}"
        if hasattr(I, cand):
            inst = getattr(I, cand); break
    if inst is None:                       # fallback: any match for this ticker
        for x in dir(I):
            if x.startswith(f"INSTRUMENT_{market}_{t}_"):
                inst = getattr(I, x); break
    if inst is None:
        return "NOSYM"

    df = dukascopy_python.fetch(inst, interval, dukascopy_python.OFFER_SIDE_BID,
                                from_date, to_date)
    if df is None or df.empty:
        return None
    df = df.rename(columns={'open':'Open', 'high':'High', 'low':'Low',
                            'close':'Close', 'volume':'Volume'})
    keep = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
    df = df[keep]
    df.index.name = 'Date'
    return df

# ---- Foreign INDEX (friendly name -> Dukascopy instrument attribute) ----
DUKA_INDEX_MAP = {
    'SP500':'INSTRUMENT_IDX_AMERICA_E_SANDP_500',
    'NAS100':'INSTRUMENT_IDX_AMERICA_E_NQ_100',
    'DOW':'INSTRUMENT_IDX_AMERICA_E_D_J_IND',
    'RUSSELL2000':'INSTRUMENT_IDX_AMERICA_USSC2000_IDX_USD',
    'RUSSELL':'INSTRUMENT_IDX_AMERICA_RUSSELL_IDX_USD',
    'VIX':'INSTRUMENT_IDX_AMERICA_VOL_IDX_USD',
    'DOLLARIDX':'INSTRUMENT_IDX_AMERICA_DOLLAR_IDX_USD',
    'DAX':'INSTRUMENT_IDX_EUROPE_E_DAAX',
    'FTSE':'INSTRUMENT_IDX_EUROPE_E_FUTSEE_100',
    'CAC':'INSTRUMENT_IDX_EUROPE_E_CAAC_40',
    'EUSTOXX':'INSTRUMENT_IDX_EUROPE_E_DJE50XX',
    'SWISS':'INSTRUMENT_IDX_EUROPE_E_SWMI',
    'IBEX':'INSTRUMENT_IDX_EUROPE_E_IBC_MAC',
    'ITALY':'INSTRUMENT_IDX_EUROPE_ITA_IDX_EUR',
    'NETHERLANDS':'INSTRUMENT_IDX_EUROPE_NLD_IDX_EUR',
    'POLAND':'INSTRUMENT_IDX_EUROPE_PLN_IDX_PLN',
    'PORTUGAL':'INSTRUMENT_IDX_PRT_IDX_EUR',
    'NIKKEI':'INSTRUMENT_IDX_ASIA_E_N225JAP',
    'HANGSENG':'INSTRUMENT_IDX_ASIA_E_H_KONG',
    'ASX':'INSTRUMENT_IDX_ASIA_E_XJO_ASX',
    'CHINA':'INSTRUMENT_IDX_ASIA_CHI_IDX_USD',
    'INDIA':'INSTRUMENT_IDX_ASIA_IND_IDX_USD',
    'SINGAPORE':'INSTRUMENT_IDX_ASIA_SGD_IDX_SGD',
    'SOUTHAFRICA':'INSTRUMENT_IDX_AFRICA_SOA_IDX_ZAR',
}

def duka_index_fetch(name, timeframe, from_date, to_date):
    """Returns a cleaned df, None (no data), or 'NOSYM' (name not in the list)."""
    import dukascopy_python
    from dukascopy_python import instruments as I
    attr = DUKA_INDEX_MAP.get(name.strip().upper())
    inst = getattr(I, attr, None) if attr else None
    if inst is None:
        return "NOSYM"
    interval = getattr(dukascopy_python, DUKA_TF_NAMES[timeframe])
    df = dukascopy_python.fetch(inst, interval, dukascopy_python.OFFER_SIDE_BID,
                                from_date, to_date)
    if df is None or df.empty:
        return None
    df = df.rename(columns={'open':'Open', 'high':'High', 'low':'Low',
                            'close':'Close', 'volume':'Volume'})
    keep = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
    df = df[keep]
    df.index.name = 'Date'
    return df
st.subheader("1. Choose data source")
source = st.radio("Source", ["Crypto", "Foreign Stocks", "Foreign Index"], horizontal=True)

if source == "Crypto":
    st.subheader("2. Which coins?")
    names_raw = st.text_area("Coin names (separate with commas)", placeholder="BTC, ETH, SOL")
    c1, c2 = st.columns(2)
    quote = c1.selectbox("Quote currency", ["USDT", "FDUSD", "USDC", "BTC", "ETH"])
    timeframe = c2.selectbox("Timeframe", list(BINANCE_TF),
                             index=list(BINANCE_TF).index('1day'))
elif source == "Foreign Stocks":
    st.subheader("2. Which stocks?")
    st.caption("Global major stocks only (US ~630, UK, Japan, Germany...). "
               "Indian NSE stocks are not available here.")
    names_raw = st.text_area("Tickers (separate with commas)", placeholder="AAPL, MSFT, TSLA")
    c1, c2 = st.columns(2)
    market = c1.selectbox("Market", DUKA_MARKETS)
    timeframe = c2.selectbox("Timeframe", list(DUKA_TF_NAMES),
                             index=list(DUKA_TF_NAMES).index('1day'))
else:  # Foreign Index
    st.subheader("2. Which indices?")
    names_raw = st.text_area("Index names (separate with commas)", placeholder="SP500, NAS100, DAX")
    with st.expander("Available index names"):
        st.write(", ".join(DUKA_INDEX_MAP.keys()))
    timeframe = st.selectbox("Timeframe", list(DUKA_TF_NAMES),
                             index=list(DUKA_TF_NAMES).index('1day'))

d1, d2 = st.columns(2)
from_date = d1.date_input("From date", value=datetime(2016, 1, 1))
to_date   = d2.date_input("To date",   value=datetime(2025, 12, 31))

st.divider()
run = st.button("Download data", type="primary", use_container_width=True)

# ============================================================
#  RUN
# ============================================================
if run:
    names = [n.strip() for n in names_raw.replace("\n", ",").split(",") if n.strip()]
    if not names:
        st.error("Please enter at least one name."); st.stop()
    if from_date >= to_date:
        st.error("From date must be before To date."); st.stop()

    f_date = datetime.combine(from_date, datetime.min.time())
    t_date = datetime.combine(to_date, datetime.min.time())

    results, no_data, not_found = {}, [], []
    prog = st.progress(0.0, text="Fetching data...")
    status = st.empty()

    for i, nm in enumerate(names, 1):
        if source == "Crypto":
            label = f"{nm.upper()}{quote}"
            prog.progress((i - 1) / len(names), text=f"{label} ...")
            df = binance_fetch(f"{nm.upper()}{quote}", BINANCE_TF[timeframe],
                               f_date, t_date, status)
            if df is None or df.empty:
                no_data.append(label)
            else:
                results[label] = df
        elif source == "Foreign Stocks":
            label = f"{nm.upper()}_{market}"
            prog.progress((i - 1) / len(names), text=f"{label} ...")
            try:
                out = duka_fetch(nm, market, timeframe, f_date, t_date)
            except Exception as e:
                no_data.append(f"{label} ({e})"); continue
            if isinstance(out, str) and out == "NOSYM":
                not_found.append(f"{nm.upper()} ({market})")
            elif out is None or out.empty:
                no_data.append(label)
            else:
                results[label] = out
        else:  # Foreign Index
            label = nm.upper()
            prog.progress((i - 1) / len(names), text=f"{label} ...")
            try:
                out = duka_index_fetch(nm, timeframe, f_date, t_date)
            except Exception as e:
                no_data.append(f"{label} ({e})"); continue
            if isinstance(out, str) and out == "NOSYM":
                not_found.append(f"{label} (not in list)")
            elif out is None or out.empty:
                no_data.append(label)
            else:
                results[label] = out

    prog.progress(1.0, text="Done!")
    status.empty()

    if not_found:
        st.warning("Not found on Dukascopy (check name / market): " + ", ".join(not_found))
    if no_data:
        st.warning("No data (check name / date range): " + ", ".join(no_data))
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
                           file_name=f"{source.replace(' ','_')}_{timeframe}.zip",
                           mime="application/zip", type="primary",
                           use_container_width=True)
