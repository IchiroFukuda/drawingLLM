#!/usr/bin/env python3
"""
Drawing Search UI - Streamlit アプリ（シンプル版）
"""

import streamlit as st

# ページ設定
st.set_page_config(
    page_title="Drawing Search - 図面検索",
    page_icon="🔍",
    layout="wide"
)

# テスト
st.title("🔍 Drawing Search")
st.write("このテキストが表示されていますか？")

st.success("✅ Streamlitは正常に動作しています")

st.markdown("---")
st.markdown("### テスト")
st.write("もしこのページが正しく表示されていれば、Streamlit自体は動作しています。")

if st.button("テストボタン"):
    st.balloons()
    st.write("✨ ボタンが動作しました！")
