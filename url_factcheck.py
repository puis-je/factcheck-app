import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import markdown
from duckduckgo_search import DDGS

# ページ設定
st.set_page_config(page_title="AI Fact Checker Pro (Live Search)", layout="wide")

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
    with st.expander("❓ APIキーの取得方法"):
        st.markdown("""
        1. **[Google AI Studio](https://aistudio.google.com/app/apikey)** にアクセス。
        2. "Create API key" をクリック。
        3. キーをコピーして下に貼り付け。
        """)
    
    api_key = st.text_input("Google Gemini APIキー", type="password", placeholder="AIzaSy...")
    
    model_name = st.selectbox(
        "使用モデル",
        ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"],
        index=0
    )
    
    if st.button("🗑️ 結果をクリア"):
        st.session_state.result_md = None
        st.session_state.source_text = None
        st.session_state.search_log = None
        st.rerun()

# --- メインエリア ---
st.title("🛡️ AI Fact Checker Pro (Live Search)")
st.markdown("""
Web記事を読み込み、**最新のネット検索情報**と照らし合わせてファクトチェックを行います。
AIの知識だけでなく、検索による裏付けを行うため、最新のニュース（人事や事件など）にも対応可能です。
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
            status_area.info("🌍 2/3 記事の内容について最新情報を検索中...")
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            # 検索クエリを考える
            query_prompt = f"""
            以下のテキストの真偽を検証するために必要な「検索キーワード」を3つ作成してください。
            特に、固有名詞、日付、役職、科学的用語に注目してください。
            出力はキーワードのみをカンマ区切りで出してください。
            
            テキスト: {text_content[:2000]}
            """
            query_resp = model.generate_content(query_prompt)
            search_queries = query_resp.text.strip()
            
            # DuckDuckGoで検索
            search_results = ""
            with DDGS() as ddgs:
                # 生成されたクエリで検索（上位3件×3クエリ程度）
                keywords = [k.strip() for k in search_queries.split(',')]
                log_text = ""
                
                for keyword in keywords[:3]: # 最大3つのキーワードで検索
                    results = list(ddgs.text(keyword, max_results=3))
                    if results:
                        log_text += f"**検索語:** {keyword}\n"
                        for r in results:
                            search_results += f"- {r['title']}: {r['body']}\n"
                            log_text += f"  - {r['title']}\n"
            
            st.session_state.search_log = log_text # 検索ログを保存

            # 3. 検索結果を使ったファクトチェック
            status_area.info("🤖 3/3 検索結果と照らし合わせて検証中...")
            
            final_prompt = f"""
            あなたは厳格なファクトチェッカーです。
            以下の「検証対象テキスト」を、**「最新の検索結果」**およびあなたの知識に基づいて検証してください。

            【重要】
            - AIの学習データよりも、**「最新の検索結果」の情報を優先**してください（例：現在の首相、最新の科学的発見など）。
            - 検索結果と矛盾する記述、または科学的・歴史的に疑わしい記述（ニセ科学、陰謀論、デマ）を抽出してください。

            【検索された最新情報（エビデンス）】
            {search_results}

            【検証対象テキスト】
            {text_content}

            【出力フォーマット】
            Markdown形式で出力してください。

            # 🚨 検証レポート

            ## 疑わしい記述のリスト
            
            ### 1. [疑わしい記述の引用]
            - **判定:** 誤り / 疑義あり / ミスリード
            - **理由:** [検索結果や科学的根拠に基づいた解説]

            ---
            ※このレポートはAIとWeb検索結果に基づいています。

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