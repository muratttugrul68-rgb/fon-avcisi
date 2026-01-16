import streamlit as st
import pandas as pd
from tefas import Crawler
from datetime import datetime, timedelta
import plotly.express as px
import time

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="OKS Fon Avcısı", layout="wide", initial_sidebar_state="expanded")

st.title("🛡️ OKS/BES Fon Performans Denetçisi")
st.markdown("*Veri Kaynağı: TEFAS | Objektif Analiz*")

# --- SIDEBAR (AYARLAR) ---
st.sidebar.header("⚙️ Filtre Ayarları")

# 1. OKS TİKİ KUTUSU (İsteğin Üzerine Eklendi)
only_oks = st.sidebar.checkbox("Sadece OKS Fonları", value=True, help="Seçiliyse sadece Otomatik Katılım fonlarını listeler.")

# 2. Portföy
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
    
    # 3 KERE DENEME DÖNGÜSÜ (Bağlantı hatasına karşı)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Veri Çekme (EMK = Emeklilik Fonları)
            df = crawler.fetch(
                start=start_date.strftime("%Y-%m-%d"), 
                end=end_date.strftime("%Y-%m-%d"), 
                kind="EMK"
            )
            
            if df is not None and not df.empty:
                # Sütunları düzenle ve çık
                df = df.rename(columns={"code": "fonkodu", "title": "fonadi", "price": "fiyat", "date": "tarih"})
                df['tarih'] = pd.to_datetime(df['tarih'])
                df['fiyat'] = df['fiyat'].astype(float)
                return df
                
        except Exception as e:
            time.sleep(2) # Hata varsa 2 saniye bekle tekrar dene
            continue

    return pd.DataFrame()

# --- ANA AKIŞ ---
try:
    with st.spinner(f'Son {lookback_days} günün verileri analiz ediliyor...'):
        df = get_data(lookback_days)

    if df.empty:
        st.error("⚠️ TEFAS sunucularından veri alınamadı. Lütfen sayfayı yenileyin.")
        st.stop()

    # --- FİLTRELEME MANTIĞI ---
    if only_oks:
        # Sadece OKS fonlarını tut
        filtered_df = df[df['fonadi'].str.contains('OKS|OTOMATİK', case=False, na=False)]
        
        if filtered_df.empty:
            st.warning("⚠️ OKS filtresi sonucunda veri bulunamadı. Filtre geçici olarak kaldırılıyor.")
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
    
    # Sıralama (En çok kazandıran en üstte)
    league = league.sort_values('Getiri (%)', ascending=False).reset_index(drop=True)
    league['Getiri (%)'] = league['Getiri (%)'].round(2)

    # --- EKRAN GÖRÜNTÜSÜ ---
    
    # Başlık değişir: "OKS Ligi" veya "Tüm Emeklilik Ligi"
    st.header(f"🏆 {'OKS' if only_oks else 'Tüm Emeklilik'} Ligi ({lookback_days} Gün)")
    
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
        # Eğer OKS seçiliyse ve senin fonun OKS değilse burada uyarı verir
        msg = "Seçtiğin fonlar listede yok."
        if only_oks:
            msg += " (Not: 'Sadece OKS' kutusu işaretli, senin fonun OKS olmayabilir mi?)"
        st.warning(msg)

except Exception as e:
    st.error(f"Beklenmedik bir hata oluştu: {e}")
