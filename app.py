import streamlit as st
import pandas as pd
from tefas import Crawler
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="OKS Fon Avcısı", layout="wide", initial_sidebar_state="expanded")

st.title("🛡️ OKS/BES Fon Performans Denetçisi")
st.markdown("*Objektif Veri Analizi: Duygulara yer yok, sadece matematik.*")

# --- SIDEBAR (AYARLAR) ---
st.sidebar.header("⚙️ Denetim Ayarları")

# Madde 4: Benim Fonlarım
default_funds = "VGA,VEG,ALR,CHG" 
user_funds_input = st.sidebar.text_input("Benim Fonlarım (Kodları virgülle ayır):", default_funds)
user_funds = [x.strip().upper() for x in user_funds_input.split(',')]

# Madde 3: Analiz Süresi
lookback_days = st.sidebar.selectbox("Analiz Süresi (Gün):", [30, 90, 180, 365], index=0)

# Madde 13: Enflasyon Kıyası
st.sidebar.markdown("---")
st.sidebar.subheader("📉 Reel Getiri Kontrolü")
inflation_rate = st.sidebar.number_input("Aylık Enflasyon Beklentisi (%):", value=3.0, step=0.1)

# --- VERİ ÇEKME MOTORU ---
@st.cache_data(ttl=3600)
def get_data(days):
    crawler = Crawler()
    
    # Tarihleri kesinleştir
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Formatları string yap (YYYY-MM-DD)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Veriyi çek (EMK = Emeklilik Fonları)
    df = crawler.fetch(start=start_str, end=end_str, kind="EMK")
    
    # Sütunları düzenle
    df = df.rename(columns={
        "code": "fonkodu",
        "title": "fonadi",
        "price": "fiyat",
        "date": "tarih"
    })
    
    # Veri Tiplerini ZORLA (Hata önleyici)
    df['tarih'] = pd.to_datetime(df['tarih'])
    df['fiyat'] = df['fiyat'].astype(float)
    
    return df

try:
    with st.spinner(f'Son {lookback_days} günün verileri analiz ediliyor...'):
        df = get_data(lookback_days)

    # Veri Kontrolü (Hata ayıklama için bilgi)
    date_range = df['tarih'].max() - df['tarih'].min()
    st.info(f"📅 Analiz edilen veri aralığı: {df['tarih'].min().date()} - {df['tarih'].max().date()} ({date_range.days} Gün)")

    # --- HESAPLAMA ---
    pivot_df = df.pivot(index='tarih', columns='fonkodu', values='fiyat')
    
    # Veri boşluklarını doldur (Hafta sonları vs için önceki günü kopyala)
    pivot_df = pivot_df.ffill().bfill()

    # Getiri Hesapla: (Son Fiyat - İlk Fiyat) / İlk Fiyat
    # Not: İlk gün ile son gün arasındaki farkı alıyoruz
    first_prices = pivot_df.iloc[0]
    last_prices = pivot_df.iloc[-1]
    
    returns = ((last_prices - first_prices) / first_prices) * 100
    returns = returns.sort_values(ascending=False)
    
    # Tabloyu Hazırla
    league_table = pd.DataFrame({
        'Fon Kodu': returns.index,
        'Getiri (%)': returns.values
    })
    
    # İsimleri ekle
    last_day_info = df[df['tarih'] == df['tarih'].max()][['fonkodu', 'fonadi']].set_index('fonkodu')
    # Tekrarları önle
    last_day_info = last_day_info[~last_day_info.index.duplicated(keep='first')]
    
    league_table = league_table.join(last_day_info, on='Fon Kodu')
    league_table = league_table[['Fon Kodu', 'fonadi', 'Getiri (%)']] # Sıralama
    league_table['Getiri (%)'] = league_table['Getiri (%)'].round(2)

    # --- GÖRÜNÜM: LİG TABLOSU ---
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header(f"🏆 Top 20 Getiri Ligi ({lookback_days} Gün)")
        st.dataframe(league_table.head(20), use_container_width=True)
        
    with col2:
        st.header("📊 Özet")
        if not league_table.empty:
            top_fund = league_table.iloc[0]
            st.metric(label="🥇 Şampiyon", value=top_fund['Fon Kodu'], delta=f"%{top_fund['Getiri (%)']}")
            st.metric(label="Ortalama Getiri", value=f"%{league_table['Getiri (%)'].mean():.2f}")

    # --- GÖRÜNÜM: BENİM FONLARIM ---
    st.markdown("---")
    st.header("🔍 Portföy Analizi")
    
    my_funds_data = league_table[league_table['Fon Kodu'].isin(user_funds)]
    
    if not my_funds_data.empty:
        for index, row in my_funds_data.iterrows():
            f_code = row['Fon Kodu']
            f_return = row['Getiri (%)']
            f_name = row['fonadi']
            
            rank = league_table.index[league_table['Fon Kodu'] == f_code].tolist()[0] + 1
            total = len(league_table)
            
            with st.expander(f"📌 {f_code} - {f_name}", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Getiri", f"%{f_return}")
                c2.metric("Sıralama", f"{rank} / {total}")
                
                period_inflation = inflation_rate * (lookback_days / 30)
                if f_return < period_inflation:
                    c3.error(f"⚠️ Hedef Altında (Enf: %{period_inflation:.1f})")
                else:
                    c3.success("✅ Reel Kazanç")
                
                # Grafik
                fund_history = df[df['fonkodu'] == f_code]
                fig = px.line(fund_history, x='tarih', y='fiyat', title=f'{f_code} Fiyat Grafiği')
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Seçilen fonlara ait veri bulunamadı.")

except Exception as e:
    st.error(f"Hata oluştu: {e}")
