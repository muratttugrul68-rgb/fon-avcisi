import streamlit as st
import pandas as pd
from tefas import Crawler
from datetime import datetime, timedelta
import time

# --- SAYFA ---
st.set_page_config(page_title="OKS Tanı Modu", layout="wide")
st.title("🛡️ OKS Veri Röntgeni")

# --- AYARLAR ---
st.sidebar.header("Ayarlar")
# Güvenli olsun diye 30 günü seçili getiriyorum
days = st.sidebar.selectbox("Süre:", [30, 90, 180], index=0) 

# Senin Fonların (Filtre çalışmasa bile bunları zorla bulacağız)
my_codes_input = st.sidebar.text_input("Fon Kodların:", "VGA,VEG,ALR,CHG,AH1")
my_codes = [x.strip().upper() for x in my_codes_input.split(',')]

# --- VERİ ÇEKME ---
@st.cache_data(ttl=600)
def get_data_diagnostic(lookback):
    crawler = Crawler()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback)
    
    for _ in range(3): # 3 Kere Dene
        try:
            # kind="EMK" -> Emeklilik (BES+OKS)
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
    return pd.DataFrame()

# --- İŞLEM ---
with st.spinner('TEFAS deposuna giriliyor...'):
    df = get_data_diagnostic(days)

# 1. KONTROL: Depo boş mu?
if df.empty:
    st.error("❌ Depo boş döndü. (TEFAS yanıt vermedi).")
    st.stop()

# Veri temizliği
df = df.rename(columns={"code": "fonkodu", "title": "fonadi", "price": "fiyat", "date": "tarih"})
df['fiyat'] = df['fiyat'].astype(float)
df['tarih'] = pd.to_datetime(df['tarih'])

st.success(f"✅ Başarılı! Toplam {len(df['fonkodu'].unique())} adet emeklilik fonu çekildi.")

# --- FİLTRELEME TESTİ ---
st.markdown("---")
col1, col2 = st.columns(2)

# SENİN FONLARINI ARA (İsminde OKS yazmasa bile bulur)
with col1:
    st.subheader("🔍 Senin Fonların")
    my_funds_df = df[df['fonkodu'].isin(my_codes)]
    
    if not my_funds_df.empty:
        # Son günün fiyatını al
        last_date = my_funds_df['tarih'].max()
        display_df = my_funds_df[my_funds_df['tarih'] == last_date][['fonkodu', 'fonadi', 'fiyat']]
        st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("Senin yazdığın kodlar (VGA, CHG vb.) listede bulunamadı.")

# GENEL OKS ARAMASI
with col2:
    st.subheader("🔎 Sistemdeki 'OKS' Fonları")
    # Filtreyi esnetiyoruz: Sadece 'OKS' değil, 'OTOMATİK' veya 'KATILIM' da arayalım
    oks_mask = df['fonadi'].str.contains('OKS|OTOMATİK|KATILIM Standart|Agresif', case=False, na=False)
    oks_list = df[oks_mask]
    
    if not oks_list.empty:
        last_date = oks_list['tarih'].max()
        oks_show = oks_list[oks_list['tarih'] == last_date][['fonkodu', 'fonadi']].drop_duplicates()
        st.write(f"Toplam {len(oks_show)} adet OKS benzeri fon bulundu.")
        st.dataframe(oks_show.head(10), use_container_width=True) # İlk 10 tanesini göster
    else:
        st.error("İsminde 'OKS' geçen fon bulunamadı.")
        st.info("Aşağıda veritabanından rastgele 5 fon ismi gösteriyorum, bak bakalım isimleri nasıl yazmışlar?")
        st.table(df[['fonkodu', 'fonadi']].drop_duplicates().head(5))

# --- GETİRİ HESABI (Varsa) ---
if not my_funds_df.empty:
    st.markdown("---")
    st.subheader("📈 Senin Fonlarının Getirisi")
    pivot = my_funds_df.pivot(index='tarih', columns='fonkodu', values='fiyat').ffill().bfill()
    
    if len(pivot) > 1:
        first = pivot.iloc[0]
        last = pivot.iloc[-1]
        ret = ((last - first) / first) * 100
        st.bar_chart(ret)
    else:
        st.warning("Getiri hesabı için tarih aralığı yetersiz (Veri tek günlük olabilir).")
