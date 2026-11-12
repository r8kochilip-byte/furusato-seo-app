import streamlit as st
import re
import datetime
import pandas as pd
import json
import time
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai
from PIL import Image

st.set_page_config(page_title="ふるさと納税SEO分析システム", page_icon="🔍", layout="centered")

# --- APIキー設定（StreamlitのSecretsから安全に読み込む） ---
active_api_key = st.secrets.get("GEMINI_API_KEY", "")
RAKUTEN_APP_ID = st.secrets.get("RAKUTEN_APP_ID", "")
RAKUTEN_ACCESS_KEY = st.secrets.get("RAKUTEN_ACCESS_KEY", "")
DEFAULT_GAS_URL = "https://script.google.com/a/macros/uproject.jp/s/AKfycby6Vdg2dTPIldJ2pl99M9NXiEjUKLCmTBOf72odGuscQDrt6zmyTXlFJCgSsE2AuQRvCQ/exec"
SCRAPINGANT_API_KEY = "25082eaa554e4bb498a613df0a3648e1"

# --- デザイン・スタイル設定 ---
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
        color: #b82e3e !important;
        font-weight: 700 !important;
        font-size: 16px !important;
    }

    div.stButton > button {
        background: linear-gradient(90deg, #b82e3e 0%, #c83246 100%) !important; color: #ffffff !important; font-weight: 700 !important; font-size: 18px !important; border: none !important; border-radius: 30px !important; padding: 14px 30px !important; box-shadow: 0 6px 20px rgba(184, 46, 62, 0.35) !important; transition: all 0.3s ease !important;
    }
    div.stButton > button:hover { transform: translateY(-2px) scale(1.02); box-shadow: 0 8px 25px rgba(184, 46, 62, 0.55) !important; }
    .report-card { background: #ffffff !important; border-radius: 16px !important; padding: 24px !important; border: 2px solid #f7c5cc !important; margin-top: 15px !important; overflow-x: auto !important; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
    .report-card h2 { color: #b82e3e; border-bottom: 2px solid #fcece9; padding-bottom: 8px; margin-top: 24px; font-size: 20px; }
    .report-card h2:first-child { margin-top: 0; }
    
    mark { background-color: #fff3cd; padding: 2px 6px; border-radius: 4px; color: #856404; font-weight: bold; }
</style>
<div class="hero-card">
    <div class="hero-title">🔍 ふるさと納税SEO分析システム</div>
    <div class="hero-subtitle">
        AIが検索し、ふるさと納税の返礼品に関して具体的な修正案を作成します。
    </div>
</div>
""", unsafe_allow_html=True)

# --- 各種機能関数 ---
def scrape_target_page(url):
    if not url or not url.startswith("http"):
        return None
    api_endpoint = "https://api.scrapingant.com/v2/general"
    params = {'x-api-key': SCRAPINGANT_API_KEY, 'url': url, 'proxy_country': 'JP', 'browser': 'false'}
    try:
        res = requests.get(api_endpoint, params=params, timeout=15)
        if res.status_code == 200:
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, 'html.parser')
            title = soup.title.text.strip() if soup.title else "タイトル取得不可"
            meta_desc = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
            desc = meta_desc.get('content', '').strip() if meta_desc else ""
            return {"url": url, "title": title, "description": desc[:150]}
    except Exception:
        pass
    return {"url": url, "title": "指定の返礼品", "description": "詳細はリンク先を参照"}

def get_improvement_image_url(keyword):
    if any(k in keyword for k in ["肉", "ハンバーグ", "牛", "豚", "鶏"]):
        return "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=600&q=80"
    elif any(k in keyword for k in ["海鮮", "蟹", "ホタテ", "いくら", "魚"]):
        return "https://images.unsplash.com/photo-1611143669185-af224c5e3252?auto=format&fit=crop&w=600&q=80"
    else:
        return "https://images.unsplash.com/photo-1610832958506-aa56368176cf?auto=format&fit=crop&w=600&q=80"

def get_rakuten_real_data(keyword):
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {
        "applicationId": RAKUTEN_APP_ID.replace("-", "") if "-" in RAKUTEN_APP_ID else "1019079537947262807",
        "keyword": f"ふるさと納税 {keyword}",
        "hits": 5,
        "sort": "-reviewCount"
    }
    headers = {
        "Authorization": f"Bearer {RAKUTEN_ACCESS_KEY}",
        "x-api-key": RAKUTEN_APP_ID
    }
    items = []
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for i, item_data in enumerate(data.get("Items", [])):
                item = item_data["Item"]
                t = item.get("itemName", "")
                items.append({
                    'オーガニック順位': i + 1,
                    '商品名': t,
                    '商品名文字数': len(t),
                    'キーワード重複回数': t.count(keyword),
                    '寄付金額': item.get("itemPrice", 0),
                    'レビュー数': item.get("reviewCount", 0),
                    'レビュー評価': item.get("reviewAverage", 0.0),
                    '説明文文字数': len(item.get("itemCaption", t)),
                    '商品URL': item.get("itemUrl", "#")
                })
    except Exception:
        pass
    return items

# --- 最新モデルを優先しつつ、404エラー時に自動切替する候補リストを作成 ---
def get_candidate_models():
    candidates = ['models/gemini-3.8-flash', 'models/gemini-3.8-pro']
    try:
        available_models = [
            m.name for m in genai.list_models()
            if 'generateContent' in m.supported_generation_methods
        ]
        # 新しいバージョン（数字が大きい順）に並べ替え
        available_models.sort(reverse=True)
        for m in available_models:
            if 'flash' in m.lower() or 'pro' in m.lower():
                if m not in candidates and '2.5' not in m and '1.5' not in m:
                    candidates.append(m)
        for m in available_models:
            if m not in candidates:
                candidates.append(m)
    except Exception:
        pass
    return candidates

# --- 入力フォームエリア ---
with st.container():
    portal_name = st.selectbox("1. 対象ポータルサイトを選択", ["楽天ふるさと納税", "ふるさとチョイス", "さとふる", "ふるなび", "Amazon"])
    search_keyword = st.text_input("2. 分析したいキーワードを入力", value="地鶏")
    target_url = st.text_input("3. 改善したい特定の返礼品URLを入力（任意）", value="", placeholder="https://item.rakuten.co.jp/...")
    uploaded_files = st.file_uploader("4. 診断したい返礼品画像をアップロード（任意・最大10枚まで）", type=["jpg", "jpeg", "
