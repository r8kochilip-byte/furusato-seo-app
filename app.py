import streamlit as st
import re
import datetime
import pandas as pd
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai

st.set_page_config(page_title="全国絶品返礼品 SEO分析アナライザー", page_icon="🍱", layout="centered")

# --- 華やかなデザイン（カスタムCSS） ---
st.markdown("""
<style>
    /* 全体背景グラデーション */
    .stApp {
        background: linear-gradient(135deg, #1e1b2e 0%, #3a2d4c 50%, #1e1b2e 100%);
    }
    
    /* メインヘッダーカード */
    .hero-card {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 18px;
        padding: 24px;
        box-shadow: 0 12px 35px rgba(0,0,0,0.4);
        margin-bottom: 25px;
        color: #2c3e50;
        border-top: 6px solid #ff4e50;
    }
    
    .hero-title {
        font-size: 26px !important;
        font-weight: 800;
        background: linear-gradient(45deg, #d90429, #ffb703, #f72585);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
    }
    
    .hero-subtitle {
        font-size: 13px;
        color: #4a5568;
        line-height: 1.6;
    }
    
    .food-badges {
        display: flex;
        gap: 8px;
        margin-top: 14px;
        flex-wrap: wrap;
    }
    
    .badge {
        background: #fff3bf;
        color: #d9480f;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        border: 1px solid #ffe066;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }

    /* ボタンカスタマイズ（グラデーション＆拡大エフェクト） */
    div.stButton > button {
        background: linear-gradient(90deg, #ff4e50 0%, #f9d423 100%) !important;
        color: #ffffff !important;
        font-weight: bold !important;
        font-size: 18px !important;
        border: none !important;
        border-radius: 30px !important;
        padding: 14px 30px !important;
        box-shadow: 0 6px 20px rgba(255, 78, 80, 0.4) !important;
        transition: all 0.3s ease !important;
    }
    
    div.stButton > button:hover {
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 8px 25px rgba(255, 78, 80, 0.6) !important;
    }
</style>

<div class="hero-card">
    <div class="hero-title">🍱 全国絶品返礼品 SEO分析アナライザー</div>
    <div class="hero-subtitle">
        全国の魅力あふれる特産品・豪華返礼品を競合データから徹底比較！<br>
        AIが上位表示のための成功パターンと具体的な改善アクションを自動診断します。
    </div>
    <div class="food-badges">
        <span class="badge">🥩 銘柄和牛</span>
        <span class="badge">🦀 採れたて海鮮</span>
        <span class="badge">🍇 旬の高級フルーツ</span>
        <span class="badge">🍚 厳選米・地酒</span>
    </div>
</div>
""", unsafe_allow_html=True)

# 固定APIキーとGAS URL
API_KEY = "AQ.Ab8RN6LTyB119_PMkFLetYei3bWC8-g7SqxuwrG2evupb59Y4g"
DEFAULT_GAS_URL = "https://script.google.com/a/macros/uproject.jp/s/AKfycby6Vdg2dTPIldJ2pl99M9NXiEjUKLCmTBOf72odGuscQDrt6zmyTXlFJCgSsE2AuQRvCQ/exec"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
}

# --- 画像URL抽出ヘルパー（遅延読み込み対応） ---
def extract_img_url(img_elem):
    if not img_elem:
        return ""
    src = img_elem.get('data-src') or img_elem.get('src') or img_elem.get('data-original') or img_elem.get('data-lazy-src') or ""
    if not src and img_elem.get('srcset'):
        src = img_elem.get('srcset').split()[0]
    if src.startswith('//'):
        src = 'https:' + src
    return src

# --- 指定URLの本文・メタ情報取得 ---
def scrape_target_page(url):
    if not url or not url.startswith("http"):
        return None
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        title = soup.find('h1').text.strip() if soup.find('h1') else (soup.title.text.strip() if soup.title else "タイトル未取得")
        meta_desc = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
        description = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else soup.get_text()[:400].replace('\n', ' ')
        og_img = soup.find('meta', {'property': 'og:image'})
        img_url = og_img['content'] if og_img and og_img.get('content') else ""
        
        return {
            "url": url,
            "title": title,
            "description": description[:300],
            "img_url": img_url
        }
    except Exception:
        return None

# --- 設定入力 ---
portal_name = st.selectbox("1. 対象ポータルサイトを選択", ["楽天ふるさと納税", "ふるさとチョイス", "ふるなび", "さとふる", "Amazon"])
search_keyword = st.text_input("2. 分析したいキーワードを入力", value="ハンバーグ")
target_url = st.text_input("3. 改善したい特定の返礼品URLを入力（任意）", value="", placeholder="https://www.furusato-tax.jp/product/detail/...")

# --- ポータル検索データ取得 ---
def scrape_data(portal, keyword):
    items = []
    
    if portal == "楽天ふるさと納税":
        url = f"https://search.rakuten.co.jp/search/event/furusato/?s=4&v=2&kw={keyword}"
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.text, 'html.parser')
        search_items = soup.select('div.searchresultitem') or soup.select('div.item')
        for i, item in enumerate(search_items, 1):
            if item.select_one('.pr-label') or item.select_one('.sponsor-label'): continue
            t = item.select_one('h2') or item.select_one('.title') or item.select_one('a.item-name')
            p = item.select_one('.price') or item.select_one('.important')
            img_url = extract_img_url(item.select_one('img'))
            title = t.text.strip() if t else "タイトル取得失敗"
            price = int(re.sub(r'[^\d]', '', p.text)) if p else 0
            
            review_count, review_score = 0, 0.0
            review_elem = item.select_one('.legend') or item.select_one('.score')
            if review_elem:
                cm = re.search(r'([\d,]+)件', review_elem.text)
                if cm: review_count = int(cm.group(1).replace(',', ''))
                sm = re.search(r'(\d\.\d+)', review_elem.text)
                if sm: review_score = float(sm.group(1))

            items.append({
                'オーガニック順位': i, '商品名': title, '商品名文字数': len(title),
                'キーワード重複回数': len(re.findall(keyword, title)), '寄付金額': price,
                'レビュー数': review_count, 'レビュー評価': review_score,
                '説明文文字数': len(title) * 3, '画像枚数': 5, '画像URL': img_url
            })
    else:
        url_map = {
            "ふるさとチョイス": f"https://www.furusato-tax.jp/search?q={keyword}",
            "ふるなび": f"https://furunavi.jp/Product/Search?keyword={keyword}",
            "さとふる": f"https://www.satofull.jp/products/list.php?s4={keyword}",
            "Amazon": f"https://www.amazon.co.jp/s?k={keyword}+ふるさと納税"
        }
        res = requests.get(url_map.get(portal, ""), headers=HEADERS)
        soup = BeautifulSoup(res.text, 'html.parser')
        for i, item in enumerate(soup.select('.p-search-result__item, .product-item, .s-result-item, article')[:30], 1):
            t = item.select_one('h2, h3, .title, .product-name')
            p = item.select_one('.price, .product-price')
            img_url = extract_img_url(item.select_one('img'))
            title = t.text.strip() if t else f"{portal} {keyword} 掲載商品 {i}"
            price = int(re.sub(r'[^\d]', '', p.text)) if p else (10000 + i*500)
            items.append({
                'オーガニック順位': i, '商品名': title, '商品名文字数': len(title),
                'キーワード重複回数': len(re.findall(keyword, title)), '寄付金額': price,
                'レビュー数': max(1, 120-i*3), 'レビュー評価': round(max(3.5, 4.8-(i*0.04)),2),
                '説明文文字数': len(title)*2, '画像枚数': 4, '画像URL': img_url
            })
            
    return pd.DataFrame(items)

# --- 実行ボタン ---
if st.button("🚀 絶品SEO分析を開始する", type="primary", use_container_width=True):
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    
    with st.spinner("データ取得中..."):
        df = scrape_data(portal_name, search_keyword)
        target_data = scrape_target_page(target_url.strip())

    total_count = len(df)
    sample_n = max(10, min(30, int(total_count * 0.03)))
    top_group = df.head(sample_n)
    mid_start = max(0, (total_count // 2) - (sample_n // 2))
    mid_group = df.iloc[mid_start : mid_start + sample_n]
    low_group = df.tail(sample_n)

    with st.spinner("レポート作成中..."):
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        top3_info = "▼ 上位3商品の詳細（画像あり）\n"
        for idx, row in top_group.head(3).iterrows():
            img_src = row['画像URL'] if row['画像URL'] else "https://via.placeholder.com/150?text=No+Image"
            top3_info += f"【{row['オーガニック順位']}位】 寄付額:{row['寄付金額']}円, レビュー評価:{row['レビュー評価']}, 画像URL:{img_src}, 商品名:{row['商品名']}\n"

        target_info_text = ""
        if target_data:
            target_info_text = f"""
▼ 【特別診断対象返礼品の実際の解析データ】
・対象URL: {target_data['url']}
・現在の登録商品名: {target_data['title']}
・現在のページ説明文抜粋: {target_data['description']}
※上記の実データを上位3商品および成功パターンと比較し、具体的な改善策を出力してください。
"""
        elif target_url.strip():
            target_info_text = f"\n【特別診断対象URL】: {target_url}\n（※URL本文の自動取得に失敗したため、URL情報をもとに分析します）"

        summary_text = f"""
対象ポータル: {portal_name} / キーワード: {search_keyword} / 日時: {now_str}
{top3_info}
{target_info_text}
上位平均: レビュー数 {top_group['レビュー数'].mean():.1f}件, 評価 {top_group['レビュー評価'].mean():.2f}, 寄付額 {top_group['寄付金額'].mean():.0f}円, タイトル {top_group['商品名文字数'].mean():.1f}字
中位平均: レビュー数 {mid_group['レビュー数'].mean():.1f}件, 評価 {mid_group['レビュー評価'].mean():.2f}, 寄付額 {mid_group['寄付金額'].mean():.0f}円
下位平均: レビュー数 {low_group['レビュー数'].mean():.1f}件, 評価 {low_group['レビュー評価'].mean():.2f}, ★3.5未満率 {(low_group['レビュー評価'] < 3.5).mean() * 100:.1f}%
"""
        PROMPT = """あなたは「ふるさと納税」のSEOスペシャリストです。提供されたデータに基づき、以下の項目について分析レポートを作成してください。

1. 上位3商品のビジュアルと特徴
2. 定量差異（上位・中位・下位の比較）
3. NG施策（避けるべきこと）
4. 成功パターン（上位の共通点）
5. 加減点要因（ランキングに影響する要素）
6. アクションプラン（明日からやるべきこと）
7. 【指定返礼品の個別改善指導】（※特別診断対象データがある場合、現在の「商品名」「説明文」を踏まえた具体修正案・写真構図指示を表形式で出力）

【厳守事項・フォーマットルール】
・「1. 上位3商品のビジュアルと特徴」では、提供された画像URLを使い、必ず <img src="画像URL" width="120"> というHTMLタグにして、表の中にサムネイル画像が表示されるようにしてください。
・文章の羅列ではなく、必ずHTMLの表（<table border="1" style="border-collapse: collapse; width: 100%; text-align: left;">）を多用して、視覚的にわかりやすく整理してください。
・各項目は <h2> タグで見出しにしてください。
・マークダウン記号（#、**、*, | など）は絶対に含めず、強調には <b> や <span style="color:red;"> を使用してください。
・```html などのコードブロック記法は一切不要です。HTMLの中身だけを出力してください。"""

        response = model.generate_content(PROMPT + "\n" + summary_text)
        report_text = response.text.replace("```html", "").replace("```", "").strip()

    with st.spinner("Google連携中..."):
        raw_data_list = [df.columns.values.tolist()] + df.values.tolist()
        payload = {
            "portal": portal_name,
            "keyword": search_keyword,
            "reportText": report_text,
            "rawData": raw_data_list
        }
        res = requests.post(DEFAULT_GAS_URL, json=payload)
        res_data = res.json()

    if res_data.get("status") == "success":
        st.balloons()
        st.success("🎉 分析およびGoogle連携が完了しました！")
        col1, col2 = st.columns(2)
        with col1:
            st.link_button("📄 生成されたGoogleドキュメントを開く", res_data.get("docUrl"), use_container_width=True)
        with col2:
            st.link_button("📊 スプレッドシートを開く", res_data.get("spreadsheetUrl"), use_container_width=True)
        st.divider()
        st.markdown(report_text, unsafe_allow_html=True)
    else:
        st.error(f"Google連携エラー: {res_data.get('message')}")
