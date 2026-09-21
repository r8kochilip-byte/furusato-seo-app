import streamlit as st
import re
import datetime
import pandas as pd
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai
import time

st.set_page_config(page_title="ふるさと納税SEO分析システム", page_icon="🔍", layout="centered")

# === ScrapingAnt API Token ===
SCRAPINGANT_API_KEY = "25082eaa554e4bb498a613df0a3648e1"

# 固定Gemini APIキーとGAS URL
API_KEY = "AQ.Ab8RN6LTyB119_PMkFLetYei3bWC8-g7SqxuwrG2evupb59Y4g"
DEFAULT_GAS_URL = "https://script.google.com/a/macros/uproject.jp/s/AKfycby6Vdg2dTPIldJ2pl99M9NXiEjUKLCmTBOf72odGuscQDrt6zmyTXlFJCgSsE2AuQRvCQ/exec"

REQUIRED_COLUMNS = ['オーガニック順位', '商品名', '商品名文字数', 'キーワード重複回数', '寄付金額', 'レビュー数', 'レビュー評価', '説明文文字数', '画像枚数', '画像URL', '商品URL']

# --- デザイン設定 ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap');

    html, body, [class*="st-"], .stApp, .hero-title, .hero-subtitle, label, button, input, div, p, span {
        font-family: 'Zen Kaku Gothic New', sans-serif !important;
    }

    .stApp {
        background-color: #fcece9;
        background-image: 
            linear-gradient(rgba(252, 236, 233, 0.88), rgba(252, 236, 233, 0.88)),
            url("https://images.unsplash.com/photo-1610832958506-aa56368176cf?auto=format&fit=crop&w=1200&q=80");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        color: #2c3e50;
    }

    .hero-card {
        background: #ffffff;
        border-radius: 18px;
        padding: 24px;
        box-shadow: 0 10px 30px rgba(184, 46, 62, 0.12);
        margin-bottom: 25px;
        color: #2c3e50;
        border: 2px solid #f7d5cd;
        border-top: 6px solid #b82e3e;
    }

    .hero-title { font-size: 26px !important; font-weight: 700; color: #b82e3e; margin-bottom: 6px; }
    .hero-subtitle { font-size: 14px; color: #5a4b4e; line-height: 1.6; font-weight: 500; }

    .stSelectbox label, .stTextInput label { color: #2c3e50 !important; font-weight: 700 !important; font-size: 15px !important; }

    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
        background-color: #b82e3e !important;
        border-radius: 10px !important;
        border: none !important;
    }
    
    div[data-baseweb="select"] span, input { color: #ffffff !important; font-weight: 500 !important; }
    input::placeholder { color: #f7cfc8 !important; }

    div.stButton > button {
        background: linear-gradient(90deg, #b82e3e 0%, #c83246 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 18px !important;
        border: none !important;
        border-radius: 30px !important;
        padding: 14px 30px !important;
        box-shadow: 0 6px 20px rgba(184, 46, 62, 0.35) !important;
        transition: all 0.3s ease !important;
    }

    div.stButton > button:hover {
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 8px 25px rgba(184, 46, 62, 0.55) !important;
    }

    .report-card {
        background: rgba(255, 245, 246, 0.96) !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 10px 30px rgba(184, 46, 62, 0.15) !important;
        border: 2px solid #f7c5cc !important;
        margin-top: 25px !important;
        color: #2c3e50 !important;
        overflow-x: auto !important;
    }
</style>

<div class="hero-card">
    <div class="hero-title">🔍 ふるさと納税SEO分析システム（デバッグ診断機能付き）</div>
    <div class="hero-subtitle">
        リアルタイム通信ログを表示してデータ取得状況を診断します。
    </div>
</div>
""", unsafe_allow_html=True)

def fetch_html_debug(target_url):
    api_endpoint = "https://api.scrapingant.com/v2/general"
    params = {
        'x-api-key': SCRAPINGANT_API_KEY,
        'url': target_url,
        'proxy_country': 'JP',
        'browser': 'true'
    }
    try:
        st.write(f"📡 接続試行中: {target_url}")
        res = requests.get(api_endpoint, params=params, timeout=50)
        st.write(f"📊 ステータスコード: {res.status_code} / 受信サイズ: {len(res.text)} bytes")
        if res.status_code == 200:
            return res.text
        else:
            st.error(f"❌ ScrapingAnt エラー ({res.status_code}): {res.text[:300]}")
            return None
    except Exception as e:
        st.error(f"❌ 通信例外: {str(e)}")
        return None

def scrape_data(portal, keyword):
    url_map = {
        "楽天ふるさと納税": f"https://search.rakuten.co.jp/search/mall/ふるさと納税+{keyword}/",
        "ふるさとチョイス": f"https://www.furusato-tax.jp/search?q={keyword}",
        "ふるなび": f"https://furunavi.jp/Product/Search?keyword={keyword}",
        "さとふる": f"https://www.satofull.jp/products/list.php?s4={keyword}",
        "Amazon": f"https://www.amazon.co.jp/s?k=ふるさと納税+{keyword}"
    }
    
    target_url = url_map.get(portal)
    html = fetch_html_debug(target_url)
    
    if not html:
        return pd.DataFrame()

    soup = BeautifulSoup(html, 'html.parser')
    
    # 受け取ったタイトルのプレビューを表示（デバッグ用）
    page_title = soup.title.text.strip() if soup.title else "タイトルなし"
    st.info(f"📄 取得ページのタイトル: 「{page_title}」")

    items = []
    # 広い要素で抽出をテスト
    elements = soup.select('div[class*="item"], div[class*="card"], article, li')
    st.write(f"🔍 検出された要素数: {len(elements)} 件")

    for i, item in enumerate(elements[:30], 1):
        t = item.select_one('h2, h3, a, [class*="title"]')
        p = item.select_one('[class*="price"]')
        img = item.select_one('img')
        
        title = t.text.strip() if t else ""
        if len(title) < 6: continue
        
        price = int(re.sub(r'[^\d]', '', p.text)) if p and re.sub(r'[^\d]', '', p.text) else 10000
        img_url = img.get('src') if img else ""
        
        items.append({
            'オーガニック順位': i, '商品名': title[:40], '商品名文字数': len(title),
            'キーワード重複回数': 1, '寄付金額': price, 'レビュー数': 50, 'レビュー評価': 4.5,
            '説明文文字数': 100, '画像枚数': 4, '画像URL': img_url, '商品URL': target_url
        })

    return pd.DataFrame(items)

# --- メイン画面 ---
portal_name = st.selectbox("1. 対象ポータルサイトを選択", ["楽天ふるさと納税", "ふるさとチョイス", "ふるなび", "さとふる", "Amazon"])
search_keyword = st.text_input("2. 分析したいキーワードを入力", value="ハンバーグ")

if st.button("🚀 診断テストを実行する", type="primary", use_container_width=True):
    with st.spinner("通信テスト中..."):
        df = scrape_data(portal_name, search_keyword)

    if df.empty:
        st.error("🚨 データを取得できませんでした。ScrapingAntがサイト側でブロックされている可能性があります。")
    else:
        st.success(f"🎉 SUCCESS! {len(df)} 件のリアルデータを検出しました！")
        st.dataframe(df[['オーガニック順位', '商品名', '寄付金額']])
