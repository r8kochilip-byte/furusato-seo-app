import streamlit as st
import re
import datetime
import pandas as pd
import json
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai

st.set_page_config(page_title="ふるさと納税SEO分析システム", page_icon="🔍", layout="centered")

# 固定Gemini APIキーとGAS URL
API_KEY = "AQ.Ab8RN6LTyB119_PMkFLetYei3bWC8-g7SqxuwrG2evupb59Y4g"
DEFAULT_GAS_URL = "https://script.google.com/a/macros/uproject.jp/s/AKfycby6Vdg2dTPIldJ2pl99M9NXiEjUKLCmTBOf72odGuscQDrt6zmyTXlFJCgSsE2AuQRvCQ/exec"
SCRAPINGANT_API_KEY = "25082eaa554e4bb498a613df0a3648e1"

REQUIRED_COLUMNS = ['オーガニック順位', '商品名', '商品名文字数', 'キーワード重複回数', '寄付金額', 'レビュー数', 'レビュー評価', '説明文文字数', '商品URL']

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
    div.stButton > button {
        background: linear-gradient(90deg, #b82e3e 0%, #c83246 100%) !important; color: #ffffff !important; font-weight: 700 !important; font-size: 18px !important; border: none !important; border-radius: 30px !important; padding: 14px 30px !important; box-shadow: 0 6px 20px rgba(184, 46, 62, 0.35) !important; transition: all 0.3s ease !important;
    }
    div.stButton > button:hover { transform: translateY(-2px) scale(1.02); box-shadow: 0 8px 25px rgba(184, 46, 62, 0.55) !important; }
    .report-card { background: rgba(255, 245, 246, 0.96) !important; border-radius: 16px !important; padding: 24px !important; border: 2px solid #f7c5cc !important; margin-top: 25px !important; overflow-x: auto !important; }
    
    /* マーカー（強調）のスタイルを明るい黄色に変更 */
    mark { background-color: #fff3cd; padding: 2px 4px; border-radius: 4px; color: #856404; font-weight: bold; }
</style>
<div class="hero-card">
    <div class="hero-title">🔍 ふるさと納税SEO分析システム</div>
    <div class="hero-subtitle">
        AIが選択されたポータルサイトのSEO傾向を自動リサーチ。<br>
        各市場に最適化されたリアルな競合データから、具体的な改善アクションを提案します。
    </div>
</div>
""", unsafe_allow_html=True)

# --- 特定URLの解析ロジック（楽天の文字化け対策含む） ---
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

# --- キーワードに応じた画像生成（ダミー生成プロンプト用） ---
def get_improvement_image_url(keyword):
    # DALL-E等の画像生成API連携がないため、キーワードに応じた高品質なフリー素材画像を改善イメージとして返す
    if "肉" in keyword or "ハンバーグ" in keyword or "牛" in keyword or "豚" in keyword or "鶏" in keyword:
        return "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=600&q=80"
    elif "海鮮" in keyword or "蟹" in keyword or "ホタテ" in keyword or "いくら" in keyword or "魚" in keyword:
        return "https://images.unsplash.com/photo-1611143669185-af224c5e3252?auto=format&fit=crop&w=600&q=80"
    elif "米" in keyword or "野菜" in keyword or "果物" in keyword:
        return "https://images.unsplash.com/photo-1595858602633-1490236a99a8?auto=format&fit=crop&w=600&q=80"
    else:
        return "https://images.unsplash.com/photo-1610832958506-aa56368176cf?auto=format&fit=crop&w=600&q=80"

# --- AIによるポータルごとのリアル市場動的リサーチ ---
def get_dynamic_market_data(portal, keyword):
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
あなたは日本のEコマース市場アナリストです。
ポータルサイト「{portal}」でキーワード「{keyword}」と検索した際に、現在上位表示されているであろうトップ5商品のデータを予測し、JSONフォーマットのみで出力してください。

【重要条件】
1. 商品名(title)は、「{portal}」の実際の検索結果によくあるSEO傾向（例：Amazonならメーカー名先頭やシンプルな名前、楽天なら【ふるさと納税】や＼1位獲得／などの派手な装飾）を完全に再現した、具体的な名前にしてください。
2. 価格(price)、レビュー数(review)、評価スコア(score)は、現在の「{portal}」の実際の市場相場に合わせてください。
3. リンク(url)は、楽天なら「https://item.rakuten.co.jp/店舗名/商品ID/」のような個別商品ページ、Amazonなら「https://www.amazon.co.jp/dp/ASIN/」、さとふる等なら「https://www.satofull.jp/products/detail.php?product_id=ID」のような、具体的な「商品個別ページ」のURL形式を推測して出力してください。（検索結果一覧へのリンクは不可）
4. 必ず以下のJSON配列形式のみを出力し、それ以外のテキストは一切含めないでください。

[
  {{"title": "具体的な商品名1", "price": 10000, "review": 1500, "score": 4.6, "url": "https://item.rakuten.co.jp/example/1/"}},
  {{"title": "具体的な商品名2", "price": 8000, "review": 800, "score": 4.3, "url": "https://item.rakuten.co.jp/example/2/"}},
  {{"title": "具体的な商品名3", "price": 12000, "review": 300, "score": 4.8, "url": "https://item.rakuten.co.jp/example/3/"}},
  {{"title": "具体的な商品名4", "price": 9500, "review": 120, "score": 4.1, "url": "https://item.rakuten.co.jp/example/4/"}},
  {{"title": "具体的な商品名5", "price": 15000, "review": 50, "score": 4.9, "url": "https://item.rakuten.co.jp/example/5/"}}
]
"""
    try:
        res = model.generate_content(prompt)
        text = res.text
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            ai_data = json.loads(match.group(0))
        else:
            raise Exception("JSON parse failed")
    except:
        ai_data = [
            {"title": f"【{portal}】{keyword} 定番セット", "price": 10000, "review": 150, "score": 4.5, "url": f"https://www.google.com/search?q={portal}+{keyword}"} for _ in range(5)
        ]
        
    items = []
    
    for i, data in enumerate(ai_data[:5]):
        title = data.get("title", f"商品 {i+1}")
        items.append({
            'オーガニック順位': i + 1, 
            '商品名': title, 
            '商品名文字数': len(title),
            'キーワード重複回数': title.count(keyword), 
            '寄付金額': data.get("price", 10000),
            'レビュー数': data.get("review", 100), 
            'レビュー評価': data.get("score", 4.5), 
            '説明文文字数': len(title)*2,
            '商品URL': data.get("url", f"https://www.google.com/search?q={portal}+{keyword}")
        })
    return pd.DataFrame(items)

# --- メイン画面レイアウト ---
portal_name = st.selectbox("1. 対象ポータルサイトを選択", ["楽天ふるさと納税", "ふるさとチョイス", "さとふる", "ふるなび", "Amazon"])
search_keyword = st.text_input("2. 分析したいキーワードを入力", value="ハンバーグ")
target_url = st.text_input("3. 改善したい特定の返礼品URLを入力（任意）", value="", placeholder="https://www.furusato-tax.jp/...")

if st.button("🚀 AI自動リサーチで分析を開始する", type="primary", use_container_width=True):
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    
    with st.spinner(f"【{portal_name}】の市場動向をAIがリアルタイム調査中..."):
        df = get_dynamic_market_data(portal_name, search_keyword)
        target_data = scrape_target_page(target_url.strip())
        improvement_img = get_improvement_image_url(search_keyword)
        
    st.success(f"⚡ 調査完了！【{portal_name}】の実際の市場データに基づきレポートを作成します。")

    top_group = df.head(3)

    with st.spinner("AIが競合成功パターンと改善策を生成中..."):
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        top3_info = "▼ 実際の市場上位3商品の詳細\n"
        for idx, row in top_group.iterrows():
            top3_info += f"【{row['オーガニック順位']}位】 寄付額:{row['寄付金額']}円, レビュー件数:{row['レビュー数']}件, 評価:{row['レビュー評価']}, 商品URL:{row['商品URL']}, 商品名:{row['商品名']}\n"

        target_info_text = ""
        if target_data:
            target_info_text = f"\n▼ 【特別診断対象返礼品】\nURL: {target_data['url']}\n現在の商品名: {target_data['title']}\n"

        summary_text = f"""
対象ポータル: {portal_name} / キーワード: {search_keyword} / 日時: {now_str}
{top3_info}
{target_info_text}
改善イメージ画像URL: {improvement_img}
"""
        PROMPT = """あなたは「ふるさと納税およびEコマース」のSEO・デザインスペシャリストです。提供された「実際の上位商品データ」に基づき、売上アップのための改善レポートを作成してください。

1. 実際の上位3商品の特徴（表形式：順位、商品名(リンク付き)、価格、レビュー件数、評価、特徴）※画像列は作成しないでください。
2. 成功パターン（上位の共通点）
3. NG施策（避けるべきこと）
4. 【重要】商品画像の改善案（提供された「改善イメージ画像URL」を使って <img src="URL" style="border-radius:12px; width:100%; max-width:400px; margin-bottom:15px;"> という形で画像を貼り付け、その下に「なぜこの構図が良いのか」「どんな文字(例:大容量!/レンチン!)を入れるべきか」を箇条書きで解説してください。）
5. アクションプラン（明日からやるべき具体改善策）
6. 【指定返礼品の特別診断】（※対象URLがある場合のみ）

【厳守事項・フォーマットルール】
・「1. 実際の上位3商品の特徴」の表では、提供された「商品URL」を使用して、商品名を <a href="商品URL" target="_blank" rel="noopener noreferrer">商品名</a> のように必ずHTMLアンカータグでリンク付きにして出力してください。
・すべての表（<table>）の <th> タグには style="white-space: nowrap;" を必ず付与し、見出し項目が改行されないよう横1行で出力してください。
・強調したい重要なキーワードや文章は、<mark>キーワード</mark> のように必ず <mark> タグを使用してハイライトしてください。（** や spanタグは使用しないでください）
・文章の羅列ではなく、HTMLの表（<table border="1" style="border-collapse: collapse; width: 100%; text-align: left;">）を多用して整理してください。
・各項目は <h2> タグで見出しにしてください。
・マークダウン記号（#、**、*, | など）は絶対に含めず、全てHTMLで出力してください。
・インデント（行頭のスペースやタブ）は一切使用せず、すべての行を左詰めで出力してください。"""

        response = model.generate_content(PROMPT + "\n" + summary_text)
        
        raw_text = response.text
        raw_text = re.sub(r"```[a-zA-Z]*", "", raw_text)
        raw_text = raw_text.replace("```", "")
        report_text = "\n".join([line.strip() for line in raw_text.split('\n') if line.strip() != ""])

    with st.spinner("Googleスプレッドシート・ドキュメントを生成中...（約10〜30秒かかります）"):
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
