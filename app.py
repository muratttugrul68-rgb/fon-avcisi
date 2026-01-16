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
default_funds = "VGA,VEG,ALR,AH1" # Örnek OKS fonları
user_funds_input = st.sidebar.text_input("Benim Fonlarım (Kodları virgülle ayır):", default_funds)
user_funds = [x.strip().upper() for x in user_funds_input.split(',')]

# Madde 3: Analiz Süresi
lookback_days = st.sidebar.selectbox("Analiz Süresi (Gün):", [30, 90, 180, 365], index=1)

# Madde 13: Enflasyon Kıyası
st.sidebar.markdown("---")
st.sidebar.subheader("📉 Reel Getiri Kontrolü")
inflation_rate = st.sidebar.number_input("Aylık Enflasyon Beklentisi (%):", value=3.0, step=0.1)

# --- VERİ ÇEKME MOTORU (DÜZELTİLMİŞ) ---
@st.cache_data(ttl=3600)
def get_data(days):
    crawler = Crawler()
    # Bugünden geriye 'days' kadar git
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # DÜZELTME BURADA YAPILDI: "EYF" yerine "EMK" yazıldı.
    # EMK = Emeklilik Fonları
    df = crawler.fetch(start=start_date, kind="EMK")
    
    # Sütun isimlerini standartlaştır
    df = df.rename(columns={
        "code": "fonkodu",
        "title": "fonadi",
        "price": "fiyat",
        "date": "tarih"
    })
    
    # Tarihi datetime formatına çevir
    df['tarih'] = pd.to_datetime(df['tarih'])
    return df

try:
    with st.spinner(f'Son {lookback_days} günün Emeklilik Fonu (BES/OKS) verileri çekiliyor...'):
        df = get_data(lookback_days)

    # --- VERİ İŞLEME VE HESAPLAMA ---
    # Her fon için getiri hesapla
    pivot_df = df.pivot(index='tarih', columns='fonkodu', values='fiyat')
    
    # Yüzdesel Getiri Hesapla
    returns = ((pivot_df.iloc[-1] - pivot_df.iloc[0]) / pivot_df.iloc[0]) * 100
    returns = returns.sort_values(ascending=False)
    
    # Ana Tabloyu Oluştur
    league_table = pd.DataFrame({
        'Fon Kodu': returns.index,
        'Getiri (%)': returns.values
    })
    
    # Fon isimlerini ekle
    last_day_info = df[df['tarih'] == df['tarih'].max()][['fonkodu', 'fonadi']].set_index('fonkodu')
    league_table = league_table.join(last_day_info, on='Fon Kodu')
    
    # Tabloyu düzenle
    league_table = league_table[['Fon Kodu', 'fonadi', 'Getiri (%)']]
    league_table['Getiri (%)'] = league_table['Getiri (%)'].round(2)

    # --- GÖRÜNÜM: LİG TABLOSU ---
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header(f"🏆 Top 20 Getiri Ligi ({lookback_days} Gün)")
        st.dataframe(league_table.head(20), use_container_width=True)
        
    with col2:
        st.header("📊 Özet İstatistikler")
        top_fund = league_table.iloc[0]
        st.metric(label="🥇 Şampiyon Fon", value=top_fund['Fon Kodu'], delta=f"%{top_fund['Getiri (%)']}")
        st.metric(label="Ortalama Getiri", value=f"%{league_table['Getiri (%)'].mean():.2f}")

    # --- GÖRÜNÜM: BENİM FONLARIM ---
    st.markdown("---")
    st.header("🔍 Benim Fonlarımın Karnesi")
    
    my_funds_data = league_table[league_table['Fon Kodu'].isin(user_funds)]
    
    if not my_funds_data.empty:
        for index, row in my_funds_data.iterrows():
            f_code = row['Fon Kodu']
            f_return = row['Getiri (%)']
            
            # Sıralamasını bul
            rank = league_table.index[league_table['Fon Kodu'] == f_code].tolist()[0] + 1
            total_funds = len(league_table)
            
            # Kart Görünümü
            with st.expander(f"📌 {f_code} - {row['fonadi']}", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Getiri", f"%{f_return}", delta_color="normal")
                c2.metric("Sıralama", f"{rank} / {total_funds}", help="Tüm BES fonları arasındaki sırası")
                
                # Enflasyon Kontrolü
                period_inflation = inflation_rate * (lookback_days / 30)
                if f_return < period_inflation:
                    c3.error(f"⚠️ Enflasyona Yenildi! (Hedef: %{period_inflation:.1f})")
                else:
                    c3.success("✅ Reel Kazanç Var")
                
                # Grafik Çiz
                fund_history = df[df['fonkodu'] == f_code]
                fig = px.line(fund_history, x='tarih', y='fiyat', title=f'{f_code} Fiyat Hareketi')
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Girdiğin fon kodları listede bulunamadı. Lütfen fon kodlarının BES/OKS fonu olduğundan emin ol.")

except Exception as e:
    st.error(f"Bir hata oluştu. Lütfen şunları kontrol et:\n1. İnternet bağlantın var mı?\n2. TEFAS sunucuları yanıt veriyor mu?\n\nHata Detayı: {e}")
