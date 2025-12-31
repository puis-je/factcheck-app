import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import markdown

# ページ設定
st.set_page_config(page_title="AI Fact Checker Pro", layout="wide")

# --- セッションステートの初期化（データを記憶する箱を作る） ---
if 'result_md' not in st.session_state:
    st.session_state.result_md = None
if 'source_text' not in st.session_state:
    st.session_state.source_text = None

# --- サイドバー：設定とガイド ---
with st.sidebar:
    st.header("⚙️ 設定")
    
    # APIキー取得ガイド
    with st.expander("❓ APIキーの取得方法（図解）"):
        st.markdown("""
        1. **[Google AI Studio](https://aistudio.google.com/app/apikey)** にアクセスします。
        2. Googleアカウントでログインします。
        3. 左上の **"Create API key"** をクリックします。
        4. **"Create API key in new project"** を選択します。
        5. 生成された `AIzaSy...` から始まるキーをコピーします。
        6. 下の入力欄に貼り付けます。
        """)
        st.info("※APIキーはブラウザ内でのみ使用され、外部に保存されることはありません。")

    # APIキー入力欄
    api_key = st.text_input("Google Gemini APIキー", type="password", placeholder="AIzaSy...")
    
    # モデル選択
    model_name = st.selectbox(
        "使用モデル",
        ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"],
        index=0,
        help="最新の gemini-2.5-flash を推奨します"
    )
    
    # リセットボタン（サイドバーにも配置）
    if st.button("🗑️ 結果をクリアして初期化"):
        st.session_state.result_md = None
        st.session_state.source_text = None
        st.rerun()

# --- メインエリア ---
st.title("🛡️ AI Fact Checker Pro")
st.markdown("""
Web記事のURLを入力すると、**科学的・歴史的な観点**からファクトチェックを行います。
事実を歪めていたり、ニセ科学や陰謀論の疑いがある部分を抽出し、その理由を解説します。
""")

# URL入力
url_input = st.text_input("検証したい記事のURL", placeholder="https://example.com/article...")

# 分析ボタン
if st.button("🔍 記事を読み込んで検証する", type="primary"):
    if not api_key:
        st.error("サイドバーにAPIキーを入力してください！")
    elif not url_input:
        st.warning("URLを入力してください！")
    else:
        # --- 処理開始 ---
        status_area = st.empty() # 進行状況表示用
        
        try:
            # 1. スクレイピング
            status_area.info("🌐 Webページにアクセスして本文を抽出中...")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url_input, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # 不要なタグの削除
            for tag in soup(["script", "style", "header", "footer", "nav", "iframe"]):
                tag.decompose()
            
            # 本文抽出
            text_content = ""
            for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'li', 'article']):
                text_content += tag.get_text() + "\n"
            
            if len(text_content) > 20000:
                text_content = text_content[:20000] + "...(以下省略)"
            
            if len(text_content) < 100:
                st.error("記事の本文がうまく取得できませんでした。")
                st.stop()

            # 2. Geminiによる検証
            status_area.info(f"🤖 AI ({model_name}) がファクトチェックを実行中...")
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            prompt = f"""
            あなたは厳格な科学者であり、歴史家であり、ファクトチェッカーです。
            以下のWeb記事のテキストを読み、**「科学的・歴史的に疑わしい記述（ニセ科学、陰謀論、事実の歪曲、デマ）」**だけを抽出して報告してください。

            【ルール】
            - 科学的合意や歴史的事実に基づいている部分（青）や、単なる意見（黒）は無視してください。
            - **「赤色（Dubious）」に相当する危険な記述だけ**を抜き出してください。
            - もし疑わしい記述が一つもなければ、「この記事には、科学的・歴史的に明らかに誤った記述は見当たりませんでした」と報告してください。

            【出力フォーマット】
            Markdown形式で出力してください。

            # 🚨 検証レポート

            ## 疑わしい記述のリスト
            
            ### 1. [疑わしい記述の引用]
            - **判定理由:** なぜこれが誤り、または疑わしいのかを科学的・歴史的根拠に基づいて簡潔に解説。

            ### 2. [疑わしい記述の引用]
            - **判定理由:** ...

            ---
            ※このレポートはAIによる生成です。最終的な判断は一次情報を確認してください。

            【検証対象テキスト】
            {text_content}
            """
            
            response = model.generate_content(prompt)
            
            # 結果をセッションステートに保存（これでボタンを押しても消えない）
            st.session_state.result_md = response.text
            st.session_state.source_text = text_content
            
            status_area.empty() # 進行状況を消す

        except requests.exceptions.RequestException as e:
            status_area.error(f"Webページへのアクセスに失敗しました: {e}")
        except Exception as e:
            status_area.error(f"エラーが発生しました: {e}")

# --- 結果の表示（セッションステートにデータがある場合のみ表示） ---
if st.session_state.result_md:
    st.subheader("📊 検証結果")
    st.markdown(st.session_state.result_md)
    st.markdown("---")

    # --- 出力・保存エリア ---
    st.subheader("💾 レポートの書き出し")
    col1, col2, col3 = st.columns(3)

    # 1. テキスト形式 (.txt)
    with col1:
        st.download_button(
            label="📄 Text形式で保存",
            data=st.session_state.result_md,
            file_name="factcheck_report.txt",
            mime="text/plain"
        )

    # 2. Markdown形式 (.md)
    with col2:
        st.download_button(
            label="📝 Markdown形式で保存",
            data=st.session_state.result_md,
            file_name="factcheck_report.md",
            mime="text/markdown"
        )

    # 3. HTML形式 (.html)
    with col3:
        html_body = markdown.markdown(st.session_state.result_md)
        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Fact Check Report</title>
            <style>body {{ font-family: sans-serif; padding: 20px; line-height: 1.6; }} h1 {{ color: #d32f2f; }} strong {{ color: #d32f2f; }}</style>
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """
        st.download_button(
            label="🌐 HTML形式で保存",
            data=html_content,
            file_name="factcheck_report.html",
            mime="text/html"
        )

    # 読み込んだ原文の確認
    with st.expander("読み込んだWebページの原文を確認する"):
        st.text(st.session_state.source_text)
    
    # メインエリア下部にもリセットボタン配置
    st.markdown("---")
    if st.button("🔄 新しい記事を検証する（リセット）"):
        st.session_state.result_md = None
        st.session_state.source_text = None
        st.rerun()