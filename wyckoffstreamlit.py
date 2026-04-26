import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
from bs4 import BeautifulSoup
import requests

# Konfigurasi Halaman
st.set_page_config(page_title="Wyckoff Engine V4", layout="wide")

# ==========================================
# 1. ANALISIS SENTIMEN (KATALIS BERITA)
# ==========================================
def get_news_sentiment(ticker):
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}/news"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = [h.text.lower() for h in soup.find_all('h3')[:5]]
        
        pos = ['buy', 'profit', 'up', 'growth', 'akumulasi', 'naik', 'laba', 'invest', 'rebound']
        neg = ['sell', 'loss', 'down', 'drop', 'jual', 'rugi', 'crash', 'debt', 'lemah']
        
        score = 0
        for h in headlines:
            score += sum(1 for w in pos if w in h)
            score -= sum(1 for w in neg if w in h)
        
        return "Positive ✅" if score > 0 else "Negative ❌" if score < 0 else "Neutral ⚪"
    except:
        return "No Data"

# ==========================================
# 2. WYCKOFF ENGINE CORE
# ==========================================
@st.cache_data(ttl=3600)
def get_ultimate_wyckoff_v4(ticker, index_ticker="^JKSE"):
    try:
        # Ticker asli tetap digunakan untuk download data
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        idx = yf.download(index_ticker, period="1y", interval="1d", progress=False)
        
        if df.empty or len(df) < 100: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        if isinstance(idx.columns, pd.MultiIndex): idx.columns = idx.columns.get_level_values(0)

        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['Vol_Avg'] = df['Volume'].rolling(20).mean()
        
        curr = df.iloc[-1]
        c_price = float(curr['Close'])
        
        stock_perf = (c_price / df['Close'].iloc[-20]) - 1
        idx_perf = (idx['Close'].iloc[-1] / idx['Close'].iloc[-20]) - 1
        is_strong = stock_perf > idx_perf
        rs_label = "STRONG" if is_strong else "WEAK"

        recent_60 = df.tail(60)
        support = float(recent_60['Low'].min())
        resistance = float(recent_60['High'].max())
        buy_max = round(support * 1.04, 0)
        
        box_size = float(curr['ATR'] * 0.5)
        median_p = recent_60['Close'].median()
        cons_bars = recent_60[recent_60['Close'].between(median_p * 0.96, median_p * 1.04)]
        target_pf = round(((len(cons_bars)/3) * box_size * 3) + support, 0)
        upside_pct = round(((target_pf / c_price) - 1) * 100, 1)

        low_5 = float(df['Low'].tail(5).min())
        is_spring = (low_5 < support * 1.01) and (c_price > support)
        is_sos = (c_price > df['SMA50'].iloc[-1]) and (curr['Volume'] > curr['Vol_Avg'])
        
        decision = "WAIT"
        status = "CONSOLD"
        
        if is_spring and is_strong:
            status = "SPRING(C)"
            decision = "BUY" if c_price <= buy_max else "RUNNING"
        elif is_sos and is_strong:
            status = "SOS(D)"
            decision = "BUY/HOLD" if c_price <= resistance else "HOLD"
        elif c_price > resistance:
            status = "MARKUP(E)"
            decision = "HOLD"
        elif c_price < support:
            status = "MARKDOWN"
            decision = "AVOID"

        return {
            "Ticker": ticker.replace(".JK", ""), # Tampilan tanpa .JK
            "Price": int(c_price),
            "Buy Area": f"{int(support)} - {int(buy_max)}",
            "Target": int(target_pf),
            "Upside": f"{upside_pct}%",
            "Decision": decision,
            "Status": status,
            "RS": rs_label,
            "News Sentiment": get_news_sentiment(ticker)
        }
    except:
        return None

# ==========================================
# 3. STREAMLIT UI
# ==========================================

st.title("📈 Wyckoff Market Analysis Engine")
st.markdown("Screener saham otomatis untuk IHSG (Tanpa perlu mengetik .JK)")

# Input Watchlist (User cukup input kode saham saja)
default_watchlist = 'BBCA, BBRI, BMRI, TLKM, ASII, GOTO, BRMS, ADRO, AMRT, ANTM'
input_stocks = st.sidebar.text_area("Masukkan Kode Saham (pisahkan dengan koma):", default_watchlist)

# Proses input: hilangkan spasi, ubah ke uppercase, dan tambahkan .JK otomatis
watchlist_raw = [s.strip().upper() for s in input_stocks.split(',')]
watchlist_jk = [f"{s}.JK" if not s.endswith(".JK") else s for s in watchlist_raw]

if st.button("Run Analysis" ,type="primary"):
    results = []
    
    with st.spinner('Sedang menarik data dari Yahoo Finance...'):
        for t in watchlist_jk:
            res = get_ultimate_wyckoff_v4(t)
            if res:
                results.append(res)
    
    if results:
        df_result = pd.DataFrame(results)
        
        def highlight_decision(val):
            color = 'white'
            if val == 'BUY': color = '#2ecc71'
            elif val == 'BUY/HOLD': color = '#3498db'
            elif val == 'AVOID': color = '#e74c3c'
            elif val == 'HOLD': color = '#f1c40f'
            return f'background-color: {color}; color: black; font-weight: bold'

        st.subheader("Hasil Screening")
        # Kode lama (Error di Pandas 3.0)
st.dataframe(
    df_result.style.applymap(highlight_decision, subset=['Decision']),
    use_container_width=True,
    hide_index=True
)
        st.success(f"Berhasil menganalisis {len(results)} saham.")
    else:
        st.error("Data tidak ditemukan. Pastikan kode saham benar.")

st.divider()
st.caption("Fokus pada saham IHSG. Sistem otomatis menambahkan '.JK' di latar belakang.")
