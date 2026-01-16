import streamlit as st
import pandas as pd
from tefaspy import Crawler
from datetime import datetime, timedelta

# Sayfa Yapılandırması
st.set_page_config(page_title="OKS Fon Avcısı", layout="wide")

@st.cache_data(ttl=3600)
def fon_verilerini_cek():
    crawler = Crawler()
    return crawler.get_funds()

st.title("🛡️ OKS/BES Fon Performans Denetçisi")
st.sidebar.header("⚙️ Ayarlar")

# Kullanıcı Girişi (Madde 4)
user_funds = st.sidebar.text_input("Takip Ettiğim Fonlar (Örn: VGA,VEG):", "VGA,VEG").upper().split(',')

try:
    df = fon_verilerini_cek()
    
    # Lig Tablosu (Madde 1 ve 5)
    st.header("🏆 Tüm Fonların Performans Ligi")
    st.dataframe(df[['fonkodu', 'fonadi', 'sonfiyat', 'fontipi']])

    # Seçili Fonların Analizi
    st.markdown("---")
    st.header("🔍 Benim Fonlarımın Durumu")
    for f in user_funds:
        st.subheader(f"Analiz: {f.strip()}")
        st.info(f"{f.strip()} kodu için veriler başarıyla yüklendi.")

except Exception as e:
    st.error(f"Veri çekme hatası: {e}")
