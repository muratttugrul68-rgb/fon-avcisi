import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
from io import StringIO

# Sayfa ayarları
st.set_page_config(
    page_title="🔍 Fon Radar",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Başlık
st.title("🔍 Fon Radar")
st.markdown("**OKS/BES Fon Performans Denetçisi**")
st.markdown("---")

# TEFAS veri çekme fonksiyonu
@st.cache_data(ttl=3600)
def tefas_veri_cek(baslangic, bitis):
    """TEFAS'tan fon verilerini çeker"""
    try:
        url = "https://www.tefas.gov.tr/api/DB/BindHistoryAllocation"
        
        params = {
            'fontip': 'YAT',
            'sfontur': '',
            'fonkod': '',
            'bastarih': baslangic.strftime('%d.%m.%Y'),
            'bittarih': bitis.strftime('%d.%m.%Y'),
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data['data'])
            
            if not df.empty:
                # Tarih formatı düzeltme
                df['TARIH'] = pd.to_datetime(df['TARIH'], format='%d-%m-%Y')
                
                # Sayısal kolonları düzeltme
                numeric_cols = ['FIYAT', 'TEDPAYSAYISI', 'PORTFOYBUYUKLUK']
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
                
                return df
        
        return pd.DataFrame()
    
    except Exception as e:
        st.error(f"Veri çekme hatası: {str(e)}")
        return pd.DataFrame()

# Getiri hesaplama fonksiyonu
def getiri_hesapla(df, gun):
    """Belirli gün için getiri hesaplar"""
    try:
        son_tarih = df['TARIH'].max()
        baslangic_tarih = son_tarih - timedelta(days=gun)
        
        # Her fon için son ve başlangıç fiyatlarını bul
        sonuclar = []
        
        for fonkod in df['FONKOD'].unique():
            fon_df = df[df['FONKOD'] == fonkod].sort_values('TARIH')
            
            # En son fiyat
            son_fiyat = fon_df[fon_df['TARIH'] == son_tarih]['FIYAT'].values
            
            # Başlangıç fiyatı (en yakın tarih)
            baslangic_df = fon_df[fon_df['TARIH'] >= baslangic_tarih]
            
            if len(son_fiyat) > 0 and len(baslangic_df) > 0:
                baslangic_fiyat = baslangic_df.iloc[0]['FIYAT']
                son_fiyat = son_fiyat[0]
                
                if baslangic_fiyat > 0:
                    getiri = ((son_fiyat - baslangic_fiyat) / baslangic_fiyat) * 100
                    
                    # Fon bilgileri
                    son_kayit = fon_df.iloc[-1]
                    
                    sonuclar.append({
                        'FONKOD': fonkod,
                        'FONUNVAN': son_kayit['FONUNVAN'],
                        'FIYAT': son_fiyat,
                        'GETIRI': getiri,
                        'FONTIP': son_kayit.get('FONTIP', 'Bilinmiyor')
                    })
        
        return pd.DataFrame(sonuclar)
    
    except Exception as e:
        st.error(f"Getiri hesaplama hatası: {str(e)}")
        return pd.DataFrame()

# Sidebar - Filtreler
st.sidebar.header("⚙️ Filtreler")

# Süre seçimi
sure_secimi = st.sidebar.selectbox(
    "📅 Analiz Dönemi",
    ["Son 7 Gün", "Son 30 Gün", "Son 90 Gün"],
    index=1
)

gun_mapping = {
    "Son 7 Gün": 7,
    "Son 30 Gün": 30,
    "Son 90 Gün": 90
}

secili_gun = gun_mapping[sure_secimi]

# Veri çekme
with st.spinner('📊 TEFAS verisi çekiliyor...'):
    bugun = datetime.now()
    baslangic = bugun - timedelta(days=secili_gun + 10)  # Biraz fazla çek
    
    df_ham = tefas_veri_cek(baslangic, bugun)

if df_ham.empty:
    st.error("❌ TEFAS verisi çekilemedi. Lütfen daha sonra tekrar deneyin.")
    st.stop()

# Getiri hesapla
with st.spinner('🔢 Getiriler hesaplanıyor...'):
    df_getiri = getiri_hesapla(df_ham, secili_gun)

if df_getiri.empty:
    st.error("❌ Getiri hesaplanamadı.")
    st.stop()

# Kategori filtresi
kategoriler = ['Tümü'] + sorted(df_getiri['FONTIP'].unique().tolist())
secili_kategori = st.sidebar.selectbox(
    "📂 Kategori",
    kategoriler
)

# Filtreleme
if secili_kategori != 'Tümü':
    df_filtre = df_getiri[df_getiri['FONTIP'] == secili_kategori].copy()
else:
    df_filtre = df_getiri.copy()

# Sıralama
df_filtre = df_filtre.sort_values('GETIRI', ascending=False).reset_index(drop=True)
df_filtre['SIRA'] = df_filtre.index + 1

# Ana ekran
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📊 Toplam Fon", len(df_filtre))

with col2:
    ort_getiri = df_filtre['GETIRI'].mean()
    st.metric("📈 Ortalama Getiri", f"%{ort_getiri:.2f}")

with col3:
    en_iyi = df_filtre['GETIRI'].max()
    st.metric("🥇 En İyi", f"%{en_iyi:.2f}")

with col4:
    en_kotu = df_filtre['GETIRI'].min()
    st.metric("📉 En Kötü", f"%{en_kotu:.2f}")

st.markdown("---")

# Arama
st.subheader("🔍 Hızlı Arama")
arama = st.text_input("Fon kodu veya adı ile ara:", "")

if arama:
    df_filtre = df_filtre[
        df_filtre['FONKOD'].str.contains(arama.upper()) | 
        df_filtre['FONUNVAN'].str.contains(arama.upper())
    ]

# Top 10
st.subheader("🏆 En İyi 10 Fon")
df_top10 = df_filtre.head(10).copy()

# Momentum hesapla (basit versiyon)
df_top10['MOMENTUM'] = df_top10['GETIRI'].apply(
    lambda x: "📈" if x > ort_getiri else "📉"
)

# Tablo gösterimi
df_goster = df_top10[['SIRA', 'FONKOD', 'FONUNVAN', 'GETIRI', 'MOMENTUM', 'FIYAT']].copy()
df_goster['GETIRI'] = df_goster['GETIRI'].apply(lambda x: f"%{x:.2f}")
df_goster['FIYAT'] = df_goster['FIYAT'].apply(lambda x: f"{x:.4f} TL")

st.dataframe(
    df_goster,
    use_container_width=True,
    hide_index=True,
    column_config={
        "SIRA": "Sıra",
        "FONKOD": "Kod",
        "FONUNVAN": "Fon Adı",
        "GETIRI": "Getiri",
        "MOMENTUM": "Trend",
        "FIYAT": "Fiyat"
    }
)

# Tüm fonlar
st.markdown("---")
st.subheader("📊 Tüm Fonlar")

df_tumfonlar = df_filtre.copy()
df_tumfonlar['GETIRI'] = df_tumfonlar['GETIRI'].apply(lambda x: f"%{x:.2f}")
df_tumfonlar['FIYAT'] = df_tumfonlar['FIYAT'].apply(lambda x: f"{x:.4f} TL")

st.dataframe(
    df_tumfonlar[['SIRA', 'FONKOD', 'FONUNVAN', 'GETIRI', 'FIYAT']],
    use_container_width=True,
    hide_index=True,
    height=400,
    column_config={
        "SIRA": "Sıra",
        "FONKOD": "Kod",
        "FONUNVAN": "Fon Adı",
        "GETIRI": "Getiri",
        "FIYAT": "Fiyat"
    }
)

# Footer
st.markdown("---")
son_guncelleme = df_ham['TARIH'].max().strftime('%d.%m.%Y')
st.caption(f"📅 Son Güncelleme: {son_guncelleme} | 🔍 Fon Radar v1.0 | Veri: TEFAS")
