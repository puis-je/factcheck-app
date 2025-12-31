import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import markdown
from duckduckgo_search import DDGS
import datetime

# ページ設定
st.set_page_config(page_title="AI Fact Checker Pro (2025 Edition)", layout="wide")

# --- セッションステートの初期化 ---
if 'result_md' not in st.session_state:
    st.session_state.result_md = None
if 'source_text' not in st.session_state:
    st.session_state.source_text = None
if 'search_log' not in st.session_state:
    st.session_state.search_log = None

# --- サイドバー ---
with st.sidebar:
    st.header("⚙️ 設定")
    
    # 日付設定
    st.subheader("📅 基準日の設定")
    default_date = datetime.date.today()
    reference_date = st.date_input(
        "「今日」をいつとして検証しますか？",
        value=default_date
    )
    
    st.markdown("---")
    
    # APIキー
    with st.expander("❓ APIキーの取得方法"):
        st.markdown("[Google AI Studio](https://aistudio.google.com/app/apikey) で取得して貼り付けてください。")
    api_key = st.text_input("Google Gemini APIキー", type="password", placeholder="AIzaSy...")
    
    # モデル選択（2025年ラインナップ）
    st.subheader("🤖 モデル選択")
    
    # 表示名と実際のモデルIDの対応表
    model_options = {
        "Gemini 2.5 Flash (標準・安定版)": "gemini-2.5-flash",
        "Gemini 3 Pro (最新・最高性能)": "gemini-3.0-pro",
        "Gemini 3 Flash (最新・高速)": "gemini-3.0-flash",
        "Gemini 2.5 Pro (高精度)": "gemini-2.5-pro",
        "Gemini 2.5 Flash-Lite (軽量)": "gemini-2.5-flash-lite",
        "Custom (手動入力)": "custom"
    }
    
    selected_label = st.selectbox(
        "使用するGeminiモデル",
        list(model_options.keys()),
        index=0, # 0番目（Gemini 2.5 Flash）をデフォルトにする
        help="基本は Gemini 2.5 Flash で十分ですが、複雑な検証には 3 Pro が有効です。"
    )
    
    # モデルIDの決定
    if selected_label == "Custom (手動入力)":
        model_name = st.text_input("モデルIDを入力 (例: gemini-3.0-pro-001)", "gemini-2.5-flash")
    else:
        model_name = model_options[selected_label]

    st.info(f"現在のモデルID: **{model_name}**")
    
    if st.button("🗑️ 結果をクリア"):
        st.session_state.result_md = None
        st.session_state.source_text = None
        st.session_state.search_log = None
        st.rerun()

# --- メインエリア ---
st.title("🛡️ AI Fact Checker Pro (2025 Edition)")
st.markdown(f"""
Web記事を読み込み、**基準日（{reference_date.strftime('%Y/%m/%d')}）** 時点の検索情報に基づいてファクトチェックを行います。
最新の **Gemini 3 / 2.5 シリーズ** を使用して、より正確な検証が可能です。
""")

url_input = st.text_input("検証したい記事のURL", placeholder="https://example.com/article...")

if st.button("🔍 検索して検証する", type="primary"):
    if not api_key:
        st.error("APIキーを入力してください")
    elif not url_input:
        st.warning("URLを入力してください")
    else:
        status_area = st.empty()
        
        try:
            # 1. 記事のスクレイピング
            status_area.info("🌐 1/3 Webページを読み込んでいます...")
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url_input, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            
            for tag in soup(["script", "style", "header", "footer", "nav", "iframe"]):
                tag.decompose()
            
            text_content = ""
            for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'li', 'article']):
                text_content += tag.get_text() + "\n"
            
            if len(text_content) > 15000:
                text_content = text_content[:15000] + "..."
            
            if len(text_content) < 50:
                st.error("本文が取得できませんでした。")
                st.stop()

            # 2. 検索キーワードの抽出と検索実行
            status_area.info("🌍 2/3 最新情報を広範囲に検索中...")
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            # 検索クエリ作成
            query_prompt = f"""
            以下のテキストに含まれる「具体的な出来事」「災害」「事件」「固有名詞」の真偽を確認するための検索キーワードを3つ作成してください。
            
            【重要】
            - 基準日（{reference_date}）時点での事実確認を行います。
            - 具体的な災害名（例：能登半島豪雨）や事件名がある場合は必ず含めてください。
            
            テキスト: {text_content[:2000]}
            """
            query_resp = model.generate_content(query_prompt)
            search_queries = query_resp.text.strip()
            
            # DuckDuckGoで検索（件数を確保）
            search_results = ""
            with DDGS() as ddgs:
                keywords = [k.strip() for k in search_queries.split(',')]
                log_text = ""
                
                for keyword in keywords[:3]:
                    # max_results=5 で情報を厚くする
                    results = list(ddgs.text(keyword, max_results=5))
                    if results:
                        log_text += f"**検索語:** {keyword}\n"
                        for r in results:
                            search_results += f"- {r['title']}: {r['body']}\n"
                            log_text += f"  - {r['title']}\n"
            
            st.session_state.search_log = log_text

            # 3. 検索結果を使ったファクトチェック
            status_area.info(f"🤖 3/3 AI ({model_name}) が検証中...")
            
            final_prompt = f"""
            あなたは公平かつ厳格なファクトチェッカーです。
            以下の「検証対象テキスト」を、**「検索結果」**と照らし合わせて検証してください。

            【基準日】 {reference_date.strftime('%Y年%m月%d日')}

            【判定ルール】
            1. **検索結果に存在する事実は「事実」と認めてください。**
               検索結果にニュースや記録がある場合、あなたの学習データになくても事実として扱ってください。

            2. **「検索結果と矛盾する場合」のみ「誤り」としてください。**
               検索結果に情報がない（Unknown）場合は、「確認できませんでした」としてください。

            3. **未来の日付の扱い**
               記事の日付が基準日より未来であっても、記事内で語られている「過去の出来事」については、事実かどうか厳しくチェックしてください。

            【検索されたエビデンス】
            {search_results}

            【検証対象テキスト】
            {text_content}

            【出力フォーマット】
            Markdown形式で出力してください。

            # 🚨 検証レポート (モデル: {model_name})

            ## 判定結果リスト
            
            ### 1. [記述の引用]
            - **判定:** ❌ 事実誤認 / ⚠️ 要確認 / ✅ 事実と一致
            - **理由:** [検索結果のエビデンス] に基づく解説。

            ---
            ※このレポートは検索結果に基づいています。
            """
            
            final_resp = model.generate_content(final_prompt)
            
            st.session_state.result_md = final_resp.text
            st.session_state.source_text = text_content
            
            status_area.empty()

        except Exception as e:
            status_area.error(f"エラーが発生しました: {e}")

# --- 結果表示 ---
if st.session_state.result_md:
    st.subheader("📊 検証結果")
    st.markdown(st.session_state.result_md)
    
    with st.expander("🔍 参照した検索データを見る"):
        st.markdown(st.session_state.search_log)
        
    st.markdown("---")
    
    # 保存ボタンエリア
    st.subheader("💾 レポートの書き出し")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button("📄 Text保存", st.session_state.result_md, "report.txt")
    with col2:
        st.download_button("📝 Markdown保存", st.session_state.result_md, "report.md")
    with col3:
        html_body = markdown.markdown(st.session_state.result_md)
        html_content = f"<html><body>{html_body}</body></html>"
        st.download_button("🌐 HTML保存", html_content, "report.html", mime="text/html")
    
    st.markdown("---")
    if st.button("🔄 新しい記事を検証する"):
        st.session_state.result_md = None
        st.session_state.source_text = None
        st.session_state.search_log = None
        st.rerun()