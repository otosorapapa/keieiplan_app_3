from __future__ import annotations

import streamlit as st

from core import io, validators


def main() -> None:
    st.title("データ入力")
    st.caption("財務諸表や前提条件をアップロードまたは手入力します。")

    uploaded_file = st.file_uploader("財務データファイル", type=("xlsx", "csv"))
    dataset = None
    if uploaded_file:
        dataset = io.load_uploaded_dataset(uploaded_file)
        st.success("ファイルが読み込まれました。")
        st.json(dataset)

    with st.expander("手動入力フォーム", expanded=False):
        st.write("TODO: 売上・費用・投資などの入力フォームを配置します。")

    validation_messages = validators.validate_input_payload(dataset or {})
    if validation_messages:
        st.warning("入力内容の確認が必要です。")
        for message in validation_messages:
            st.write(f"- {message}")
    else:
        st.info("入力値の整合性チェックに通過しました。")


if __name__ == "__main__":
    main()
