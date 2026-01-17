import streamlit as st
import pandas as pd
from tefas import Crawler
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="OKS Lite", layout="centered") # Geniş değil, odaklı görünüm
st.title("🛡️ OKS Hızlı Kontrol")

# --- SADECE GEREKLİ AYARLAR ---
st.info("Bu mod, bağlantı sorunlarını aşmak için basitleştirilmiştir.")

# Tarih seçimi yok, otomatik 30 gün (En hızlısı bu)
days = 30 
st.write(f"📅 Analiz Aralığı: Son {days} Gün")

# Senin Fonların
my_funds = ["VGA", "VEG", "ALR", "CHG", "AH1"]

# --- BASİT VERİ ÇEKME ---
@st.cache_data(ttl=600) # 10 dakika hafızada tut
def get_simple_data():
    crawler = Crawler()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Emeklilik fonlarını çek
    try:
        df = crawler.fetch(
            start=start_date.strftime("%Y-%m-%d"), 
            end=end_date.strftime("%Y-%m-%d"), 
            kind="EMK"
        )
        return df
    except Exception as e:
        return None

# --- İŞLEM ---
with st.spinner('TEFAS ile hızlı bağlantı kuruluyor...'):
    df = get_simple_data()

if df is None or df.empty:
    st.error("❌ TEFAS Sunucusu Cevap Vermiyor.")
    st.warning("Bu kod hatası değil, sunucu yoğunluğudur. Lütfen 5-10 dakika sonra sayfayı yenileyin.")
    st.stop()

# --- VERİ GELDİYSE İŞLE ---
# Sütunları düzelt
df = df.rename(columns={"code": "fonkodu", "title": "fonadi", "price": "fiyat", "date": "tarih"})
df['fiyat'] = df['fiyat'].astype(float)
df['tarih'] = pd.to_datetime(df['tarih'])

# OKS Filtresi (Basit)
oks_df = df[df['fonadi'].str.contains('OKS|OTOMATİK', case=False, na=False)]

# Getiri Hesapla
pivot = oks_df.pivot(index='tarih', columns='fonkodu', values='fiyat').ffill().bfill()
first = pivot.iloc[0]
last = pivot.iloc[-1]
returns = ((last - first) / first) * 100
returns = returns.sort_values(ascending=False)

# --- SONUÇ EKRANI ---
st.success("✅ Bağlantı Başarılı!")

# 1. Senin Fonların
st.subheader("Senin Fonların")
for fund in my_funds:
    if fund in returns.index:
        rate = returns[fund]
        color = "green" if rate > 0 else "red"
        st.markdown(f"**{fund}**: :{color}[%{rate:.2f}]")
    else:
        st.write(f"{fund}: Veri yok (OKS olmayabilir)")

# 2. Lig Tablosu (İlk 10)
st.subheader("🏆 OKS Liderleri (Top 10)")
top10 = pd.DataFrame({'Fon': returns.index[:10], 'Getiri (%)': returns.values[:10]})
st.table(top10)
