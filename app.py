import streamlit as st
import pandas as pd
from tefas import Crawler
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="OKS/BEFAS Ham Veri", layout="wide")

st.title("🛡️ TEFAS/BEFAS Tüm Fonlar (Filtresiz)")
st.markdown(f"Veri Kaynağı: [TEFAS Emeklilik](https://www.tefas.gov.tr/FonKarsilastirma.aspx?type=emk)")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Ayarlar")
lookback_days = st.sidebar.selectbox("Geriye Dönük Gün Sayısı:", [30, 90, 180], index=0)

# --- VERİ ÇEKME (FİLTRESİZ) ---
@st.cache_data(ttl=600)
def get_all_data(days):
    crawler = Crawler()
    
    # Tarih Aralığı (Geniş tutuyoruz ki veri kesin gelsin)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # kind="EMK" -> Emeklilik Fonları (BES + OKS)
    # Bu komut senin verdiğin linkteki veriyi çeker.
    try:
        df = crawler.fetch(start=start_str, end=end_str, kind="EMK")
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return pd.DataFrame()
        
    if df is None or df.empty:
        return pd.DataFrame()

    # Sütun isimlerini düzelt
    df = df.rename(columns={"code": "fonkodu", "title": "fonadi", "price": "fiyat", "date": "tarih"})
    df['tarih'] = pd.to_datetime(df['tarih'])
    df['fiyat'] = df['fiyat'].astype(float)
    
    return df

# --- ANA EKRAN ---
with st.spinner('TEFAS sunucularından ham veri çekiliyor...'):
    df = get_all_data(lookback_days)

if df.empty:
    st.error("Veri gelmedi! TEFAS sunucularında sorun olabilir veya bugün resmi tatil/haftasonu olduğu için fiyat oluşmamış olabilir.")
    st.stop()

# Son günün verilerini al (Fon listesi için)
last_date = df['tarih'].max()
latest_df = df[df['tarih'] == last_date].copy()

# --- İSTATİSTİK ---
total_funds = len(latest_df['fonkodu'].unique())
oks_count = latest_df['fonadi'].str.contains('OKS|OTOMATİK', case=False).sum()

c1, c2, c3 = st.columns(3)
c1.metric("Toplam Emeklilik Fonu", total_funds)
c2.metric("Tespit Edilen OKS Fonu", oks_count)
c3.info(f"Son Veri Tarihi: {last_date.strftime('%d.%m.%Y')}")

# --- ARAMA VE KONTROL ---
st.markdown("### 🔍 Fon Arama & Kontrol")
st.markdown("Aşağıdaki kutuya **'OKS'** yazarak listenin içinde olup olmadıklarını gözünle görebilirsin.")

search_term = st.text_input("Fon Adı veya Kodu Ara:", "OKS")

# Arama Filtresi
if search_term:
    filtered_df = latest_df[
        latest_df['fonadi'].str.contains(search_term, case=False) | 
        latest_df['fonkodu'].str.contains(search_term, case=False)
    ]
else:
    filtered_df = latest_df

# Tabloyu Göster
st.dataframe(
    filtered_df[['fonkodu', 'fonadi', 'fiyat']].sort_values('fonadi'), 
    use_container_width=True,
    hide_index=True
)

# --- PORTFÖY TESTİ ---
st.markdown("---")
st.subheader("🧪 Portföy Testi")
my_codes = st.text_input("Test etmek istediğin fon kodları (Virgülle):", "VGA,VEG,CHG,ALR")
my_list = [x.strip().upper() for x in my_codes.split(',')]

found_funds = latest_df[latest_df['fonkodu'].isin(my_list)]

if not found_funds.empty:
    st.success("✅ Aşağıdaki fonlar sistemde BULUNDU:")
    st.table(found_funds[['fonkodu', 'fonadi', 'fiyat']])
else:
    st.error("❌ Yazdığın fonlar listede BULUNAMADI. İsimlerde hata olabilir mi?")
