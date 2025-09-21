from __future__ import annotations

import streamlit as st

from core import finance, validators


def main() -> None:
    st.title("補助金 / 金融機関資料")
    st.caption("補助金申請や金融機関向け資料のアウトラインを準備します。")

    funding_summary = finance.estimate_funding_requirements()
    st.subheader("資金計画サマリー")
    st.json(funding_summary)

    st.markdown("### 申請書テンプレート")
    st.write("TODO: 補助金・融資に必要なドキュメント構成を追加してください。")

    validation_messages = validators.collect_validation_summary(
        validators.validate_input_payload({})
    )
    if validation_messages:
        st.warning("提出前チェック項目")
        st.text(validation_messages)


if __name__ == "__main__":
    main()
