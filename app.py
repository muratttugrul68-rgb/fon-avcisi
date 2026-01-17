import streamlit as st
import pandas as pd
from tefas import Crawler
from datetime import datetime, timedelta
import time
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="OKS Güvenli Mod", layout="wide")
st.title("🛡️ OKS Fon Sistemi (Güvenli Mod)")

# --- AYARLAR ---
st.sidebar.header("⚙️ Ayarlar")
days = st.sidebar.selectbox("Analiz Süresi:", [30, 90, 180, 365], index=0)
user_funds_input = st.sidebar.text_input("Fonlarım:", "VGA,VEG,ALR,CHG,AH1")
user_funds = [x.strip().upper() for x in user_funds_input.split(',')]

# --- GÜVENLİ VERİ MOTORU ---
@st.cache_data(ttl=600)
def get_safe_data(lookback):
    crawler = Crawler()
    # Hafta sonu hatasını önlemek için bitiş tarihini dünden başlatabiliriz ama
    # biz geniş aralık alıp filtreleyeceğiz.
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback)
    
    # 3 Kere Dene (Retry Logic)
    for _ in range(3):
        try:
            df = crawler.fetch(
                start=start_date.strftime("%Y-%m-%d"), 
                end=end_date.strftime("%Y-%m-%d"), 
                kind="EMK"
            )
            if df is not None and not df.empty:
                return df
        except:
            time.sleep(1)
            continue
    return pd.DataFrame() # Başarısızsa boş dön

# --- İŞLEM ---
with st.spinner('Veriler kontrol edilerek çekiliyor...'):
    df = get_safe_data(days)

# 1. GÜVENLİK KONTROLÜ: Veri hiç geldi mi?
if df.empty:
    st.error("⚠️ TEFAS'tan veri çekilemedi.")
    st.info("İpucu: Hafta sonları bazen veri geç gelir. Lütfen 'Analiz Süresi'ni değiştirip tekrar deneyin.")
    st.stop() # UYGULAMAYI DURDUR (Çökmesini engeller)

# Veri Temizliği
df = df.rename(columns={"code": "fonkodu", "title": "fonadi", "price": "fiyat", "date": "tarih"})
df['fiyat'] = df['fiyat'].astype(float)
df['tarih'] = pd.to_datetime(df['tarih'])

# 2. GÜVENLİK KONTROLÜ: OKS Filtresi sonrası veri kalıyor mu?
oks_df = df[df['fonadi'].str.contains('OKS|OTOMATİK', case=False, na=False)]

if oks_df.empty:
    st.warning("⚠️ Veri çekildi ama 'OKS' kriterine uyan fon bulunamadı.")
    st.write("Tüm Emeklilik fonlarını gösteriyorum:")
    oks_df = df # Filtreyi iptal et, en azından bir şey gösterelim.

# Pivot İşlemi
pivot = oks_df.pivot(index='tarih', columns='fonkodu', values='fiyat').ffill().bfill()

# 3. GÜVENLİK KONTROLÜ: Pivot tablosu dolu mu?
if pivot.empty or len(pivot) < 2:
    st.warning("⚠️ Getiri hesaplamak için yeterli tarih verisi yok (En az 2 gün gerekli).")
    st.stop() # Çökmeden dur.

# --- HESAPLAMA (Artık buraya geldiyse veri kesin vardır) ---
try:
    first = pivot.iloc[0]
    last = pivot.iloc[-1]
    returns = ((last - first) / first) * 100
    returns = returns.sort_values(ascending=False)

    # Tablo
    league = pd.DataFrame({'Fon Kodu': returns.index, 'Getiri (%)': returns.values})
    
    # İsimleri ekle
    names = df[['fonkodu', 'fonadi']].drop_duplicates(subset='fonkodu', keep='last').set_index('fonkodu')
    league = league.join(names, on='Fon Kodu')
    league['Getiri (%)'] = league['Getiri (%)'].round(2)

    # --- EKRAN ---
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"🏆 Liderlik Tablosu ({days} Gün)")
        st.dataframe(league, use_container_width=True)
        
    with col2:
        st.subheader("🔍 Senin Fonların")
        my_data = league[league['Fon Kodu'].isin(user_funds)]
        if not my_data.empty:
            st.dataframe(my_data[['Fon Kodu', 'Getiri (%)']], use_container_width=True)
        else:
            st.info("Senin fonların bu listede yok.")

except Exception as e:
    st.error(f"Hesaplama hatası: {e}")
