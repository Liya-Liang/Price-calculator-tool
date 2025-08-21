from __future__ import annotations

import io
from datetime import date
from typing import List

import streamlit as st
import pandas as pd

from pricing import (
    InputRow,
    OutputRow,
    batch_calculate,
    to_dataframe,
    template_dataframe,
)

st.set_page_config(page_title="活动提报价格测算工具", layout="wide")

st.title("活动提报价格测算工具")
st.caption("输入最低可接受活动价与折扣要求，倒推参考价/过去30天最低价的最低要求，并给出时间窗口")

# Welcome popover on first run (auto-open, close on outside click)
if 'first_run' not in st.session_state:
    popover_label = "🎉 欢迎使用活动提报价格测算工具"
    with st.popover(popover_label, use_container_width=True):
        st.markdown(
            """
            # 价格计算工具使用说明
            
            ## 📖 功能简介
            - 快速计算商品活动前价格要求，并给出价格策略建议
            - 支持单条计算和批量导入/导出
            - 支持CSV和XLSX格式
            - 支持实时可视化结果
            
            ## 🚀 使用方法
            1. 单条计算：在对应输入框中输入参数，点击计算，查看计算结果和操作建议
            2. 批量导入/导出：下载模板，填写后上传，查看计算结果和操作建议,可直接线上查看结果也可批量下载结果
            
            ## 💡 提示
            - 所有数据仅在当前会话有效
            - 支持导出计算结果
            - 此工具仅作为价格推算参考，实际价格要求以卖家后台为准
            
            ---
            © 版权所有：Liya Liang
            """
        )
    # Inject a tiny script to auto-click the popover trigger after render
    try:
        st.html(
            """
            <script>
            (function openWelcome(){
              const label = "🎉 欢迎使用活动提报价格测算工具";
              function tryOpen(){
                const btns = window.parent.document.querySelectorAll('button[data-testid="stPopoverButton"]');
                for (const b of btns){ if ((b.innerText||'').includes(label)) { b.click(); return; } }
                setTimeout(tryOpen, 150);
              }
              // Delay slightly to ensure DOM ready
              setTimeout(tryOpen, 50);
            })();
            </script>
            """,
            height=0,
        )
    except Exception:
        import streamlit.components.v1 as components  # type: ignore
        components.html(
            """
            <script>
            (function openWelcome(){
              const label = "🎉 欢迎使用活动提报价格测算工具";
              function tryOpen(){
                const btns = window.parent.document.querySelectorAll('button[data-testid="stPopoverButton"]');
                for (const b of btns){ if ((b.innerText||'').includes(label)) { b.click(); return; } }
                setTimeout(tryOpen, 150);
              }
              setTimeout(tryOpen, 50);
            })();
            </script>
            """,
            height=0,
        )
    st.session_state.first_run = True

with st.expander("单条计算", expanded=True):
    c1, c2, c3, c4, c5 = st.columns(5)
    asin = c1.text_input("ASIN号", "B00EXAMPLE")
    start_date = c2.date_input("活动开始日期 (MM/DD/YYYY)", value=date.today(), format="MM/DD/YYYY")
    min_price = c3.number_input("最低可接受活动价($)", min_value=0.01, value=19.99, step=0.01)
    ref_disc = c4.number_input("参考价折扣要求(%)", min_value=0.0, max_value=99.99, value=20.0, step=0.1)
    past_disc = c5.number_input("过去30天最低价折扣(%)", min_value=0.0, max_value=99.99, value=0.0, step=0.1)

    if st.button("计算", type="primary"):
        row = InputRow(
            asin=asin,
            start_date=start_date,
            min_acceptable_price=min_price,
            ref_discount_percent=ref_disc,
            past30_discount_percent=past_disc,
        )
        result: OutputRow = batch_calculate([row])[0]
        df = to_dataframe([result])
        st.dataframe(df, use_container_width=True)
        # 操作建议
        try:
            from pricing import build_suggestions

            tips = build_suggestions(result)
            if tips:
                st.markdown("**操作建议：**")
                for t in tips:
                    st.markdown(f"- {t}")
        except Exception:
            pass

with st.expander("批量导入/导出", expanded=True):
    col_dl, col_up = st.columns([1, 2])
    with col_dl:
        st.markdown("下载模板：")
        tmpl_df = template_dataframe()
        csv_buf = io.StringIO()
        tmpl_df.to_csv(csv_buf, index=False)
        st.download_button(
            label="下载CSV模板",
            data=csv_buf.getvalue().encode("utf-8-sig"),
            file_name="template.csv",
            mime="text/csv",
        )
        xlsx_buf = io.BytesIO()
        with pd.ExcelWriter(xlsx_buf, engine="xlsxwriter") as writer:
            tmpl_df.to_excel(writer, index=False, sheet_name="模板")
        st.download_button(
            label="下载XLSX模板",
            data=xlsx_buf.getvalue(),
            file_name="template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col_up:
        st.markdown("上传已填写的模板：")
        uploaded = st.file_uploader("上传CSV或XLSX", type=["csv", "xlsx"])
    if uploaded is not None:
            if uploaded.name.lower().endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
            st.dataframe(df.head(20))

            from pricing import from_input_dataframe

            try:
                rows: List[InputRow] = from_input_dataframe(df)
                results: List[OutputRow] = batch_calculate(rows)
                out_df = to_dataframe(results)
                st.subheader("计算结果")
                st.dataframe(out_df, use_container_width=True)

                out_csv = io.StringIO()
                out_df.to_csv(out_csv, index=False)
                st.download_button(
                    label="下载结果CSV",
                    data=out_csv.getvalue().encode("utf-8-sig"),
                    file_name="results.csv",
                    mime="text/csv",
                )
            except Exception as e:
                st.error(str(e))

st.markdown("---")
with st.expander("说明与建议"):
    st.markdown(
        """
        - 参考价：系统抓取的过去90天买家支付的中间价格（不含促销），若70%以上时间以某促销价成交，则该促销价可能被抓取为参考价。
        - 过去30天最低价：过去30天的实际成交最低价，所有促销都会影响该值。
        - 计算逻辑：为满足最低活动价P，要求 参考价≥P/(参考折扣系数)；过去30天最低价≥P/(过去30天折扣系数)。
        - 时间窗口：参考价窗口[S-90, S-1]；过去30天窗口[S-30, S-1]，S为活动开始日期。
        - 操作建议：
            1) 在参考价窗口内，避免将产品价格/促销价下调至参考价最低值以下，且避免>70%的时间以该价格促销。
            2) 在过去30天窗口内，确保实际成交价不低于对应最低值，避免叠加折扣导致价低。
        """
    )