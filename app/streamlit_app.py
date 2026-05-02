import streamlit as st

st.title("ResearchPilot")
st.write("当前为最小 MVP 骨架版本，暂未接入后端业务逻辑。")

st.subheader("未来功能（规划中）")
st.markdown("""
- PDF 上传与管理
- PDF 解析与分块
- 混合检索（BM25 + 向量）
- 带证据引用的问答
- 论文卡片生成
- 文献综述生成
- Claim 级引用验证
""")
