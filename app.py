import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from tefas import Crawler

# Sayfa ayarları
st.set_page_config(
    page_title="🔍 Fon Radar",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Mobil optimizasyon
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

# Session state başlangıç
if 'benim_fonlarim' not in st.session_state:
    st.session_state.benim_fonlarim = []

# TEFAS veri çekme fonksiyonu
@st.cache_data(ttl=3600)
def tefas_veri_cek(baslangic, bitis):
    """TEFAS'tan tüm fonların verilerini çeker"""
    try:
        crawler = Crawler()
        
        # Tüm fonları çek
        df_list = []
        
        # YAT (Yatırım Fonları)
        try:
            data = crawler.fetch(
                start=baslangic.strftime('%d-%m-%Y'),
                end=bitis.strftime('%d-%m-%Y')
            )
            if data is not None and not data.empty:
                df_list.append(data)
        except:
            pass
        
        if df_list:
            df = pd.concat(df_list, ignore_index=True)
            
            # Tarih formatı
            if 'date' in df.columns:
                df['TARIH'] = pd.to_datetime(df['date'])
            
            # Kolon isimleri standardize et
            rename_map = {
                'code': 'FONKOD',
                'title': 'FONUNVAN',
                'price': 'FIYAT',
                'type': 'FONTIP'
            }
            
            for old, new in rename_map.items():
                if old in df.columns:
                    df[new] = df[old]
            
            return df
        
        return pd.DataFrame()
    
    except Exception as e:
        st.error(f"Veri çekme hatası: {str(e)}")
        return pd.DataFrame()

# Getiri ve analiz hesaplama
def gelismis_analiz(df, gun):
    """Gelişmiş performans analizi"""
    try:
        son_tarih = df['TARIH'].max()
        baslangic_tarih = son_tarih - timedelta(days=gun)
        
        sonuclar = []
        
        for fonkod in df['FONKOD'].unique():
            fon_df = df[df['FONKOD'] == fonkod].sort_values('TARIH')
            
            # Son fiyat
            son_fiyat = fon_df[fon_df['TARIH'] == son_tarih]['FIYAT'].values
            
            # Başlangıç fiyatı
            baslangic_df = fon_df[fon_df['TARIH'] >= baslangic_tarih]
            
            if len(son_fiyat) > 0 and len(baslangic_df) > 0:
                baslangic_fiyat = baslangic_df.iloc[0]['FIYAT']
                son_fiyat_val = son_fiyat[0]
                
                if baslangic_fiyat > 0:
                    # 1. Getiri
                    getiri = ((son_fiyat_val - baslangic_fiyat) / baslangic_fiyat) * 100
                    
                    # 6. Momentum (son 7 gün vs genel trend)
                    son_7gun_tarih = son_tarih - timedelta(days=7)
                    son_7gun_df = fon_df[fon_df['TARIH'] >= son_7gun_tarih]
                    
                    momentum = "📈"
                    if len(son_7gun_df) >= 2:
                        son_7_baslangic = son_7gun_df.iloc[0]['FIYAT']
                        son_7_getiri = ((son_fiyat_val - son_7_baslangic) / son_7_baslangic) * 100
                        
                        oran = son_7_getiri / (getiri / (gun / 7)) if getiri != 0 else 1
                        momentum = "📈" if oran > 1 else "📉"
                    
                    # 14. Drawdown (Maksimum düşüş)
                    fiyatlar = baslangic_df['FIYAT'].values
                    max_dusus = 0
                    
                    if len(fiyatlar) > 0:
                        zirve = fiyatlar[0]
                        for fiyat in fiyatlar:
                            if fiyat > zirve:
                                zirve = fiyat
                            dusus = ((zirve - fiyat) / zirve) * 100
                            if dusus > max_dusus:
                                max_dusus = dusus
                    
                    # Fon bilgileri
                    son_kayit = fon_df.iloc[-1]
                    
                    # 12. Risk seviyesi (volatilite bazlı basit hesap)
                    if len(baslangic_df) > 1:
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
                        'FONUNVAN': son_kayit['FONUNVAN'],
                        'FIYAT': son_fiyat_val,
                        'GETIRI': getiri,
                        'MOMENTUM': momentum,
                        'DRAWDOWN': max_dusus,
                        'RISK': risk,
                        'RISK_SKOR': risk_skor,
                        'FONTIP': son_kayit.get('FONTIP', 'Bilinmiyor'),
                        'FIYAT_DATA': fiyatlar.tolist()
                    })
        
        return pd.DataFrame(sonuclar)
    
    except Exception as e:
        st.error(f"Analiz hatası: {str(e)}")
        return pd.DataFrame()

# Sidebar
st.sidebar.header("⚙️ Ayarlar")

# 3. Dinamik Süre Seçimi
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

# 13. Reel Getiri Kontrolü (Manuel)
st.sidebar.markdown("---")
st.sidebar.subheader("💰 Kıyaslama")

enflasyon = st.sidebar.number_input(
    "Yıllık Enflasyon (%)",
    min_value=0.0,
    max_value=200.0,
    value=65.0,
    step=1.0,
    help="TÜİK verisi - Manuel güncelleme gerekir"
)

mevduat = st.sidebar.number_input(
    "Yıllık Mevduat Faizi (%)",
    min_value=0.0,
    max_value=100.0,
    value=50.0,
    step=1.0,
    help="Bankalardan ortalama faiz"
)

# Veri çekme
with st.spinner('📊 TEFAS verisi çekiliyor...'):
    bugun = datetime.now()
    baslangic = bugun - timedelta(days=secili_gun + 15)
    
    df_ham = tefas_veri_cek(baslangic, bugun)

if df_ham.empty:
    st.error("❌ TEFAS verisi çekilemedi. Lütfen daha sonra tekrar deneyin.")
    st.info("💡 İnternet bağlantınızı kontrol edin veya birkaç dakika sonra tekrar deneyin.")
    st.stop()

# Analiz
with st.spinner('🔢 Gelişmiş analiz yapılıyor...'):
    df_analiz = gelismis_analiz(df_ham, secili_gun)

if df_analiz.empty:
    st.error("❌ Analiz yapılamadı.")
    st.stop()

# 2. Kategori Filtresi
kategoriler = ['Tümü'] + sorted(df_analiz['FONTIP'].unique().tolist())
secili_kategori = st.sidebar.selectbox(
    "📂 Kategori",
    kategoriler
)

# Filtreleme
if secili_kategori != 'Tümü':
    df_filtre = df_analiz[df_analiz['FONTIP'] == secili_kategori].copy()
else:
    df_filtre = df_analiz.copy()

# 11. Sıralama Modları
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

# 7. Kategori Ortalaması
ort_getiri = df_filtre['GETIRI'].mean()
medyan_getiri = df_filtre['GETIRI'].median()

# Ana ekran metrikleri
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📊 Toplam Fon", len(df_filtre))

with col2:
    st.metric("📈 Ortalama Getiri", f"%{ort_getiri:.2f}")

with col3:
    en_iyi = df_filtre['GETIRI'].max()
    st.metric("🥇 En İyi", f"%{en_iyi:.2f}")

with col4:
    en_kotu = df_filtre['GETIRI'].min()
    st.metric("📉 En Kötü", f"%{en_kotu:.2f}")

st.markdown("---")

# 4. "Benim Fonlarım" Paneli
st.subheader("💼 Benim Fonlarım")

col_fon1, col_fon2 = st.columns([3, 1])

with col_fon1:
    yeni_fon = st.text_input(
        "Fon kodu ekle (örn: ABC)",
        "",
        key="fon_input",
        help="Takip etmek istediğin fonun kodunu yaz"
    )

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
                    st.warning("⚠️ Bu fon zaten listede!")
            else:
                st.error("❌ Fon bulunamadı!")

# 5. Lig Sıralaması - Benim fonlarımın durumu
if st.session_state.benim_fonlarim:
    st.markdown("#### 📍 Portföy Durumu")
    
    for fon_kod in st.session_state.benim_fonlarim:
        fon_bilgi = df_filtre[df_filtre['FONKOD'] == fon_kod]
        
        if not fon_bilgi.empty:
            fon = fon_bilgi.iloc[0]
            
            col_a, col_b, col_c = st.columns([2, 1, 1])
            
            with col_a:
                st.markdown(f"**{fon['FONKOD']}** - {fon['FONUNVAN'][:50]}")
            
            with col_b:
                getiri_renk = "🟢" if fon['GETIRI'] > ort_getiri else "🔴"
                st.metric(
                    "Getiri",
                    f"%{fon['GETIRI']:.2f}",
                    f"{getiri_renk} Ort: %{ort_getiri:.2f}"
                )
            
            with col_c:
                toplam_fon = len(df_filtre)
                sira = fon['SIRA']
                yuzde = (sira / toplam_fon) * 100
                
                if yuzde <= 20:
                    durum = "🥇 Üst %20"
                elif yuzde <= 50:
                    durum = "✅ Üst Yarı"
                elif yuzde <= 80:
                    durum = "⚠️ Alt Yarı"
                else:
                    durum = "🚨 Alt %20"
                
                st.metric("Sıralama", f"{sira}/{toplam_fon}", durum)
            
            # 13. Reel Getiri Kontrolü
            yillik_getiri = (fon['GETIRI'] / secili_gun) * 365
            
            col_d, col_e, col_f = st.columns(3)
            
            with col_d:
                vs_enf = yillik_getiri - enflasyon
                renk_enf = "🟢" if vs_enf > 0 else "🔴"
                st.caption(f"{renk_enf} Enflasyon: {vs_enf:+.1f}%")
            
            with col_e:
                vs_mev = yillik_getiri - mevduat
                renk_mev = "🟢" if vs_mev > 0 else "🔴"
                st.caption(f"{renk_mev} Mevduat: {vs_mev:+.1f}%")
            
            with col_f:
                st.caption(f"⚠️ Risk: {fon['RISK']}")
            
            # Silme butonu
            if st.button(f"🗑️ Kaldır", key=f"remove_{fon_kod}"):
                st.session_state.benim_fonlarim.remove(fon_kod)
                st.rerun()
            
            st.markdown("---")

# 10. Hızlı Arama
st.subheader("🔍 Hızlı Arama")
arama = st.text_input("Fon kodu veya adı ile ara:", "")

if arama:
    df_filtre_arama = df_filtre[
        df_filtre['FONKOD'].str.contains(arama.upper(), na=False) | 
        df_filtre['FONUNVAN'].str.contains(arama.upper(), na=False)
    ]
else:
    df_filtre_arama = df_filtre

# 9. Top 10 Hızlı Liste
st.subheader("🏆 En İyi 10 Fon")
df_top10 = df_filtre_arama.head(10).copy()

# Tablo
df_goster = df_top10[['SIRA', 'FONKOD', 'FONUNVAN', 'GETIRI', 'MOMENTUM', 'RISK', 'DRAWDOWN', 'FIYAT']].copy()
df_goster['GETIRI'] = df_goster['GETIRI'].apply(lambda x: f"%{x:.2f}")
df_goster['DRAWDOWN'] = df_goster['DRAWDOWN'].apply(lambda x: f"%{x:.1f}")
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
        "RISK": "Risk",
        "DRAWDOWN": "Max Düşüş",
        "FIYAT": "Fiyat"
    }
)

# 8. İnteraktif Grafik
st.markdown("---")
st.subheader("📈 Performans Grafiği")

secili_fonlar = st.multiselect(
    "Karşılaştırmak için fon seç (max 5):",
    df_top10['FONKOD'].tolist(),
    default=[df_top10.iloc[0]['FONKOD']] if len(df_top10) > 0 else []
)

if secili_fonlar and len(secili_fonlar) <= 5:
    fig = go.Figure()
    
    for fon_kod in secili_fonlar:
        fon_data = df_analiz[df_analiz['FONKOD'] == fon_kod].iloc[0]
        fiyatlar = fon_data['FIYAT_DATA']
        
        if len(fiyatlar) > 0:
            # Normalize et (100 bazlı)
            baslangic = fiyatlar[0]
            normalize = [(f / baslangic) * 100 for f in fiyatlar]
            
            fig.add_trace(go.Scatter(
                y=normalize,
                mode='lines',
                name=fon_kod,
                line=dict(width=2)
            ))
    
    fig.update_layout(
        title="Fon Performans Karşılaştırması (100 Bazlı)",
        xaxis_title="Gün",
        yaxis_title="İndeks (Başlangıç=100)",
        hovermode='x unified',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

elif len(secili_fonlar) > 5:
    st.warning("⚠️ En fazla 5 fon seçebilirsiniz")

# Tüm fonlar tablosu
st.markdown("---")
st.subheader("📊 Tüm Fonlar")

df_tumfonlar = df_filtre_arama.copy()
df_tumfonlar['GETIRI'] = df_tumfonlar['GETIRI'].apply(lambda x: f"%{x:.2f}")
df_tumfonlar['DRAWDOWN'] = df_tumfonlar['DRAWDOWN'].apply(lambda x: f"%{x:.1f}")
df_tumfonlar['FIYAT'] = df_tumfonlar['FIYAT'].apply(lambda x: f"{x:.4f} TL")

st.dataframe(
    df_tumfonlar[['SIRA', 'FONKOD', 'FONUNVAN', 'GETIRI', 'MOMENTUM', 'RISK', 'DRAWDOWN']],
    use_container_width=True,
    hide_index=True,
    height=400,
    column_config={
        "SIRA": "Sıra",
        "FONKOD": "Kod",
        "FONUNVAN": "Fon Adı",
        "GETIRI": "Getiri",
        "MOMENTUM": "Trend",
        "RISK": "Risk",
        "DRAWDOWN": "Max Düşüş"
    }
)

# 15. Veri Tazelik Damgası - Footer
st.markdown("---")
son_guncelleme = df_ham['TARIH'].max().strftime('%d.%m.%Y')
st.caption(f"📅 Son Güncelleme: {son_guncelleme} | 🔍 Fon Radar v2.0 | Veri: TEFAS")
st.caption("⚠️ Geçmiş performans gelecek performansın garantisi değildir. Yatırım kararlarınızı danışman desteği ile alın.")
