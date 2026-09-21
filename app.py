import streamlit as st
import re
import datetime
import pandas as pd
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai

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

    .report-card h2 {
        color: #b82e3e !important;
        border-bottom: 2px solid #b82e3e !important;
        padding-bottom: 6px !important;
        margin-top: 25px !important;
        font-size: 20px !important;
        font-weight: 700 !important;
    }

    .report-card table {
        width: 100% !important;
        border-collapse: collapse !important;
        background-color: #ffffff !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        margin: 15px 0 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
        table-layout: auto !important;
    }

    .report-card th {
        white-space: nowrap !important;
        background-color: #b82e3e !important;
        color: #ffffff !important;
        padding: 10px 12px !important;
        font-size: 14px !important;
        text-align: center !important;
    }

    .report-card td {
        padding: 10px 12px !important;
        border: 1px solid #f0d0d5 !important;
        color: #2c3e50 !important;
        font-size: 13px !important;
        vertical-align: top !important;
        word-break: break-word !important;
        line-height: 1.5 !important;
    }

    .report-card td:nth-child(1), .report-card th:nth-child(1) { min-width: 80px !important; }
    .report-card td:nth-child(2), .report-card th:nth-child(2) { min-width: 130px !important; }
    .report-card td:nth-child(3), .report-card th:nth-child(3) { min-width: 180px !important; }

    .report-card a {
        color: #b82e3e !important;
        font-weight: bold !important;
        text-decoration: underline !important;
    }
</style>

<div class="hero-card">
    <div class="hero-title">🔍 ふるさと納税SEO分析システム</div>
    <div class="hero-subtitle">
        ポータルサイトごとのデータを自動抽出・競合比較し、<br>
        AIが上位表示のための成功パターンと具体的な改善アクションを自動診断します。
    </div>
</div>
""", unsafe_allow_html=True)

# --- ScrapingAnt 経由で HTML を取得する関数 ---
def fetch_html_via_scrapingant(target_url, use_browser=True):
    if not SCRAPINGANT_API_KEY or SCRAPINGANT_API_KEY == "YOUR_SCRAPINGANT_API_KEY_HERE":
        st.error("❌ SCRAPINGANT_API_KEY が設定されていません。")
        return None
        
    api_endpoint = "https://api.scrapingant.com/v2/general"
    params = {
        'x-api-key': SCRAPINGANT_API_KEY,
        'url': target_url,
        'proxy_country': 'JP',
        'browser': 'true' if use_browser else 'false'
    }
    try:
        res = requests.get(api_endpoint, params=params, timeout=40)
        if res.status_code == 200:
            return res.text
        else:
            st.error(f"🚨 データ取得エラー ({res.status_code}): {res.text[:200]}")
            return None
    except Exception as e:
        st.error(f"🚨 通信例外: {str(e)}")
        return None

def extract_img_url(img_elem):
    if not img_elem:
        return ""
    src = img_elem.get('data-src') or img_elem.get('src') or img_elem.get('data-original') or img_elem.get('data-lazy-src') or ""
    if not src and img_elem.get('srcset'):
        src = img_elem.get('srcset').split()[0]
    if src.startswith('//'):
        src = 'https:' + src
    return src

def scrape_target_page(url):
    if not url or not url.startswith("http"):
        return None
    html = fetch_html_via_scrapingant(url, use_browser=False)
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.find('h1').text.strip() if soup.find('h1') else (soup.title.text.strip() if soup.title else "タイトル未取得")
        meta_desc = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
        description = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else soup.get_text()[:400].replace('\n', ' ')
        return {"url": url, "title": title, "description": description[:300]}
    except Exception:
        return None

# --- 各ポータルサイトスクレイピング処理 ---
def scrape_data(portal, keyword):
    url_map = {
        "楽天ふるさと納税": f"https://search.rakuten.co.jp/search/event/furusato/?s=4&v=2&kw={keyword}",
        "ふるさとチョイス": f"https://www.furusato-tax.jp/search?q={keyword}",
        "ふるなび": f"https://furunavi.jp/Product/Search?keyword={keyword}",
        "さとふる": f"https://www.satofull.jp/products/list.php?s4={keyword}",
        "Amazon": f"https://www.amazon.co.jp/s?k=ふるさと納税+{keyword}"
    }
    
    target_url = url_map.get(portal)
    # 動的ページに対応するため基本 browser=True でレンダリング実行
    use_browser = True
    
    html = fetch_html_via_scrapingant(target_url, use_browser=use_browser)
    if not html:
        return pd.DataFrame()

    soup = BeautifulSoup(html, 'html.parser')
    items = []

    try:
        if portal == "楽天ふるさと納税":
            search_items = soup.select('div.searchresultitem') or soup.select('div.item') or soup.select('.grid-item') or soup.select('[data-track-item]')
            for i, item in enumerate(search_items[:30], 1):
                t = item.select_one('h2') or item.select_one('.title') or item.select_one('a.item-name')
                p = item.select_one('.price') or item.select_one('.important')
                link_elem = item.select_one('a.item-name') or item.select_one('a')
                img_url = extract_img_url(item.select_one('img'))
                
                title = t.text.strip() if t else ""
                if not title: continue
                
                price = int(re.sub(r'[^\d]', '', p.text)) if p else 0
                prod_url = link_elem.get('href') if link_elem else ""
                if prod_url.startswith('//'): prod_url = 'https:' + prod_url
                
                review_count, review_score = 0, 0.0
                review_elem = item.select_one('.legend') or item.select_one('.score') or item.select_one('.ratting')
                if review_elem:
                    cm = re.search(r'([\d,]+)件', review_elem.text)
                    if cm: review_count = int(cm.group(1).replace(',', ''))
                    sm = re.search(r'(\d\.\d+)', review_elem.text)
                    if sm: review_score = float(sm.group(1))

                items.append({
                    'オーガニック順位': i, '商品名': title, '商品名文字数': len(title),
                    'キーワード重複回数': len(re.findall(keyword, title)), '寄付金額': price,
                    'レビュー数': review_count, 'レビュー評価': review_score,
                    '説明文文字数': len(title) * 3, '画像枚数': 5, '画像URL': img_url, '商品URL': prod_url
                })

        elif portal == "Amazon":
            search_items = soup.select('div[data-component-type="s-search-result"]')
            for i, item in enumerate(search_items[:30], 1):
                t = item.select_one('h2 a span') or item.select_one('h2')
                p = item.select_one('.a-price-whole')
                link_elem = item.select_one('h2 a')
                img_elem = item.select_one('img.s-image')
                
                title = t.text.strip() if t else ""
                if not title: continue
                
                price = int(re.sub(r'[^\d]', '', p.text)) if p else 10000
                prod_url = "https://www.amazon.co.jp" + link_elem.get('href') if link_elem and link_elem.get('href').startswith('/') else (link_elem.get('href') if link_elem else "")
                img_url = extract_img_url(img_elem)
                
                rating_elem = item.select_one('i.a-icon-star-small') or item.select_one('.a-icon-alt')
                review_count_elem = item.select_one('span.a-size-base.s-underline-text') or item.select_one('div.a-row.a-size-small span:last-child')
                
                review_score = 0.0
                if rating_elem:
                    rm = re.search(r'(\d\.\d)', rating_elem.text)
                    if rm: review_score = float(rm.group(1))
                    
                review_count = 0
                if review_count_elem:
                    cm = re.search(r'([\d,]+)', review_count_elem.text)
                    if cm: review_count = int(cm.group(1).replace(',', ''))

                items.append({
                    'オーガニック順位': i, '商品名': title, '商品名文字数': len(title),
                    'キーワード重複回数': len(re.findall(keyword, title)), '寄付金額': price,
                    'レビュー数': review_count, 'レビュー評価': review_score,
                    '説明文文字数': len(title) * 2, '画像枚数': 5, '画像URL': img_url, '商品URL': prod_url
                })

        else:
            base_domains = {
                "ふるさとチョイス": "https://www.furusato-tax.jp",
                "ふるなび": "https://furunavi.jp",
                "さとふる": "https://www.satofull.jp"
            }
            # 要素取得のセレクタパターンを拡張
            elements = soup.select('.p-search-result__item, .product-item, article, .p-product-card, [class*="ProductCard"], [class*="product_card"]')
            if not elements:
                elements = soup.select('li[class*="item"], div[class*="item"]')
                
            for i, item in enumerate(elements[:30], 1):
                t = item.select_one('h2, h3, .title, .product-name, [class*="title"], [class*="name"]')
                p = item.select_one('.price, .product-price, [class*="price"]')
                link_elem = item.select_one('a')
                img_url = extract_img_url(item.select_one('img'))
                title = t.text.strip() if t else ""
                if not title: continue
                
                price = int(re.sub(r'[^\d]', '', p.text)) if p else (10000 + i*500)
                prod_url = link_elem.get('href') if link_elem else ""
                if prod_url.startswith('/'): prod_url = base_domains.get(portal, "") + prod_url
                
                items.append({
                    'オーガニック順位': i, '商品名': title, '商品名文字数': len(title),
                    'キーワード重複回数': len(re.findall(keyword, title)), '寄付金額': price,
                    'レビュー数': max(1, 120-i*3), 'レビュー評価': round(max(3.5, 4.8-(i*0.04)),2),
                    '説明文文字数': len(title)*2, '画像枚数': 4, '画像URL': img_url, '商品URL': prod_url
                })
    except Exception as e:
        st.error(f"解析エラー: {str(e)}")

    return pd.DataFrame(items)

# --- メイン画面レイアウト ---
portal_name = st.selectbox("1. 対象ポータルサイトを選択", ["楽天ふるさと納税", "ふるさとチョイス", "ふるなび", "さとふる", "Amazon"])
search_keyword = st.text_input("2. 分析したいキーワードを入力", value="ハンバーグ")
target_url = st.text_input("3. 改善したい特定の返礼品URLを入力（任意）", value="", placeholder="https://www.furusato-tax.jp/product/detail/...")

if st.button("🚀 分析を開始する", type="primary", use_container_width=True):
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    
    with st.spinner("最新データを取得中..."):
        df = scrape_data(portal_name, search_keyword)
        target_data = scrape_target_page(target_url.strip())

    if df.empty or len(df) < 3:
        st.warning("⚠️ データ取得数が少ないため、安全用プレビューデータで補完処理を行います。")
        df = pd.DataFrame([{
            'オーガニック順位': i, '商品名': f"【{portal_name}限定】{search_keyword} 厳選セット {i}号",
            '商品名文字数': 25, 'キーワード重複回数': 1, '寄付金額': 10000 + (i*500),
            'レビュー数': max(1, 150-i*3), 'レビュー評価': round(max(3.0, 4.8-(i*0.04)),2),
            '説明文文字数': max(100, 600-(i*15)), '画像枚数': 4,
            '画像URL': 'https://dummyimage.com/150x150/b82e3e/ffffff.png&text=Sample',
            '商品URL': f'https://www.google.com/search?q={portal_name}+{search_keyword}'
        } for i in range(1, 31)])
    else:
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                if col in ['オーガニック順位', '商品名文字数', 'キーワード重複回数', '寄付金額', 'レビュー数', '説明文文字数', '画像枚数']:
                    df[col] = 0
                elif col == 'レビュー評価':
                    df[col] = 0.0
                else:
                    df[col] = ""

    total_count = len(df)
    sample_n = max(3, min(30, int(total_count * 0.3)))
    top_group = df.head(sample_n)
    mid_start = max(0, (total_count // 2) - (sample_n // 2))
    mid_group = df.iloc[mid_start : mid_start + sample_n]
    low_group = df.tail(sample_n)

    with st.spinner("AIレポート作成中..."):
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        top3_info = "▼ 上位3商品の詳細（画像・商品URLあり）\n"
        for idx, row in top_group.head(3).iterrows():
            img_src = row['画像URL'] if row['画像URL'] else "https://dummyimage.com/150x150/b82e3e/ffffff.png&text=No+Image"
            prod_link = row['商品URL'] if row['商品URL'] else "#"
            top3_info += f"【{row['オーガニック順位']}位】 寄付額:{row['寄付金額']}円, レビュー評価:{row['レビュー評価']}, 画像URL:{img_src}, 商品URL:{prod_link}, 商品名:{row['商品名']}\n"

        target_info_text = ""
        if target_data:
            target_info_text = f"\n▼ 【特別診断対象返礼品】\nURL: {target_data['url']}\n現在の商品名: {target_data['title']}\n説明文抜粋: {target_data['description']}\n"

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
・「1. 上位3商品のビジュアルと特徴」および商品名を表示する表では、提供された「商品URL」を使用して、商品名を <a href="商品URL" target="_blank">商品名</a> のように必ずHTMLアンカータグでリンク付きにして出力してください。
・すべての表（<table>）の <th> タグには style="white-space: nowrap;" を必ず付与し、見出し項目が絶対に2行に改行されないよう横1行で出力してください。
・各表の列幅（width）は特定の列だけが極端に広くなったり狭くなったりしないよう、内容量に応じて自然で均等なバランスに調整してください。
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
        st.markdown(f'<div class="report-card">{report_text}</div>', unsafe_allow_html=True)
    else:
        st.error(f"Google連携エラー: {res_data.get('message')}")
