import streamlit as st
import pandas as pd
from tefas import Crawler
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="BEFAS/OKS Avcısı", layout="wide")

st.title("🛡️ BEFAS & OKS Fon Performans Denetçisi")
st.markdown("*Veri Kaynağı: BEFAS (Emeklilik Gözetim Merkezi)*")

# --- SIDEBAR (AYARLAR) ---
st.sidebar.header("⚙️ Denetim Ayarları")

# Madde: OKS Filtresi
only_oks = st.sidebar.checkbox("Sadece OKS Fonlarını Göster", value=True, help="İşaretli değilse tüm BEFAS fonları görünür.")

# Madde 4: Benim Fonlarım
default_funds = "VGA,VEG,ALR,CHG" 
user_funds_input = st.sidebar.text_input("Benim Fonlarım (Kodları virgülle ayır):", default_funds)
user_funds = [x.strip().upper() for x in user_funds_input.split(',')]

# Madde 3: Analiz Süresi
lookback_days = st.sidebar.selectbox("Analiz Süresi (Gün):", [30, 90, 180, 365], index=0)

# Madde 13: Enflasyon
st.sidebar.markdown("---")
inflation_rate = st.sidebar.number_input("Aylık Enflasyon Beklentisi (%):", value=3.0)

# --- VERİ ÇEKME MOTORU ---
@st.cache_data(ttl=3600)
def get_befas_data(days):
    crawler = Crawler()
    
    # Tarih Hesaplama
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # DİKKAT: kind="EMK" komutu BEFAS (Emeklilik) verilerini çeker.
    try:
        df = crawler.fetch(start=start_str, end=end_str, kind="EMK")
    except Exception as e:
        return pd.DataFrame() # Hata durumunda boş dön

    if df is None or df.empty:
        return pd.DataFrame()

    # Sütunları düzenle
    df = df.rename(columns={"code": "fonkodu", "title": "fonadi", "price": "fiyat", "date": "tarih"})
    
    # Tipleri düzelt
    df['tarih'] = pd.to_datetime(df['tarih'])
    df['fiyat'] = df['fiyat'].astype(float)
    
    return df

# --- ANA PROGRAM AKIŞI ---
try:
    with st.spinner(f'BEFAS verileri taranıyor ({lookback_days} Gün)...'):
        df = get_befas_data(lookback_days)

    if df.empty:
        st.error("⚠️ BEFAS'tan veri çekilemedi. Hafta sonu veya resmi tatil nedeniyle fiyat oluşmamış olabilir. Lütfen 'Analiz Süresi'ni değiştirip tekrar deneyin.")
        st.stop()

    # --- FİLTRELEME ---
    # Eğer kullanıcı "Sadece OKS" dediyse filtrele
    if only_oks:
        # OKS filtreleme mantığı (İsminde OKS, OTOMATİK veya KATILIM geçenleri yakalamaya çalış)
        oks_mask = df['fonadi'].str.contains('OKS|OTOMATİK', case=False, na=False)
        
        # Eğer filtre sonucunda veri kalıyorsa filtreyi uygula
        if not df[oks_mask].empty:
            df = df[oks_mask]
        else:
            st.warning("⚠️ 'Sadece OKS' seçili ancak OKS etiketli veri bulunamadı. Tüm BEFAS fonları gösteriliyor.")

    # --- HESAPLAMA ---
    pivot_df = df.pivot(index='tarih', columns='fonkodu', values='fiyat').ffill().bfill()
    
    # Getiri Hesapla
    first_prices = pivot_df.iloc[0]
    last_prices = pivot_df.iloc[-1]
    returns = ((last_prices - first_prices) / first_prices) * 100
    returns = returns.sort_values(ascending=False)
    
    # Tablo Oluştur
    league_table = pd.DataFrame({'Fon Kodu': returns.index, 'Getiri (%)': returns.values})
    
    # Fon İsimlerini Getir
    last_day_info = df[['fonkodu', 'fonadi']].drop_duplicates(subset='fonkodu', keep='last').set_index('fonkodu')
    league_table = league_table.join(last_day_info, on='Fon Kodu')
    league_table = league_table[['Fon Kodu', 'fonadi', 'Getiri (%)']]
    league_table['Getiri (%)'] = league_table['Getiri (%)'].round(2)

    # --- GÖRÜNÜM ---
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header(f"🏆 {'OKS' if only_oks else 'BEFAS'} Ligi")
        st.dataframe(league_table.head(20), use_container_width=True)

    with col2:
        st.header("📊 Özet")
        top_fund = league_table.iloc[0]
        st.metric("🥇 Lider", top_fund['Fon Kodu'], f"%{top_fund['Getiri (%)']}")
        st.metric("Ortalama Getiri", f"%{league_table['Getiri (%)'].mean():.2f}")

    # --- PORTFÖYÜM ---
    st.markdown("---")
    st.header("🔍 Portföy Analizi")
    
    my_funds = league_table[league_table['Fon Kodu'].isin(user_funds)]
    
    if not my_funds.empty:
        for _, row in my_funds.iterrows():
            code = row['Fon Kodu']
            ret = row['Getiri (%)']
            rank = league_table.index[league_table['Fon Kodu'] == code].tolist()[0] + 1
            
            with st.expander(f"📌 {code} - {row['fonadi']}", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Getiri", f"%{ret}")
                c2.metric("Sıralama", f"{rank} / {len(league_table)}")
                
                target = inflation_rate * (lookback_days/30)
                if ret < target:
                    c3.error(f"⚠️ Hedef Altı (Enf: %{target:.1f})")
                else:
                    c3.success("✅ Başarılı")
                
                # Grafik
                fig = px.line(df[df['fonkodu'] == code], x='tarih', y='fiyat', title=f"{code} Grafiği")
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Portföyündeki fonlar listede yok. Kodları kontrol et veya 'Sadece OKS' kutucuğunu kaldırarak tüm BEFAS içinde ara.")

except Exception as e:
    st.error(f"Beklenmedik Hata: {e}")
