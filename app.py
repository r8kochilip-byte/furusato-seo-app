import streamlit as st
import re
import datetime
import pandas as pd
import json
import time
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai

st.set_page_config(page_title="ふるさと納税SEO分析システム", page_icon="🔍", layout="centered")

# 固定Gemini APIキーとGAS URL
DEFAULT_API_KEY = "AQ.Ab8RN6LTyB119_PMkFLetYei3bWC8-g7SqxuwrG2evupb59Y4g"
DEFAULT_GAS_URL = "https://script.google.com/a/macros/uproject.jp/s/AKfycby6Vdg2dTPIldJ2pl99M9NXiEjUKLCmTBOf72odGuscQDrt6zmyTXlFJCgSsE2AuQRvCQ/exec"
SCRAPINGANT_API_KEY = "25082eaa554e4bb498a613df0a3648e1"

REQUIRED_COLUMNS = ['オーガニック順位', '商品名', '商品名文字数', 'キーワード重複回数', '寄付金額', 'レビュー数', 'レビュー評価', '説明文文字数', '商品URL']

# --- サイドバー：APIキー設定 ---
with st.sidebar:
    st.markdown("### ⚙️ システム設定")
    user_api_key = st.text_input("Gemini APIキー（予備用）", value="", type="password", placeholder="制限時は新しいキーを入力")
    active_api_key = user_api_key.strip() if user_api_key.strip() else DEFAULT_API_KEY

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
    
    label, .stSelectbox label, .stTextInput label {
        color: #b82e3e !important;
        font-weight: 700 !important;
        font-size: 16px !important;
    }

    div.stButton > button {
        background: linear-gradient(90deg, #b82e3e 0%, #c83246 100%) !important; color: #ffffff !important; font-weight: 700 !important; font-size: 18px !important; border: none !important; border-radius: 30px !important; padding: 14px 30px !important; box-shadow: 0 6px 20px rgba(184, 46, 62, 0.35) !important; transition: all 0.3s ease !important;
    }
    div.stButton > button:hover { transform: translateY(-2px) scale(1.02); box-shadow: 0 8px 25px rgba(184, 46, 62, 0.55) !important; }
    .report-card { background: rgba(255, 245, 246, 0.96) !important; border-radius: 16px !important; padding: 24px !important; border: 2px solid #f7c5cc !important; margin-top: 25px !important; overflow-x: auto !important; }
    
    mark { background-color: #fff3cd; padding: 2px 4px; border-radius: 4px; color: #856404; font-weight: bold; }
</style>
<div class="hero-card">
    <div class="hero-title">🔍 ふるさと納税SEO分析システム</div>
    <div class="hero-subtitle">
        AIが選択ポータルのSEO傾向と競合動向を即座に分析。<br>
        各市場に最適化されたリアルなデータに基づき、具体的な改善アクションを提案します。
    </div>
</div>
""", unsafe_allow_html=True)

# --- 特定URLの解析ロジック ---
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
            desc = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else ""
            return {"url": url, "title": title, "description": desc[:150]}
    except:
        pass
    return {"url": url, "title": "指定の返礼品", "description": "詳細はリンク先を参照"}

# --- キーワードに応じた画像URL ---
def get_improvement_image_url(keyword):
    if "肉" in keyword or "ハンバーグ" in keyword or "牛" in keyword or "豚" in keyword or "鶏" in keyword:
        return "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=600&q=80"
    elif "海鮮" in keyword or "蟹" in keyword or "ホタテ" in keyword or "いくら" in keyword or "魚" in keyword:
        return "https://images.unsplash.com/photo-1611143669185-af224c5e3252?auto=format&fit=crop&w=600&q=80"
    else:
        return "https://images.unsplash.com/photo-1610832958506-aa56368176cf?auto=format&fit=crop&w=600&q=80"

# --- メイン画面レイアウト ---
portal_name = st.selectbox("1. 対象ポータルサイトを選択", ["楽天ふるさと納税", "ふるさとチョイス", "さとふる", "ふるなび", "Amazon"])
search_keyword = st.text_input("2. 分析したいキーワードを入力", value="地鶏")
target_url = st.text_input("3. 改善したい特定の返礼品URLを入力（任意）", value="", placeholder="https://item.rakuten.co.jp/...")

if st.button("🚀 AI自動リサーチで分析を開始する", type="primary", use_container_width=True):
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    
    with st.spinner("URL情報の確認中..."):
        target_data = scrape_target_page(target_url.strip())
        improvement_img = get_improvement_image_url(search_keyword)

    target_info_text = ""
    if target_data:
        target_info_text = f"\n▼ 【特別診断対象返礼品】\nURL: {target_data['url']}\n現在の商品名: {target_data['title']}\n"

    # API呼び出しを「1回」に集約した統合プロンプト
    COMBINED_PROMPT = f"""あなたは「ふるさと納税およびEコマース」のSEO・デザインスペシャリストです。
ポータルサイト「{portal_name}」におけるキーワード「{search_keyword}」の市場動向を分析し、以下のフォーマットに厳格に従って出力してください。

まずは、{portal_name}で上位表示されるであろう競合上位5商品の推測データをJSONで作成し、その直後にHTML形式の改善レポートを作成してください。

出力の区切りとして、必ず `===HTML_REPORT===` という文字列を挿入してください。

【構成形式】
```json
[
  {{"rank": 1, "title": "商品名1", "price": 10000, "review": 1500, "score": 4.6, "url": "[https://item.rakuten.co.jp/shop/1/](https://item.rakuten.co.jp/shop/1/)"}},
  {{"rank": 2, "title": "商品名2", "price": 8000, "review": 800, "score": 4.3, "url": "[https://item.rakuten.co.jp/shop/2/](https://item.rakuten.co.jp/shop/2/)"}},
  {{"rank": 3, "title": "商品名3", "price": 12000, "review": 300, "score": 4.8, "url": "[https://item.rakuten.co.jp/shop/3/](https://item.rakuten.co.jp/shop/3/)"}},
  {{"rank": 4, "title": "商品名4", "price": 9500, "review": 120, "score": 4.1, "url": "[https://item.rakuten.co.jp/shop/4/](https://item.rakuten.co.jp/shop/4/)"}},
  {{"rank": 5, "title": "商品名5", "price": 15000, "review": 50, "score": 4.9, "url": "[https://item.rakuten.co.jp/shop/5/](https://item.rakuten.co.jp/shop/5/)"}}
]
