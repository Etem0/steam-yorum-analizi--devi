"""
BASİT STEAM YORUM ANALİZİ
-------------------------
Çalıştırma:  python -m streamlit run app.py

Ne yapar?
  1. Oyun adını alır, Steam'de arar.
  2. Oyunun son yorumlarını Steam'den çeker.
  3. Olumlu / olumsuz oranını ve günlük yorum grafiğini gösterir.
"""

# ---------------------------------------------------------------------------
# 1) KÜTÜPHANELER (hazır araç kutuları)
# ---------------------------------------------------------------------------
import json                                   # Veriyi JSON metnine çevirmek için
import time                                   # Beklemek için (Steam'i yormamak adına)
from datetime import datetime, timedelta      # Tarih işlemleri için

import pandas as pd                           # Tablo (DataFrame) işlemleri için
import requests                               # İnternetten veri çekmek için
import streamlit as st                        # Web sayfası arayüzü için


# ---------------------------------------------------------------------------
# 2) FONKSİYONLAR (tekrar kullanılan küçük işler)
# ---------------------------------------------------------------------------
# @st.cache_data: Aynı soruyu 1 saat içinde tekrar sorarsan Steam'e yeniden gitmez,
# eski cevabı hatırlar. Böylece sayfa hızlı çalışır.
@st.cache_data(ttl=3600)
def oyun_ara(ad):
    """Oyun adını Steam'de arar, bulunan oyunların listesini döndürür."""
    cevap = requests.get(
        "https://store.steampowered.com/api/storesearch/",
        params={"term": ad, "cc": "tr", "l": "turkish"},
        timeout=20,
    )
    cevap.raise_for_status()                  # Hata kodu geldiyse (404, 500...) hata fırlat
    return cevap.json().get("items", [])      # Her oyun: {"id": ..., "name": ..., ...}


@st.cache_data(ttl=3600)
def yorumlari_cek(appid, gun, maks, dil):
    """Oyunun son `gun` gündeki yorumlarını (en fazla `maks` tane) çeker."""
    url = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
    sinir = datetime.now() - timedelta(days=gun)   # Bundan eski yorumları almayacağız
    yorumlar = []                                   # Bulunan yorumlar buraya eklenecek
    cursor = "*"                                    # "*" = ilk sayfadan başla

    while len(yorumlar) < maks:
        # Steam'e ne istediğimizi söylüyoruz
        istek = {
            "appid": appid,
            "filter": 1,                  # 1 = en yeni yorumlar önce
            "languages": [dil],           # "all", "turkish", "english" gibi
            "purchase_type": 1,           # Tüm satın alma türleri
            "num_per_page": 100,          # Bir seferde 100 yorum
            "cursor": cursor,             # Hangi sayfadayız
        }
        cevap = requests.get(url, params={"input_json": json.dumps(istek)}, timeout=20)
        cevap.raise_for_status()
        veri = cevap.json().get("response", {})
        sayfa = veri.get("reviews", [])

        if not sayfa:                     # Yorum kalmadıysa dur
            break

        sinira_geldik = False
        for y in sayfa:
            tarih = datetime.fromtimestamp(y["timestamp_created"])
            if tarih < sinir:             # Çok eski yoruma geldik, artık dur
                sinira_geldik = True
                break
            yorumlar.append({
                "Tarih": tarih,
                "Yorum": y.get("review", ""),
                "Öneriyor": y.get("voted_up", False),   # True = oyuncu oyunu öneriyor
            })

        yeni_cursor = veri.get("cursor")
        if sinira_geldik or not yeni_cursor or yeni_cursor == cursor:
            break
        cursor = yeni_cursor              # Sonraki sayfaya geç
        time.sleep(0.6)                   # Steam'i yormamak için kısa bekleme

    return pd.DataFrame(yorumlar).head(maks)


# ---------------------------------------------------------------------------
# 3) SAYFA ARAYÜZÜ
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Steam Yorum Analizi", page_icon="🎮")
st.title("🎮 Steam Yorum Analizi")

# Sol menü: kullanıcının seçeceği ayarlar
with st.sidebar:
    st.header("Ayarlar")
    oyun_adi = st.text_input("Oyun adı", placeholder="örn. Counter-Strike 2")
    gun = st.slider("Son kaç günün yorumları?", 7, 180, 30)
    maks = st.slider("En fazla kaç yorum?", 100, 1000, 300, step=100)
    dil_secenekleri = {"Tümü": "all", "Türkçe": "turkish", "İngilizce": "english"}
    dil_adi = st.selectbox("Yorum dili", list(dil_secenekleri))
    dil = dil_secenekleri[dil_adi]

# Oyun adı yazılmadıysa bilgi verip dur
if not oyun_adi.strip():
    st.info("👈 Sol menüden bir oyun adı yazıp Enter'a basın.")
    st.stop()                                 # Kodun geri kalanı çalışmaz

# --- Oyunu bul ---
try:
    oyunlar = oyun_ara(oyun_adi.strip())
except requests.RequestException as hata:
    st.error(f"Oyun aranırken hata oluştu: {hata}")
    st.stop()

if not oyunlar:
    st.warning("Oyun bulunamadı. Adı farklı yazmayı deneyin.")
    st.stop()

# Birden fazla sonuç olabilir: kullanıcı doğru oyunu seçsin
oyun = st.selectbox("Doğru oyunu seçin:", oyunlar, format_func=lambda o: o["name"])

# --- Yorumları çek ---
try:
    with st.spinner("Yorumlar çekiliyor..."):
        df = yorumlari_cek(oyun["id"], gun, maks, dil)
except requests.RequestException as hata:
    st.error(f"Yorumlar çekilemedi: {hata}")
    st.caption("Çok sık istek gönderdiyseniz bir dakika bekleyip tekrar deneyin.")
    st.stop()

if df.empty:
    st.warning("Bu ayarlarla yorum bulunamadı. Gün sayısını artırmayı veya dili 'Tümü' yapmayı deneyin.")
    st.stop()

# --- Duygu: Steam'de oyuncu zaten "öneriyorum / önermiyorum" diyor ---
df["Duygu"] = df["Öneriyor"].map({True: "Olumlu", False: "Olumsuz"})

# --- Özet kutuları ---
olumlu_sayi = int((df["Duygu"] == "Olumlu").sum())
olumsuz_sayi = len(df) - olumlu_sayi

st.header(oyun["name"])
k1, k2, k3 = st.columns(3)                    # Yan yana 3 sütun
k1.metric("Toplam yorum", len(df))
k2.metric("Olumlu", f"%{olumlu_sayi / len(df) * 100:.0f}")
k3.metric("Olumsuz", f"%{olumsuz_sayi / len(df) * 100:.0f}")

# --- Günlük yorum grafiği ---
st.subheader("Günlük yorum sayısı")
df["Gün"] = df["Tarih"].dt.strftime("%Y-%m-%d")           # Saati at, sadece günü tut
gunluk = pd.crosstab(df["Gün"], df["Duygu"])              # Gün x Duygu sayım tablosu
st.bar_chart(gunluk)

# --- Tüm yorumlar tablosu + indirme ---
st.subheader("Yorumlar")
tablo = df[["Tarih", "Yorum", "Duygu"]]
st.dataframe(tablo, hide_index=True)

st.download_button(
    "⬇️ CSV olarak indir",
    tablo.to_csv(index=False).encode("utf-8-sig"),   # utf-8-sig: Excel'de Türkçe karakterler bozulmasın
    file_name="yorumlar.csv",
    mime="text/csv",
)
