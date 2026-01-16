import streamlit as st
import pandas as pd
from tefas import Crawler
from datetime import datetime, timedelta
import plotly.express as px
import time

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="OKS Fon Avcısı", layout="wide", initial_sidebar_state="expanded")

st.title("🛡️ OKS Fon Performans Denetçisi")
st.markdown("*Veri Kaynağı: TEFAS (Emeklilik Gözetim Merkezi)*")

# --- SIDEBAR (AYARLAR) ---
st.sidebar.header("⚙️ Ayarlar")

# 1. Filtre Ayarı
show_all = st.sidebar.checkbox("Tüm BES Fonlarını Göster", value=False, help="İşaretlersen Gönüllü BES fonları da listeye dahil olur.")

# 2. Portföy (BURAYI KENDİ FONLARINLA GÜNCELLEMEYİ UNUTMA)
default_funds = "VGA,VEG,ALR,CHG,AH1" 
user_funds_input = st.sidebar.text_input("Takip Ettiğim Fonlar:", default_funds)
user_funds = [x.strip().upper() for x in user_funds_input.split(',')]

# 3. Süre ve Enflasyon
lookback_days = st.sidebar.selectbox("Analiz Süresi:", [30, 90, 180, 365], index=0)
st.sidebar.markdown("---")
inflation_rate = st.sidebar.number_input("Aylık Enflasyon Tahmini (%):", value=3.0, step=0.1)

# --- İNATÇI VERİ MOTORU (RETRY LOGIC) ---
@st.cache_data(ttl=3600)
def get_data(days):
    crawler = Crawler()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # 3 KERE DENEME DÖNGÜSÜ
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Veri Çekme (EMK = Emeklilik Fonları)
            df = crawler.fetch(
                start=start_date.strftime("%Y-%m-%d"), 
                end=end_date.strftime("%Y-%m-%d"), 
                kind="EMK"
            )
            
            # Eğer veri geldiyse ve boş değilse döngüyü kır, başarı!
            if df is not None and not df.empty:
                # Sütunları düzenle ve çık
                df = df.rename(columns={"code": "fonkodu", "title": "fonadi", "price": "fiyat", "date": "tarih"})
                df['tarih'] = pd.to_datetime(df['tarih'])
                df['fiyat'] = df['fiyat'].astype(float)
                return df
                
        except Exception as e:
            # Hata verirse bekle ve tekrar dene
            time.sleep(2) # 2 saniye nefes al
            continue

    # 3 kere denedi yine olmadıysa boş dön
    return pd.DataFrame()

# --- ANA AKIŞ ---
try:
    with st.spinner(f'Son {lookback_days} günün verileri sunucudan isteniyor...'):
        df = get_data(lookback_days)

    if df.empty:
        st.error("⚠️ TEFAS sunucuları şu an yanıt vermiyor veya çok yoğun. Lütfen 1-2 dakika bekleyip sayfayı yenileyin.")
        st.stop()

    # --- AKILLI FİLTRE (OKS) ---
    if not show_all:
        mask = (
            df['fonadi'].str.contains('OKS|OTOMATİK', case=False, na=False) | 
            df['fonkodu'].isin(user_funds)
        )
        filtered_df = df[mask]
        
        if filtered_df.empty:
            st.warning("⚠️ OKS filtresi sonucunda veri bulunamadı. Tüm fonlar gösteriliyor.")
        else:
            df = filtered_df

    # --- MATEMATİK ---
    pivot = df.pivot(index='tarih', columns='fonkodu', values='fiyat').ffill().bfill()
    
    first = pivot.iloc[0]
    last = pivot.iloc[-1]
    returns = ((last - first) / first) * 100
    
    league = pd.DataFrame({'Fon Kodu': returns.index, 'Getiri (%)': returns.values})
    
    names = df[['fonkodu', 'fonadi']].drop_duplicates(subset='fonkodu', keep='last').set_index('fonkodu')
    league = league.join(names, on='Fon Kodu')
    
    league = league.sort_values('Getiri (%)', ascending=False).reset_index(drop=True)
    league['Getiri (%)'] = league['Getiri (%)'].round(2)

    # --- EKRAN GÖRÜNTÜSÜ ---
    st.header(f"🏆 {'Tüm Emeklilik' if show_all else 'OKS'} Ligi ({lookback_days} Gün)")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.dataframe(league.head(20), use_container_width=True)
    with col2:
        top = league.iloc[0]
        st.info("📊 Pazar Özeti")
        st.metric("🥇 Lider Fon", top['Fon Kodu'], f"%{top['Getiri (%)']}")
        st.metric("Ortalama Getiri", f"%{league['Getiri (%)'].mean():.2f}")
        st.caption(f"Veri Tarihi: {df['tarih'].max().strftime('%d.%m.%Y')}")

    # --- PORTFÖY ---
    st.markdown("---")
    st.header("🔍 Portföy Analizi")
    
    my_portfolio = league[league['Fon Kodu'].isin(user_funds)]
    
    if not my_portfolio.empty:
        for _, row in my_portfolio.iterrows():
            code = row['Fon Kodu']
            ret = row['Getiri (%)']
            rank = row.name + 1 
            
            with st.expander(f"📌 {code} - {row['fonadi']}", expanded=True):
                k1, k2, k3 = st.columns(3)
                k1.metric("Net Getiri", f"%{ret}")
                k2.metric("Sıralama", f"{rank} / {len(league)}")
                
                target = inflation_rate * (lookback_days/30)
                if ret < target:
                    k3.error(f"⚠️ Zarardasın (Hedef: %{target:.1f})")
                else:
                    k3.success("✅ Kârdasın")
                
                chart_data = df[df['fonkodu'] == code]
                fig = px.line(chart_data, x='tarih', y='fiyat', title=f"{code} Fiyat Grafiği")
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Seçtiğin fonlar bu listede yok. Sol menüden 'Tümünü Göster'i deneyebilirsin.")

except Exception as e:
    st.error(f"Beklenmedik bir hata oluştu: {e}")
