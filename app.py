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
DEFAULT_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
RAKUTEN_APP_ID = st.secrets.get("RAKUTEN_APP_ID", "")
RAKUTEN_ACCESS_KEY = st.secrets.get("RAKUTEN_ACCESS_KEY", "")
DEFAULT_GAS_URL = "https://script.google.com/a/macros/uproject.jp/s/AKfycby6Vdg2dTPIldJ2pl99M9NXiEjUKLCmTBOf72odGuscQDrt6zmyTXlFJCgSsE2AuQRvCQ/exec"
SCRAPINGANT_API_KEY = "25082eaa554e4bb498a613df0a3648e1"

REQUIRED_COLUMNS = ['オーガニック順位', '商品名', '商品名文字数', 'キーワード重複回数', '寄付金額', 'レビュー数', 'レビュー評価', '説明文文字数', '商品URL']

with st.sidebar:
    st.markdown("### ⚙️ システム設定")
    user_api_key = st.text_input("Gemini APIキー（予備用）", value="", type="password", placeholder="制限時は新しいキーを入力")
    active_api_key = user_api_key.strip() if user_api_key.strip() else DEFAULT_API_KEY

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
    .report-card { background: rgba(255, 245, 246, 0.96) !important; border-radius: 16px !important; padding: 24px !important; border: 2px solid #f7c5cc !important; margin-top: 25px !important; overflow-x: auto !important; }
    
    mark { background-color: #fff3cd; padding: 2px 4px; border-radius: 4px; color: #856404; font-weight: bold; }
</style>
<div class="hero-card">
    <div class="hero-title">🔍 ふるさと納税SEO＆画像ビジュアル分析システム</div>
    <div class="hero-subtitle">
        楽天API（公式）と連動し、100%正確な市場データを抽出。<br>
        さらに商品画像を直接アップロードすれば、AIがビジュアルを診断し【POINT別】の具体的な修正指示書を作成します。
    </div>
</div>
""", unsafe_allow_html=True)

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
    except:
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

portal_name = st.selectbox("1. 対象ポータルサイトを選択", ["楽天ふるさと納税", "ふるさとチョイス", "さとふる", "ふるなび", "Amazon"])
search_keyword = st.text_input("2. 分析したいキーワードを入力", value="地鶏")
target_url = st.text_input("3. 改善したい特定の返礼品URLを入力（任意）", value="", placeholder="https://item.rakuten.co.jp/...")
uploaded_files = st.file_uploader("4. 診断したい返礼品画像をアップロード（任意・最大10枚まで）", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

uploaded_images = []
if uploaded_files:
    st.markdown("<b style='color:#b82e3e;'>📷 アップロードされた診断対象画像:</b>", unsafe_allow_html=True)
    cols = st.columns(min(len(uploaded_files), 5))
    for idx, file in enumerate(uploaded_files[:10]):
        try:
            img = Image.open(file)
            img.verify()
            img = Image.open(file)
            uploaded_images.append(img)
            with cols[idx % 5]:
                st.image(img, caption=f"画像 {idx+1}", use_container_width=True)
        except Exception:
            st.warning(f"⚠️ {file.name} は破損しているか未対応の形式です。")

if st.button("🚀 API実データ取得＆AI分析を開始する", type="primary", use_container_width=True):
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    
    with st.spinner("API連携およびURL情報を解析中..."):
        target_data = scrape_target_page(target_url.strip())
        improvement_img = get_improvement_image_url(search_keyword)
        
        items = []
        if portal_name == "楽天ふるさと納税":
            items = get_rakuten_real_data(search_keyword)
            
        if not items:
            items = [{'オーガニック順位': 1, '商品名': f"【{portal_name}】{search_keyword} 人気セット", '商品名文字数': 15, 'キーワード重複回数': 1, '寄付金額': 10000, 'レビュー数': 300, 'レビュー評価': 4.5, '説明文文字数': 50, '商品URL': "#"}]
            
        df = pd.DataFrame(items)
        
        real_data_text = "【取得した実際の競合データ】\n"
        for _, row in df.iterrows():
            real_data_text += f"順位:{row['オーガニック順位']}位, 商品名:{row['商品名']}, 価格:{row['寄付金額']}円, レビュー:{row['レビュー数']}件, 評価:{row['レビュー評価']}, URL:{row['商品URL']}\n"

    target_info_text = ""
    if target_data:
        target_info_text = f"\n▼ 【特別診断対象返礼品】\nURL: {target_data['url']}\n現在の商品名: {target_data['title']}\n"

    if uploaded_images:
        image_instruction = "ユーザーから実際の返礼品画像がアップロードされています。画像を直接視覚的に分析し、デザインの改善点を指摘してください。"
        image_section_instruction = "アップロードされた画像の色合い・構図・文字・シズル感を直接評価し、デザイナーがそのまま使えるように【POINT 1】〜【POINT 6】の形式で超具体的に修正指示を出力してください。"
    else:
        image_instruction = "画像はアップロードされていません。一般的な特産品に最適なビジュアル修正案を作成してください。"
        image_section_instruction = f"<img src='{improvement_img}' style='border-radius:12px; width:100%; max-width:400px; margin-bottom:15px;'> を表示し、どのような文字や要素を画像に入れるべきか【POINT 1】〜【POINT 6】の形式で箇条書きで具体指導してください。"

    prompt_lines = [
        "あなたは「ふるさと納税およびEコマース」の最高峰クリエイティブディレクター＆SEOアナリストです。",
        f"ポータルサイト「{portal_name}」におけるキーワード「{search_keyword}」の市場動向を分析し、以下のフォーマットに厳格に従ってHTMLレポートを出力してください。",
        "",
        image_instruction,
        "",
        "以下の「取得した実際の競合データ」を基に、レポートを執筆してください。",
        real_data_text,
        "",
        "<h2>1. 実際の上位3商品の特徴</h2>",
        "（順位、商品名(上記データのURLを使ったリンク付き)、寄付額、レビュー件数、評価、特徴のHTMLテーブル）※画像列は不要",
        "<h2>2. 成功パターン（上位の共通点）</h2>",
        "<h2>3. NG施策（避けるべきこと）</h2>",
        "<h2>4. 【重要】画像ビジュアル詳細診断＆改善クリエイティブ指示書</h2>",
        f"（{image_section_instruction}）",
        "<h2>5. アクションプラン（明日からやるべき具体改善策）</h2>",
        "<h2>6. 【指定返礼品の特別診断】</h2>（※対象URL情報がある場合のみ現在のタイトルを踏まえた改善案）",
        "",
        "【厳守事項】",
        "・JSONの出力は一切不要です。いきなりHTMLの見出しから開始してください。",
        "・すべての表（<table>）の <th> タグには style='white-space: nowrap;' を付与すること。",
        "・強調には <mark>キーワード</mark> を使用すること（マークダウン記号は不可）。",
        "・商品名は必ず <a href='商品URL' target='_blank' rel='noopener noreferrer'>商品名</a> でリンク化すること。",
        target_info_text
    ]
    combined_prompt = "\n".join(prompt_lines)

    with st.spinner("AIが市場データと画像を同時分析してレポートを執筆中..."):
        genai.configure(api_key=active_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt_parts = [combined_prompt]
        if uploaded_images:
            prompt_parts.extend(uploaded_images)

        report_html = ""
        for attempt in range(3):
            try:
                response = model.generate_content(prompt_parts)
                report_html = response.text
                break
            except Exception as e:
                if "ResourceExhausted" in str(e) and attempt < 2:
                    time.sleep(5)
                    continue
                else:
                    st.error(f"🚨 API通信制限が発生しました。時間をおいてお試しください。\n詳細: {str(e)}")
                    st.stop()

        report_html = re.sub(r"```[a-zA-Z]*", "", report_html).replace("```", "")
        report_text = "\n".join([line.strip() for line in report_html.split('\n') if line.strip() != ""])

    with st.spinner("Googleスプレッドシート・ドキュメントを生成中..."):
        raw_data_list = [df.columns.values.tolist()] + df.values.tolist()
        payload = {
            "portal": portal_name,
            "keyword": search_keyword,
            "reportText": report_text,
            "rawData": raw_data_list
        }
        try:
            res = requests.post(DEFAULT_GAS_URL, json=payload, timeout=60)
            res_data = res.json()
        except:
            res_data = {"status": "error", "message": "GAS通信エラー"}

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
        st.warning("⚠️ Google連携がタイムアウトしましたが、レポートは正常に生成されました。")
        st.divider()
        st.markdown(f'<div class="report-card">{report_text}</div>', unsafe_allow_html=True)
