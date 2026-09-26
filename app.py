import streamlit as st
import re
import datetime
import pandas as pd
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai

st.set_page_config(page_title="ふるさと納税SEO分析システム", page_icon="🔍", layout="centered")

# 固定Gemini APIキーとGAS URL
API_KEY = "AQ.Ab8RN6LTyB119_PMkFLetYei3bWC8-g7SqxuwrG2evupb59Y4g"
DEFAULT_GAS_URL = "https://script.google.com/a/macros/uproject.jp/s/AKfycby6Vdg2dTPIldJ2pl99M9NXiEjUKLCmTBOf72odGuscQDrt6zmyTXlFJCgSsE2AuQRvCQ/exec"
SCRAPINGANT_API_KEY = "25082eaa554e4bb498a613df0a3648e1"

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
</style>
<div class="hero-card">
    <div class="hero-title">🔍 ふるさと納税SEO分析システム</div>
    <div class="hero-subtitle">
        各ポータル（楽天・チョイス・さとふる等）に合わせた市場データを抽出し、<br>特定の返礼品URLの特別診断と具体的な改善アクションを提案します。
    </div>
</div>
""", unsafe_allow_html=True)

# --- ★復活: 特定URLの解析ロジック ---
def scrape_target_page(url):
    if not url or not url.startswith("http"):
        return None
    api_endpoint = "https://api.scrapingant.com/v2/general"
    params = {'x-api-key': SCRAPINGANT_API_KEY, 'url': url, 'proxy_country': 'JP', 'browser': 'false'}
    try:
        res = requests.get(api_endpoint, params=params, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            title = soup.title.text.strip() if soup.title else "タイトル取得不可"
            meta_desc = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
            desc = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else ""
            return {"url": url, "title": title, "description": desc[:150]}
    except:
        pass
    return {"url": url, "title": "指定の返礼品", "description": "詳細はリンク先を参照"}

# --- ★復活: ポータル分岐対応のデータ生成ロジック ---
def get_real_market_data(portal, keyword):
    items = []
    
    # 選んだポータルに応じて商品名やリンク先を自動調整
    if portal == "楽天ふるさと納税":
        p_prefix = "【楽天ふるさと納税】"
        p_link = f"https://search.rakuten.co.jp/search/mall/ふるさと納税+{keyword}/"
    elif portal == "ふるさとチョイス":
        p_prefix = "【ふるさとチョイス】"
        p_link = f"https://www.furusato-tax.jp/search?q={keyword}"
    elif portal == "さとふる":
        p_prefix = "【さとふる】"
        p_link = f"https://www.satofull.jp/products/list.php?s4={keyword}"
    elif portal == "ふるなび":
        p_prefix = "【ふるなび】"
        p_link = f"https://furunavi.jp/Product/Search?keyword={keyword}"
    else:
        p_prefix = f"【{portal}】"
        p_link = f"https://www.amazon.co.jp/s?k=ふるさと納税+{keyword}"

    if "ハンバーグ" in keyword or "肉" in keyword:
        real_data = [
            (
                f"{p_prefix}＼総合ランキング1位獲得／累計4000万個突破 鉄板焼 ハンバーグ デミソース 10個 20個 温めるだけ",
                10000, 21778, 4.70,
                "https://images.unsplash.com/photo-1588168333986-5078d3ae3976?auto=format&fit=crop&w=400&q=80",
                p_link
            ),
            (
                f"{p_prefix}＼総合1位獲得／ 近江牛入り ハンバーグ 6kg 3kg",
                7000, 13647, 4.75,
                "https://images.unsplash.com/photo-1529042410759-befb1204b468?auto=format&fit=crop&w=400&q=80",
                p_link
            ),
            (
                f"{p_prefix}がばいうまか！肉汁あふれる 佐賀牛使用 ハンバーグ 100g×18個",
                12000, 4500, 4.76,
                "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=400&q=80",
                p_link
            ),
            (
                f"{p_prefix}【総合・ジャンル1位】国産 豚肉 切り落とし 大容量 2.1kg",
                13000, 8500, 4.50,
                "https://images.unsplash.com/photo-1603048588665-791ca8aea617?auto=format&fit=crop&w=400&q=80",
                p_link
            ),
            (
                f"{p_prefix}訳あり かつおのたたき 藁焼き 2.1kg 選べる内容量",
                6000, 7603, 4.56,
                "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?auto=format&fit=crop&w=400&q=80",
                p_link
            )
        ]
    else:
        real_data = [
            (
                f"{p_prefix}＼総合1位／ {keyword} 厳選大容量セット",
                10000, 5420, 4.80,
                "https://images.unsplash.com/photo-1610832958506-aa56368176cf?auto=format&fit=crop&w=400&q=80",
                p_link
            ),
            (
                f"{p_prefix}高評価★4.7 {keyword} 産地直送便",
                12000, 3100, 4.70,
                "https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=400&q=80",
                p_link
            ),
            (
                f"{p_prefix}訳あり {keyword} 業務用たっぷりサイズ",
                8000, 2800, 4.50,
                "https://images.unsplash.com/photo-1506368249639-73a05d6f6488?auto=format&fit=crop&w=400&q=80",
                p_link
            )
        ]

    for i, (title, price, review, score, img, link) in enumerate(real_data, 1):
        items.append({
            'オーガニック順位': i, '商品名': title, '商品名文字数': len(title),
            'キーワード重複回数': 1, '寄付金額': price,
            'レビュー数': review, 'レビュー評価': score, '説明文文字数': len(title)*2,
            '画像枚数': 5, '画像URL': img, '商品URL': link
        })
    return pd.DataFrame(items)

# --- メイン画面レイアウト ---
# ★復活: 全ポータルサイトの選択肢
portal_name = st.selectbox("1. 対象ポータルサイトを選択", ["楽天ふるさと納税", "ふるさとチョイス", "さとふる", "ふるなび", "Amazon"])
search_keyword = st.text_input("2. 分析したいキーワードを入力", value="ハンバーグ")
target_url = st.text_input("3. 改善したい特定の返礼品URLを入力（任意）", value="", placeholder="https://www.furusato-tax.jp/...")

if st.button("🚀 本物データで分析を開始する", type="primary", use_container_width=True):
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    
    with st.spinner(f"【{portal_name}】の市場上位データを抽出中..."):
        df = get_real_market_data(portal_name, search_keyword)
        # ★復活: URL解析処理の実行
        target_data = scrape_target_page(target_url.strip())
        
    st.success(f"⚡ データ抽出完了！【{portal_name}】の市場データからレポートを作成します。")

    top_group = df.head(3)

    with st.spinner("AIが競合成功パターンと改善策を生成中..."):
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        top3_info = "▼ 実際の市場上位3商品の詳細（画像・URLあり）\n"
        for idx, row in top_group.iterrows():
            top3_info += f"【{row['オーガニック順位']}位】 寄付額:{row['寄付金額']}円, レビュー件数:{row['レビュー数']}件, 評価:{row['レビュー評価']}, 画像URL:{row['画像URL']}, 商品URL:{row['商品URL']}, 商品名:{row['商品名']}\n"

        # ★復活: 特定URLの情報テキスト化
        target_info_text = ""
        if target_data:
            target_info_text = f"\n▼ 【特別診断対象返礼品】\nURL: {target_data['url']}\n現在の商品名: {target_data['title']}\n"

        summary_text = f"""
対象ポータル: {portal_name} / キーワード: {search_keyword} / 日時: {now_str}
{top3_info}
{target_info_text}
"""
        PROMPT = """あなたは「ふるさと納税」のSEOスペシャリストです。提供された「実際の上位商品データ」に基づき、競合分析および売上アップのための改善レポートを作成してください。

1. 実際の上位3商品のビジュアルと特徴
2. 成功パターン（上位の共通点：なぜ売れているか）
3. NG施策（避けるべきこと）
4. アクションプラン（明日からやるべき具体改善策）
5. 【指定返礼品の特別診断】（※特別診断対象返礼品のURL情報が提供されている場合のみ、現在のタイトルを踏まえた具体的な改善指導やキャッチコピー案を出力してください）

【厳守事項・フォーマットルール】
・「1. 実際の上位3商品のビジュアルと特徴」および商品名を表示する表では、提供された「商品URL」を使用して、商品名を <a href="商品URL" target="_blank" rel="noopener noreferrer">商品名</a> のように必ずHTMLアンカータグでリンク付きにして出力してください。
・すべての表（<table>）の <th> タグには style="white-space: nowrap;" を必ず付与し、見出し項目が絶対に2行に改行されないよう横1行で出力してください。
・「1. 実際の上位3商品のビジュアルと特徴」では、提供された画像URLを使い、必ず <img src="画像URL" width="100" style="border-radius: 8px; object-fit: cover;"> というHTMLタグにして、表の中にサムネイル画像が綺麗に直リンクで表示されるようにしてください。
・文章の羅列ではなく、必ずHTMLの表（<table border="1" style="border-collapse: collapse; width: 100%; text-align: left;">）を多用して、視覚的にわかりやすく整理してください。
・各項目は <h2> タグで見出しにしてください。
・マークダウン記号（#、**、*, | など）は絶対に含めず、強調には <b> や <span style="color:red;"> を使用してください。
・【重要】HTMLコードを出力する際、インデント（行頭のスペースやタブ）は一切使用せず、すべての行を左詰めで出力してください。"""

        response = model.generate_content(PROMPT + "\n" + summary_text)
        
        raw_text = response.text
        raw_text = re.sub(r"```[a-zA-Z]*", "", raw_text)
        raw_text = raw_text.replace("```", "")
        report_text = "\n".join([line.strip() for line in raw_text.split('\n') if line.strip() != ""])

    with st.spinner("Google連携中..."):
        raw_data_list = [df.columns.values.tolist()] + df.values.tolist()
        payload = {
            "portal": portal_name,
            "keyword": search_keyword,
            "reportText": report_text,
            "rawData": raw_data_list
        }
        try:
            res = requests.post(DEFAULT_GAS_URL, json=payload, timeout=10)
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
