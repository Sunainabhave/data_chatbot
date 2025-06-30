import streamlit as st
import requests

st.set_page_config(page_title="Data Chatbot", layout="wide")
st.title("Data Chatbot 🤖")

if "file_id" not in st.session_state:
    st.session_state.file_id = None
if "file_type" not in st.session_state:
    st.session_state.file_type = None

with st.sidebar:
    st.header("📄 Upload File")
    file = st.file_uploader("Choose CSV, Excel, PDF, or DOCX", type=["csv", "xlsx", "pdf", "docx"])

    if file:
        files = {"file": (file.name, file.getvalue())}
        try:
            res = requests.post("http://localhost:8000/upload", files=files)
            if res.status_code == 200:
                data = res.json()
                st.session_state.file_id = data["file_id"]
                st.session_state.file_type = data["file_type"]
                st.success("✅ File uploaded successfully!")
            else:
                st.error(f"❌ Upload failed: {res.json().get('detail', 'Unknown error')}")
        except requests.exceptions.ConnectionError:
            st.error("⚠️ Backend not running. Please start FastAPI server on port 8000.")

if prompt := st.chat_input("💬 Ask about your data..."):
    if not st.session_state.file_id:
        st.error("⚠️ Please upload a file first.")
        st.stop()

    try:
        res = requests.post(
            "http://localhost:8000/ask",
            params={
                "query": prompt,
                "file_id": st.session_state.file_id,
                "file_type": st.session_state.file_type
            }
        )

        if res.status_code == 200:
            data = res.json()
            if data["type"] == "sql":
                st.subheader("🧾 Generated SQL")
                st.code(data["sql"], language="sql")
                st.subheader("📊 Query Result")
                st.table(data["result"])
            else:
                st.subheader("🗣️ Answer")
                st.write(data["answer"])
                st.subheader("🔍 Relevant Context")
                for ctx in data["context"]:
                    st.write("- " + ctx)
        else:
            st.error(f"❌ Query failed: {res.json().get('detail', 'Unknown error')}")
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Couldn't connect to backend while processing query.")
