import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import requests

# Sayfa ayarları
st.set_page_config(
    page_title="🔍 Fon Radar",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Başlık
st.title("🔍 Fon Radar")
st.markdown("**OKS/BES Fon Performans Denetçisi**")
st.markdown("---")

# Session state
if 'benim_fonlarim' not in st.session_state:
    st.session_state.benim_fonlarim = []

# TEFAS veri çekme - DİREKT API
@st.cache_data(ttl=3600)
def tefas_veri_cek(baslangic, bitis):
    """TEFAS API'den direkt veri çeker"""
    try:
        url = "https://www.tefas.gov.tr/api/DB/BindHistoryAllocation"
        
        all_data = []
        
        # YAT (Yatırım Fonları)
        for fontip in ['YAT', 'EMK']:
            params = {
                'fontip': fontip,
                'sfontur': '',
                'fonkod': '',
                'bastarih': baslangic.strftime('%d.%m.%Y'),
                'bittarih': bitis.strftime('%d.%m.%Y'),
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'tr-TR,tr;q=0.9',
            }
            
            try:
                response = requests.get(url, params=params, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'data' in data and data['data']:
                        df_temp = pd.DataFrame(data['data'])
                        all_data.append(df_temp)
            except:
                continue
        
        if all_data:
            df = pd.concat(all_data, ignore_index=True)
            
            # Tarih formatı
            df['TARIH'] = pd.to_datetime(df['TARIH'], format='%d-%m-%Y', errors='coerce')
            
            # Sayısal kolonlar
            numeric_cols = ['FIYAT', 'TEDPAYSAYISI', 'PORTFOYBUYUKLUK']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(
                        df[col].astype(str).str.replace(',', '.'),
                        errors='coerce'
                    )
            
            # Null değerleri temizle
            df = df.dropna(subset=['TARIH', 'FIYAT', 'FONKOD'])
            
            return df
        
        return pd.DataFrame()
    
    except Exception as e:
        st.error(f"Veri çekme hatası: {str(e)}")
        return pd.DataFrame()

# Gelişmiş analiz
def gelismis_analiz(df, gun):
    """15 özelliği içeren tam analiz"""
    try:
        son_tarih = df['TARIH'].max()
        baslangic_tarih = son_tarih - timedelta(days=gun)
        
        sonuclar = []
        
        for fonkod in df['FONKOD'].unique():
            fon_df = df[df['FONKOD'] == fonkod].sort_values('TARIH')
            
            if len(fon_df) < 2:
                continue
            
            # Son fiyat
            son_kayit = fon_df[fon_df['TARIH'] == son_tarih]
            if son_kayit.empty:
                son_kayit = fon_df.iloc[-1:]
            
            son_fiyat = son_kayit['FIYAT'].values[0]
            
            # Başlangıç fiyatı
            baslangic_df = fon_df[fon_df['TARIH'] >= baslangic_tarih]
            
            if len(baslangic_df) == 0:
                continue
            
            baslangic_fiyat = baslangic_df.iloc[0]['FIYAT']
            
            if baslangic_fiyat <= 0 or pd.isna(baslangic_fiyat):
                continue
            
            # 1. Getiri
            getiri = ((son_fiyat - baslangic_fiyat) / baslangic_fiyat) * 100
            
            # 6. Momentum
            son_7gun_tarih = son_tarih - timedelta(days=7)
            son_7gun_df = fon_df[fon_df['TARIH'] >= son_7gun_tarih]
            
            momentum = "📊"
            if len(son_7gun_df) >= 2:
                son_7_baslangic = son_7gun_df.iloc[0]['FIYAT']
                if son_7_baslangic > 0:
                    son_7_getiri = ((son_fiyat - son_7_baslangic) / son_7_baslangic) * 100
                    oran = abs(son_7_getiri) / (abs(getiri) / (gun / 7)) if getiri != 0 else 1
                    momentum = "📈" if son_7_getiri > 0 and oran > 0.8 else "📉"
            
            # 14. Drawdown
            fiyatlar = baslangic_df['FIYAT'].values
            max_dusus = 0
            
            if len(fiyatlar) > 0:
                zirve = fiyatlar[0]
                for fiyat in fiyatlar:
                    if fiyat > zirve:
                        zirve = fiyat
                    if zirve > 0:
                        dusus = ((zirve - fiyat) / zirve) * 100
                        if dusus > max_dusus:
                            max_dusus = dusus
            
            # 12. Risk (volatilite)
            if len(baslangic_df) > 2:
                gunluk_getiriler = baslangic_df['FIYAT'].pct_change().dropna()
                volatilite = gunluk_getiriler.std() * 100
                
                if volatilite < 0.5:
                    risk = "Düşük"
                    risk_skor = 1
                elif volatilite < 1.0:
                    risk = "Orta"
                    risk_skor = 2
                else:
                    risk = "Yüksek"
                    risk_skor = 3
            else:
                risk = "Bilinmiyor"
                risk_skor = 0
            
            sonuclar.append({
                'FONKOD': fonkod,
                'FONUNVAN': son_kayit['FONUNVAN'].values[0],
                'FIYAT': son_fiyat,
                'GETIRI': getiri,
                'MOMENTUM': momentum,
                'DRAWDOWN': max_dusus,
                'RISK': risk,
                'RISK_SKOR': risk_skor,
                'FONTIP': son_kayit.get('FONTIP', pd.Series(['Bilinmiyor'])).values[0],
                'FIYAT_DATA': fiyatlar.tolist()
            })
        
        return pd.DataFrame(sonuclar)
    
    except Exception as e:
        st.error(f"Analiz hatası: {str(e)}")
        return pd.DataFrame()

# Sidebar
st.sidebar.header("⚙️ Ayarlar")

# 3. Süre seçimi
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

# 13. Reel getiri
st.sidebar.markdown("---")
st.sidebar.subheader("💰 Kıyaslama")

enflasyon = st.sidebar.number_input(
    "Yıllık Enflasyon (%)",
    min_value=0.0,
    max_value=200.0,
    value=65.0,
    step=1.0
)

mevduat = st.sidebar.number_input(
    "Yıllık Mevduat Faizi (%)",
    min_value=0.0,
    max_value=100.0,
    value=50.0,
    step=1.0
)

# Veri çekme
with st.spinner('📊 TEFAS verisi çekiliyor... (30-60 saniye sürebilir)'):
    bugun = datetime.now()
    baslangic = bugun - timedelta(days=secili_gun + 15)
    
    df_ham = tefas_veri_cek(baslangic, bugun)

if df_ham.empty:
    st.error("❌ TEFAS verisi çekilemedi.")
    st.info("💡 Olası nedenler:")
    st.write("- TEFAS API'si geçici olarak erişilemez durumda")
    st.write("- İnternet bağlantınızda sorun var")
    st.write("- API limiti aşıldı (1-2 dakika bekleyip tekrar deneyin)")
    st.stop()

# Analiz
with st.spinner('🔢 Gelişmiş analiz yapılıyor...'):
    df_analiz = gelismis_analiz(df_ham, secili_gun)

if df_analiz.empty:
    st.error("❌ Analiz yapılamadı. Veri yetersiz.")
    st.stop()

# Başarı mesajı
st.success(f"✅ {len(df_analiz)} fon analiz edildi!")

# 2. Kategori filtresi
kategoriler = ['Tümü'] + sorted(df_analiz['FONTIP'].unique().tolist())
secili_kategori = st.sidebar.selectbox(
    "📂 Kategori",
    kategoriler
)

if secili_kategori != 'Tümü':
    df_filtre = df_analiz[df_analiz['FONTIP'] == secili_kategori].copy()
else:
    df_filtre = df_analiz.copy()

# 11. Sıralama
st.sidebar.markdown("---")
siralama_modu = st.sidebar.radio(
    "🔢 Sıralama",
    ["Getiri (Yüksek→Düşük)", "Getiri (Düşük→Yüksek)", "Risk (Düşük→Yüksek)", "Fon Adı (A→Z)"]
)

if siralama_modu == "Getiri (Yüksek→Düşük)":
    df_filtre = df_filtre.sort_values('GETIRI', ascending=False)
elif siralama_modu == "Getiri (Düşük→Yüksek)":
    df_filtre = df_filtre.sort_values('GETIRI', ascending=True)
elif siralama_modu == "Risk (Düşük→Yüksek)":
    df_filtre = df_filtre.sort_values('RISK_SKOR', ascending=True)
else:
    df_filtre = df_filtre.sort_values('FONUNVAN', ascending=True)

df_filtre = df_filtre.reset_index(drop=True)
df_filtre['SIRA'] = df_filtre.index + 1

# 7. Kategori ortalaması
ort_getiri = df_filtre['GETIRI'].mean()

# Metrikler
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📊 Toplam Fon", len(df_filtre))

with col2:
    st.metric("📈 Ortalama Getiri", f"%{ort_getiri:.2f}")

with col3:
    st.metric("🥇 En İyi", f"%{df_filtre['GETIRI'].max():.2f}")

with col4:
    st.metric("📉 En Kötü", f"%{df_filtre['GETIRI'].min():.2f}")

st.markdown("---")

# 4. Benim fonlarım
st.subheader("💼 Benim Fonlarım")

col_fon1, col_fon2 = st.columns([3, 1])

with col_fon1:
    yeni_fon = st.text_input("Fon kodu ekle:", "", key="fon_input")

with col_fon2:
    if st.button("➕ Ekle", use_container_width=True):
        if yeni_fon:
            yeni_fon_upper = yeni_fon.upper()
            if yeni_fon_upper in df_analiz['FONKOD'].values:
                if yeni_fon_upper not in st.session_state.benim_fonlarim:
                    st.session_state.benim_fonlarim.append(yeni_fon_upper)
                    st.success(f"✅ {yeni_fon_upper} eklendi!")
                    st.rerun()
                else:
                    st.warning("⚠️ Zaten listede!")
            else:
                st.error("❌ Fon bulunamadı!")

# 5. Lig sıralaması
if st.session_state.benim_fonlarim:
    st.markdown("#### 📍 Portföy Durumu")
    
    for fon_kod in st.session_state.benim_fonlarim:
        fon_bilgi = df_filtre[df_filtre['FONKOD'] == fon_kod]
        
        if not fon_bilgi.empty:
            fon = fon_bilgi.iloc[0]
            
            col_a, col_b, col_c = st.columns([2, 1, 1])
            
            with col_a:
                st.markdown(f"**{fon['FONKOD']}** - {fon['FONUNVAN'][:40]}")
            
            with col_b:
                getiri_renk = "🟢" if fon['GETIRI'] > ort_getiri else "🔴"
                st.metric("Getiri", f"%{fon['GETIRI']:.2f}", f"{getiri_renk}")
            
            with col_c:
                sira = fon['SIRA']
                toplam = len(df_filtre)
                yuzde = (sira / toplam) * 100
                
                if yuzde <= 20:
                    durum = "🥇"
                elif yuzde <= 50:
                    durum = "✅"
                else:
                    durum = "⚠️"
                
                st.metric("Sıra", f"{sira}/{toplam}", durum)
            
            # 13. Reel getiri
            yillik = (fon['GETIRI'] / secili_gun) * 365
            col_d, col_e, col_f = st.columns(3)
            
            with col_d:
                vs_enf = yillik - enflasyon
                st.caption(f"{'🟢' if vs_enf > 0 else '🔴'} vs Enf: {vs_enf:+.1f}%")
            
            with col_e:
                vs_mev = yillik - mevduat
                st.caption(f"{'🟢' if vs_mev > 0 else '🔴'} vs Mev: {vs_mev:+.1f}%")
            
            with col_f:
                st.caption(f"⚠️ Risk: {fon['RISK']}")
            
            if st.button(f"🗑️", key=f"remove_{fon_kod}"):
                st.session_state.benim_fonlarim.remove(fon_kod)
                st.rerun()
            
            st.markdown("---")

# 10. Arama
st.subheader("🔍 Hızlı Arama")
arama = st.text_input("Fon ara:", "")

if arama:
    df_filtre_arama = df_filtre[
        df_filtre['FONKOD'].str.contains(arama.upper(), na=False) | 
        df_filtre['FONUNVAN'].str.contains(arama.upper(), na=False)
    ]
else:
    df_filtre_arama = df_filtre

# 9. Top 10
st.subheader("🏆 En İyi 10 Fon")
df_top10 = df_filtre_arama.head(10).copy()

df_goster = df_top10[['SIRA', 'FONKOD', 'FONUNVAN', 'GETIRI', 'MOMENTUM', 'RISK', 'DRAWDOWN']].copy()
df_goster['GETIRI'] = df_goster['GETIRI'].apply(lambda x: f"%{x:.2f}")
df_goster['DRAWDOWN'] = df_goster['DRAWDOWN'].apply(lambda x: f"%{x:.1f}")
df_goster['FONUNVAN'] = df_goster['FONUNVAN'].apply(lambda x: x[:50])

st.dataframe(
    df_goster,
    use_container_width=True,
    hide_index=True,
    column_config={
        "SIRA": "Sıra",
        "FONKOD": "Kod",
        "FONUNVAN": "Fon",
        "GETIRI": "Getiri",
        "MOMENTUM": "Trend",
        "RISK": "Risk",
        "DRAWDOWN": "Max Düşüş"
    }
)

# 8. Grafik
st.markdown("---")
st.subheader("📈 Performans Grafiği")

secili_fonlar = st.multiselect(
    "Karşılaştır (max 5):",
    df_top10['FONKOD'].tolist(),
    default=[df_top10.iloc[0]['FONKOD']] if len(df_top10) > 0 else []
)

if secili_fonlar and len(secili_fonlar) <= 5:
    fig = go.Figure()
    
    for fon_kod in secili_fonlar:
        fon_data = df_analiz[df_analiz['FONKOD'] == fon_kod].iloc[0]
        fiyatlar = fon_data['FIYAT_DATA']
        
        if len(fiyatlar) > 0:
            baslangic = fiyatlar[0]
            normalize = [(f / baslangic) * 100 for f in fiyatlar]
            
            fig.add_trace(go.Scatter(
                y=normalize,
                mode='lines',
                name=fon_kod,
                line=dict(width=2)
            ))
    
    fig.update_layout(
        title="Performans (100 Bazlı)",
        xaxis_title="Gün",
        yaxis_title="İndeks",
        hovermode='x unified',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Tüm fonlar
st.markdown("---")
st.subheader("📊 Tüm Fonlar")

df_tumfonlar = df_filtre_arama.copy()
df_tumfonlar['GETIRI'] = df_tumfonlar['GETIRI'].apply(lambda x: f"%{x:.2f}")
df_tumfonlar['DRAWDOWN'] = df_tumfonlar['DRAWDOWN'].apply(lambda x: f"%{x:.1f}")

st.dataframe(
    df_tumfonlar[['SIRA', 'FONKOD', 'FONUNVAN', 'GETIRI', 'MOMENTUM', 'RISK']],
    use_container_width=True,
    hide_index=True,
    height=400
)

# 15. Footer
st.markdown("---")
son_guncelleme = df_ham['TARIH'].max().strftime('%d.%m.%Y')
st.caption(f"📅 Son Güncelleme: {son_guncelleme} | 🔍 Fon Radar v2.0")
