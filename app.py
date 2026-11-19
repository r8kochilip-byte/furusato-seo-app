import streamlit as st
import re
import datetime
import urllib.parse
import pandas as pd
import time
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai
from PIL import Image

st.set_page_config(page_title="ふるさと納税SEO分析システム", page_icon="🔍", layout="centered")

# --- APIキー設定（Secretsから読み込み） ---
active_api_key = st.secrets.get("GEMINI_API_KEY", "")
RAKUTEN_APP_ID = st.secrets.get("RAKUTEN_APP_ID", "").strip()
RAKUTEN_ACCESS_KEY = st.secrets.get("RAKUTEN_ACCESS_KEY", "").strip()
DEFAULT_GAS_URL = "https://script.google.com/a/macros/uproject.jp/s/AKfycby6Vdg2dTPIldJ2pl99M9NXiEjUKLCmTBOf72odGuscQDrt6zmyTXlFJCgSsE2AuQRvCQ/exec"
SCRAPINGANT_API_KEY = "25082eaa554e4bb498a613df0a3648e1"

# --- デザイン設定 ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap');
    html, body, [class*="st-"], .stApp, .hero-title, .hero-subtitle, label, button, input, div, p, span {
        font-family: 'Zen Kaku Gothic New', sans-serif !important;
    }
    .stApp {
        background-color: #fcece9;
        background-image: linear-gradient(rgba(252, 236, 233, 0.88), rgba(252, 236, 233, 0.88)), url("https://images.unsplash.com/photo-1610832958506-aa56368176cf?auto=format&fit=crop&w=1200&q=80");
        background-size: cover; background-position: center; background-attachment: fixed; color: #2c3e50;
    }
    .hero-card {
        background: #ffffff; border-radius: 18px; padding: 24px; box-shadow: 0 10px 30px rgba(184, 46, 62, 0.12); margin-bottom: 25px; border: 2px solid #f7d5cd; border-top: 6px solid #b82e3e;
    }
    .hero-title { font-size: 26px !important; font-weight: 700; color: #b82e3e; margin-bottom: 6px; }
    .hero-subtitle { font-size: 14px; color: #5a4b4e; line-height: 1.6; font-weight: 500; }
    label, .stSelectbox label, .stTextInput label, div[data-testid="stFileUploader"] label, .stFileUploader label {
        color: #b82e3e !important; font-weight: 700 !important; font-size: 16px !important;
    }
    div.stButton > button {
        background: linear-gradient(90deg, #b82e3e 0%, #c83246 100%) !important; color: #ffffff !important; font-weight: 700 !important; font-size: 18px !important; border: none !important; border-radius: 30px !important; padding: 14px 30px !important; box-shadow: 0 6px 20px rgba(184, 46, 62, 0.35) !important;
    }
    .report-card {
        background: #ffffff !important; border-radius: 16px !important; padding: 24px !important; border: 2px solid #f7c5cc !important; margin-top: 15px !important; overflow-x: auto !important;
    }
    .report-card h2 { color: #b82e3e; border-bottom: 2px solid #fcece9; padding-bottom: 8px; margin-top: 24px; font-size: 20px; }
    .report-card h2:first-child { margin-top: 0; }
    mark { background-color: #fff3cd; padding: 2px 6px; border-radius: 4px; color: #856404; font-weight: bold; }
</style>
<div class="hero-card">
    <div class="hero-title">🔍 ふるさと納税SEO分析システム</div>
    <div class="hero-subtitle">AIが検索し、ふるさと納税の返礼品に関して具体的な修正案を作成します。</div>
</div>
""", unsafe_allow_html=True)

def scrape_target_page(url):
    if not url or not url.startswith("http"):
        return None
    try:
        res = requests.get("https://api.scrapingant.com/v2/general", params={'x-api-key': SCRAPINGANT_API_KEY, 'url': url, 'proxy_country': 'JP', 'browser': 'false'}, timeout=15)
        if res.status_code == 200:
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, 'html.parser')
            title = soup.title.text.strip() if soup.title else "タイトル取得不可"
            meta = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
            desc = meta.get('content', '').strip() if meta else ""
            return {"url": url, "title": title, "description": desc[:150]}
    except Exception:
        pass
    return {"url": url, "title": "指定の返礼品", "description": "詳細はリンク先を参照"}

def get_improvement_image_url(keyword):
    if any(k in keyword for k in ["肉", "ハンバーグ", "牛", "豚", "鶏"]):
        return "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=600&q=80"
    elif any(k in keyword for k in ["海鮮", "蟹", "ホタテ", "いくら", "魚"]):
        return "https://images.unsplash.com/photo-1611143669185-af224c5e3252?auto=format&fit=crop&w=600&q=80"
    return "https://images.unsplash.com/photo-1610832958506-aa56368176cf?auto=format&fit=crop&w=600&q=80"

def get_rakuten_real_data(keyword):
    items = []
    api_status = "未取得"
    
    # パターン1: 楽天API（新・旧両方の認証形式に対応）
    endpoints = [
        "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601",
        "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    ]
    
    for ep in endpoints:
        if items:
            break
        params = {
            "applicationId": RAKUTEN_APP_ID,
            "accessKey": RAKUTEN_ACCESS_KEY,
            "keyword": f"ふるさと納税 {keyword}",
            "hits": 5,
            "sort": "-reviewCount",
            "format": "json"
        }
        headers = {
            "Authorization": f"Bearer {RAKUTEN_ACCESS_KEY}",
            "Origin": "https://share.streamlit.io",
            "Referer": "https://share.streamlit.io/"
        }
        try:
            res = requests.get(ep, params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for i, item_data in enumerate(data.get("Items", [])):
                    item = item_data.get("Item", item_data)
                    t = item.get("itemName", "")
                    u = item.get("itemUrl", "")
                    if t and u:
                        items.append({
                            'オーガニック順位': i + 1,
                            '商品名': t,
                            '商品名文字数': len(t),
                            'キーワード重複回数': t.count(keyword),
                            '寄付金額': item.get("itemPrice", 0),
                            'レビュー数': item.get("reviewCount", 0),
                            'レビュー評価': item.get("reviewAverage", 0.0),
                            '説明文文字数': len(item.get("itemCaption", t)),
                            '商品URL': u
                        })
                if items:
                    api_status = "楽天APIから実データを取得"
        except Exception:
            pass

    # パターン2: 楽天APIが制限・認証エラーになった場合、楽天ふるさと納税の検索結果ページを直接解析して実URLを取得
    if not items:
        encoded_kw = urllib.parse.quote(f"ふるさと納税 {keyword}")
        rakuten_search_url = f"https://search.rakuten.co.jp/search/mall/{encoded_kw}/"
        try:
            res = requests.get(
                "https://api.scrapingant.com/v2/general",
                params={'x-api-key': SCRAPINGANT_API_KEY, 'url': rakuten_search_url, 'proxy_country': 'JP', 'browser': 'false'},
                timeout=15
            )
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                links = soup.find_all('a', href=re.compile(r'https://item\.rakuten\.co\.jp/[^/]+/[^/]+/'))
                seen_urls = set()
                for a in links:
                    href = a.get('href', '').split('?')[0]
                    title = a.get_text(strip=True)
                    if href not in seen_urls and len(title) > 10 and "ふるさと
