# ============================================================
#  Global Data Downloader  (WEBSITE version) - no login / API key needed
#    Crypto         -> Binance public dump (data.binance.vision)
#    Foreign Stocks -> Dukascopy (US / UK / Japan / Germany ...)
#    Foreign Index  -> Dukascopy (SP500, NAS100, DAX, NIKKEI ...)
#    Currency       -> Dukascopy (EURUSD, USDJPY ... ~68 pairs)
#    Commodity      -> Dukascopy (GOLD, SILVER, WTI, NATGAS ...)
#  Note: Indian NSE/MCX is NOT here (use the Angel/Fyers app for those).
#  Run:  streamlit run crypto_app.py
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import requests, io, zipfile, inspect
from datetime import datetime

st.set_page_config(page_title="Global Data Downloader",
                   page_icon="🌐", layout="centered")
st.title("Global Data Downloader")
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
#  SOURCES 2-5 : DUKASCOPY (stocks / index / currency / commodity)
# ============================================================
DUKA_MARKETS = ["US", "UK", "JAPAN", "GERMANY", "FRANCE", "ITALY",
                "NETHERLANDS", "SPAIN", "SWITZERLAND"]
DUKA_TF_NAMES = {'1min':'INTERVAL_MIN_1', '5min':'INTERVAL_MIN_5',
                 '15min':'INTERVAL_MIN_15', '30min':'INTERVAL_MIN_30',
                 '1h':'INTERVAL_HOUR_1', '4h':'INTERVAL_HOUR_4',
                 '1day':'INTERVAL_DAY_1', '1week':'INTERVAL_WEEK_1'}

def _duka_run(inst, timeframe, from_date, to_date):
    """Fetch + clean for a resolved Dukascopy instrument. None if no data."""
    import dukascopy_python
    interval = getattr(dukascopy_python, DUKA_TF_NAMES[timeframe])
    df = dukascopy_python.fetch(inst, interval, dukascopy_python.OFFER_SIDE_BID,
                                from_date, to_date)
    if df is None or df.empty:
        return None
    df = df.rename(columns={'open':'Open', 'high':'High', 'low':'Low',
                            'close':'Close', 'volume':'Volume'})
    keep = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
    return df[keep].rename_axis('Date')

# ---- Foreign STOCKS ----
def duka_stock_fetch(ticker, market, timeframe, from_date, to_date):
    from dukascopy_python import instruments as I
    t = ticker.strip().upper()
    inst = None
    for cur in ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "HKD"]:
        cand = f"INSTRUMENT_{market}_{t}_{market}_{cur}"
        if hasattr(I, cand):
            inst = getattr(I, cand); break
    if inst is None:
        for x in dir(I):
            if x.startswith(f"INSTRUMENT_{market}_{t}_"):
                inst = getattr(I, x); break
    if inst is None:
        return "NOSYM"
    return _duka_run(inst, timeframe, from_date, to_date)

# ---- Foreign INDEX ----
DUKA_INDEX_MAP = {
    'SP500':'INSTRUMENT_IDX_AMERICA_E_SANDP_500', 'NAS100':'INSTRUMENT_IDX_AMERICA_E_NQ_100',
    'DOW':'INSTRUMENT_IDX_AMERICA_E_D_J_IND', 'RUSSELL2000':'INSTRUMENT_IDX_AMERICA_USSC2000_IDX_USD',
    'RUSSELL':'INSTRUMENT_IDX_AMERICA_RUSSELL_IDX_USD', 'VIX':'INSTRUMENT_IDX_AMERICA_VOL_IDX_USD',
    'DOLLARIDX':'INSTRUMENT_IDX_AMERICA_DOLLAR_IDX_USD', 'DAX':'INSTRUMENT_IDX_EUROPE_E_DAAX',
    'FTSE':'INSTRUMENT_IDX_EUROPE_E_FUTSEE_100', 'CAC':'INSTRUMENT_IDX_EUROPE_E_CAAC_40',
    'EUSTOXX':'INSTRUMENT_IDX_EUROPE_E_DJE50XX', 'SWISS':'INSTRUMENT_IDX_EUROPE_E_SWMI',
    'IBEX':'INSTRUMENT_IDX_EUROPE_E_IBC_MAC', 'ITALY':'INSTRUMENT_IDX_EUROPE_ITA_IDX_EUR',
    'NETHERLANDS':'INSTRUMENT_IDX_EUROPE_NLD_IDX_EUR', 'POLAND':'INSTRUMENT_IDX_EUROPE_PLN_IDX_PLN',
    'PORTUGAL':'INSTRUMENT_IDX_PRT_IDX_EUR', 'NIKKEI':'INSTRUMENT_IDX_ASIA_E_N225JAP',
    'HANGSENG':'INSTRUMENT_IDX_ASIA_E_H_KONG', 'ASX':'INSTRUMENT_IDX_ASIA_E_XJO_ASX',
    'CHINA':'INSTRUMENT_IDX_ASIA_CHI_IDX_USD', 'INDIA':'INSTRUMENT_IDX_ASIA_IND_IDX_USD',
    'SINGAPORE':'INSTRUMENT_IDX_ASIA_SGD_IDX_SGD', 'SOUTHAFRICA':'INSTRUMENT_IDX_AFRICA_SOA_IDX_ZAR',
}
def duka_index_fetch(name, timeframe, from_date, to_date):
    from dukascopy_python import instruments as I
    attr = DUKA_INDEX_MAP.get(name.strip().upper())
    inst = getattr(I, attr, None) if attr else None
    if inst is None:
        return "NOSYM"
    return _duka_run(inst, timeframe, from_date, to_date)

# ---- COMMODITY ----
DUKA_CMD_MAP = {
    'GOLD':'INSTRUMENT_FX_METALS_XAU_USD', 'SILVER':'INSTRUMENT_FX_METALS_XAG_USD',
    'PLATINUM':'INSTRUMENT_CMD_METALS_XPT_CMD_USD', 'PALLADIUM':'INSTRUMENT_CMD_METALS_XPD_CMD_USD',
    'COPPER':'INSTRUMENT_CMD_METALS_COPPER_CMD_USD', 'WTI':'INSTRUMENT_CMD_ENERGY_E_LIGHT',
    'BRENT':'INSTRUMENT_CMD_ENERGY_E_BRENT', 'NATGAS':'INSTRUMENT_CMD_ENERGY_GAS_CMD_USD',
    'DIESEL':'INSTRUMENT_CMD_ENERGY_DIESEL_CMD_USD', 'COCOA':'INSTRUMENT_CMD_AGRICULTURAL_COCOA_CMD_USD',
    'COFFEE':'INSTRUMENT_CMD_AGRICULTURAL_COFFEE_CMD_USX', 'COTTON':'INSTRUMENT_CMD_AGRICULTURAL_COTTON_CMD_USX',
    'SUGAR':'INSTRUMENT_CMD_AGRICULTURAL_SUGAR_CMD_USD', 'SOYBEAN':'INSTRUMENT_CMD_AGRICULTURAL_SOYBEAN_CMD_USX',
    'ORANGEJUICE':'INSTRUMENT_CMD_AGRICULTURAL_OJUICE_CMD_USX',
}
def duka_cmd_fetch(name, timeframe, from_date, to_date):
    from dukascopy_python import instruments as I
    attr = DUKA_CMD_MAP.get(name.strip().upper())
    inst = getattr(I, attr, None) if attr else None
    if inst is None:
        return "NOSYM"
    return _duka_run(inst, timeframe, from_date, to_date)

# ---- CURRENCY (all FX pairs, built from the library) ----
@st.cache_data(show_spinner="Loading currency pairs...")
def duka_fx_map():
    from dukascopy_python import instruments as I
    fx = {}
    for x in dir(I):
        if x.startswith('INSTRUMENT_FX_') and 'METALS' not in x:
            v = getattr(I, x)              # e.g. 'EUR/USD'
            fx[v.replace('/', '')] = v     # 'EURUSD' -> 'EUR/USD'
    return fx
def duka_fx_fetch(name, timeframe, from_date, to_date):
    inst = duka_fx_map().get(name.strip().upper())
    if not inst:
        return "NOSYM"
    return _duka_run(inst, timeframe, from_date, to_date)

# ============================================================
#  Searchable name picker (dropdown: click to see all, type to filter, add many)
# ============================================================
POPULAR_COINS = ['BTC','ETH','BNB','SOL','XRP','ADA','DOGE','AVAX','DOT','MATIC',
                 'LINK','LTC','TRX','SHIB','UNI','ATOM','XLM','NEAR','APT','ARB']
POPULAR_TICKERS = ['AAPL','MSFT','GOOGL','AMZN','TSLA','META','NVDA','NFLX','AMD','INTC',
                   'JPM','V','DIS','BA','KO','PEP','WMT','NKE','PYPL','ORCL']

def select_names(label, options, placeholder, key):
    accept_new = "accept_new_options" in inspect.signature(st.multiselect).parameters
    kw = dict(options=options, placeholder=placeholder, key=key)
    if accept_new:
        kw["accept_new_options"] = True
    picked = st.multiselect(label, **kw)
    names = list(dict.fromkeys([str(s).strip() for s in picked if str(s).strip()]))
    if not accept_new:   # older Streamlit: allow typing custom names too
        extra = st.text_input("Other names (comma separated)", key=key + "_extra")
        for n in extra.split(","):
            n = n.strip()
            if n and n not in names:
                names.append(n)
    return names

# ============================================================
#  UI
# ============================================================
st.subheader("1. Choose data source")
source = st.radio("Source",
                  ["Crypto", "Foreign Stocks", "Foreign Index", "Currency", "Commodity"],
                  horizontal=True)

quote = market = None
if source == "Crypto":
    st.subheader("2. Which coins?")
    names = select_names("Coins", POPULAR_COINS, "Pick or type e.g. BTC, ETH", "sel_crypto")
    c1, c2 = st.columns(2)
    quote = c1.selectbox("Quote currency", ["USDT", "FDUSD", "USDC", "BTC", "ETH"])
    timeframe = c2.selectbox("Timeframe", list(BINANCE_TF), index=list(BINANCE_TF).index('1day'))
elif source == "Foreign Stocks":
    st.subheader("2. Which stocks?")
    st.caption("Global major stocks only. Indian NSE stocks are not available here.")
    names = select_names("Tickers", POPULAR_TICKERS, "Pick or type e.g. AAPL", "sel_stk")
    c1, c2 = st.columns(2)
    market = c1.selectbox("Market", DUKA_MARKETS)
    timeframe = c2.selectbox("Timeframe", list(DUKA_TF_NAMES), index=list(DUKA_TF_NAMES).index('1day'))
elif source == "Foreign Index":
    st.subheader("2. Which indices?")
    names = select_names("Indices", list(DUKA_INDEX_MAP.keys()), "Pick or type e.g. SP500", "sel_idx")
    timeframe = st.selectbox("Timeframe", list(DUKA_TF_NAMES), index=list(DUKA_TF_NAMES).index('1day'))
elif source == "Currency":
    st.subheader("2. Which currency pairs?")
    names = select_names("Pairs", sorted(duka_fx_map().keys()), "Pick or type e.g. EURUSD", "sel_fx")
    timeframe = st.selectbox("Timeframe", list(DUKA_TF_NAMES), index=list(DUKA_TF_NAMES).index('1day'))
else:  # Commodity
    st.subheader("2. Which commodities?")
    names = select_names("Commodities", list(DUKA_CMD_MAP.keys()), "Pick or type e.g. GOLD", "sel_cmd")
    timeframe = st.selectbox("Timeframe", list(DUKA_TF_NAMES), index=list(DUKA_TF_NAMES).index('1day'))

d1, d2 = st.columns(2)
from_date = d1.date_input("From date", value=datetime(2016, 1, 1))
to_date   = d2.date_input("To date",   value=datetime(2025, 12, 31))

st.divider()
run = st.button("Download data", type="primary", use_container_width=True)

# ============================================================
#  RUN
# ============================================================
if run:
    if not names:
        st.error("Please select or type at least one name."); st.stop()
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
            continue

        # ---- Dukascopy sources ----
        if source == "Foreign Stocks":
            label = f"{nm.upper()}_{market}"
            fetcher = lambda: duka_stock_fetch(nm, market, timeframe, f_date, t_date)
            miss = f"{nm.upper()} ({market})"
        elif source == "Foreign Index":
            label = nm.upper(); fetcher = lambda: duka_index_fetch(nm, timeframe, f_date, t_date)
            miss = f"{label} (not in list)"
        elif source == "Currency":
            label = nm.upper(); fetcher = lambda: duka_fx_fetch(nm, timeframe, f_date, t_date)
            miss = f"{label} (not a valid pair)"
        else:  # Commodity
            label = nm.upper(); fetcher = lambda: duka_cmd_fetch(nm, timeframe, f_date, t_date)
            miss = f"{label} (not in list)"

        prog.progress((i - 1) / len(names), text=f"{label} ...")
        try:
            out = fetcher()
        except Exception as e:
            no_data.append(f"{label} ({e})"); continue
        if isinstance(out, str) and out == "NOSYM":
            not_found.append(miss)
        elif out is None or out.empty:
            no_data.append(label)
        else:
            results[label] = out

    prog.progress(1.0, text="Done!")
    status.empty()

    if not_found:
        st.warning("Not found on Dukascopy: " + ", ".join(not_found))
    if no_data:
        st.warning("No data (check name / date range): " + ", ".join(no_data))
    if not results:
        st.error("No data returned."); st.stop()

    st.success(f"{len(results)} file(s) ready!")

    if len(results) > 1:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, df in results.items():
                zf.writestr(f"{name}_{timeframe}.csv", df.to_csv())
        st.download_button("Download all as ZIP", buf.getvalue(),
                           file_name=f"{source.replace(' ','_')}_{timeframe}.zip",
                           mime="application/zip", type="primary",
                           use_container_width=True)
        st.divider()

    for name, df in results.items():
        st.download_button(f"Download  {name}_{timeframe}.csv  ({len(df)} rows)",
                           df.to_csv().encode("utf-8"),
                           file_name=f"{name}_{timeframe}.csv",
                           mime="text/csv", key=f"dl_{name}",
                           use_container_width=True)
        with st.expander(f"Preview {name}"):
            st.dataframe(df.head(10), use_container_width=True)
