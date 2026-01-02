import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import markdown
from duckduckgo_search import DDGS
import datetime

# ==========================================
# 👇 ここを設定してください
# ==========================================

# 1. 送信先URL（あなたのフォームIDを埋め込み済みです）
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScTkDHcvbH6KM-mmN1EtVfLh5T1DNg5OEZggEjSBMqOz2K9hQ/formResponse"

# 2. エントリーID（★ここを書き換えてください！）
# 「事前入力したリンク」で "test" と入力して取得したURLの中にある
# "&entry.123456789=test" の数字部分を入れてください。
ENTRY_ID = "entry.1770217829" 

# ==========================================

# ページ設定
st.set_page_config(page_title="AI Fact Checker Pro (2026 Edition)", layout="wide")

# --- ログ送信関数 ---
def send_log_to_google_form(checked_url):
    """GoogleフォームにURLを送信して記録する"""
    if ENTRY_ID == "entry.123456789":
        return

    try:
        data = {ENTRY_ID: checked_url}
        requests.post(FORM_URL, data=data, timeout=2)
    except:
        pass

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
    
    # モデル選択（2026年最新ラインナップ）
    st.subheader("🤖 モデル選択")
    model_options = {
        "Gemini 3.0 Flash (最新・高速・推奨)": "gemini-3.0-flash",
        "Gemini 3.0 Pro (最新・最高性能)": "gemini-3.0-pro",
        "Gemini 2.5 Flash (安定版)": "gemini-2.5-flash",
        "Gemini 2.5 Pro (高精度)": "gemini-2.5-pro",
        "Gemini 2.5 Flash-Lite (軽量)": "gemini-2.5-flash-lite",
        "Custom (手動入力)": "custom"
    }
    
    # デフォルトを Gemini 3.0 Flash (index=0) に設定
    selected_label = st.selectbox("使用するGeminiモデル", list(model_options.keys()), index=0)
    
    if selected_label == "Custom (手動入力)":
        model_name = st.text_input("モデルIDを入力", "gemini-3.0-flash")
    else:
        model_name = model_options[selected_label]

    st.info(f"現在のモデルID: **{model_name}**")
    
    if st.button("🗑️ 結果をクリア"):
        st.session_state.result_md = None
        st.session_state.source_text = None
        st.session_state.search_log = None
        st.rerun()

# --- メインエリア ---
st.title("🛡️ AI Fact Checker Pro (2026 Edition)")
st.markdown(f"""
Web記事を読み込み、**「最新の検索結果」**と**「AIの科学的・歴史的知識」**を組み合わせてファクトチェックを行います。
基準日: **{reference_date.strftime('%Y/%m/%d')}**
""")

url_input = st.text_input("検証したい記事のURL", placeholder="https://example.com/article...")

if st.button("🔍 検索して検証する", type="primary"):
    if not api_key:
        st.error("APIキーを入力してください")
    elif not url_input:
        st.warning("URLを入力してください")
    else:
        # ログ送信
        send_log_to_google_form(url_input)
        
        status_area = st.empty()
        
        try:
            # 1. スクレイピング
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

            # 2. 検索
            status_area.info("🌍 2/3 最新情報を検索中...")
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            query_prompt = f"""
            以下のテキストの真偽を検証するための検索キーワードを3つ作成してください。
            特に「時事問題」「具体的な事件」「新しい科学的主張」に焦点を当ててください。
            テキスト: {text_content[:2000]}
            """
            query_resp = model.generate_content(query_prompt)
            search_queries = query_resp.text.strip()
            
            search_results = ""
            with DDGS() as ddgs:
                keywords = [k.strip() for k in search_queries.split(',')]
                log_text = ""
                for keyword in keywords[:3]:
                    results = list(ddgs.text(keyword, max_results=5))
                    if results:
                        log_text += f"**検索語:** {keyword}\n"
                        for r in results:
                            search_results += f"- {r['title']}: {r['body']}\n"
                            log_text += f"  - {r['title']}\n"
            
            st.session_state.search_log = log_text

            # 3. ハイブリッド検証
            status_area.info(f"🤖 3/3 AI ({model_name}) が知識と検索結果を統合して検証中...")
            
            final_prompt = f"""
            あなたは科学的・歴史的知識を持つファクトチェッカーです。
            以下の「検証対象テキスト」を、**「検索結果」**および**「あなたの持つ知識」**の両方を使って検証してください。

            【基準日】 {reference_date.strftime('%Y年%m月%d日')}

            【判定優先順位】
            1. **最新の時事問題（人事、事件、災害など）**
               -> **「検索結果」を最優先**してください。検索結果と矛盾する場合は「誤り」と判定してください。

            2. **一般的な科学・歴史・医学（ニセ科学、陰謀論など）**
               -> 検索結果になくても、**あなたの学習済み知識（科学的コンセンサス）**に基づいて判定してください。

            3. **判定不能**
               -> 検索結果にもなく、あなたの知識でも判断がつかない個人的な体験談などは「検証不能」としてください。

            【検索されたエビデンス】
            {search_results}

            【検証対象テキスト】
            {text_content}

            【出力フォーマット】
            Markdown形式で出力してください。

            # 🚨 検証レポート (モデル: {model_name})

            ## 判定結果リスト
            
            ### 1. [記述の引用]
            - **判定:** ❌ 事実誤認 / ⚠️ 科学的根拠なし / ⚠️ 陰謀論の疑い / ✅ 事実と一致
            - **根拠:** [検索結果] または [一般的な科学的知見] に基づく解説。
            - **補足:** (AIの知識ベースで判断した場合は「※AIの学習データに基づく判断です」と追記)

            ---
            ※このレポートは検索結果およびAIの学習データに基づいています。
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
    st.warning("⚠️ 注意: 最新のニュースについては検索結果を優先していますが、一般的な科学・歴史についてはAIの学習データに基づいて判定している場合があります。")
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