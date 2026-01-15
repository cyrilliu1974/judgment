import streamlit as st
import requests
import datetime
import urllib3
import ssl
import sys  # 新增：用於判斷執行環境
import os   # 新增：用於讀取 GitHub Secrets
import argparse # 新增：用於解析指令
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# ==========================================
# SSL 強制修正區塊 (解決 Streamlit Cloud 連線政府網站錯誤)
# ==========================================
# 1. 忽略 InsecureRequestWarning 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 2. 定義一個不安全的 SSL Adapter，強制降低安全等級
class UnsafeSSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        # 建立一個忽略憑證驗證的 SSL Context
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        # 強制設定加密演算法 (避開某些政府網站不支援新版加密的問題)
        # SECLEVEL=1 允許較舊的簽章算法
        try:
            ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        except Exception:
            # 如果系統不支援 SECLEVEL 設定，則使用預設
            pass
            
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx
        )

# ==========================================
# 新增：CLI 執行模式 (給 GitHub Actions 使用)
# ==========================================
def run_cli_mode(jid_input):
    # 從 GitHub Secrets 讀取帳密
    user = os.getenv("JUDICIALUSER")
    pwd = os.getenv("JUDICIALPWD")
    
    if not user or not pwd:
        print("❌ 錯誤：未設定環境變數 JUDICIAL_USER 或 JUDICIAL_PWD")
        return

    # 解析 JID
    parts = jid_input.split(",")
    if len(parts) != 6:
        print("❌ 錯誤：JID 格式應為 法院,年度,字別,號次,日期,序號")
        return

    api = JudicialYuanAPI(user, pwd)
    # 執行查詢
    data, err = api.get_judgment_content(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])
    
    if err or (isinstance(data, dict) and "error" in data):
        print(f"❌ 查詢失敗：{err or data.get('error')}")
    else:
        # 建立 output 目錄
        os.makedirs("output", exist_ok=True)
        filename = f"output/{jid_input.replace(',', '_')}.md"
        content = data.get("JFULLX", {}).get("JFULLCONTENT", "無內容")
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# 判決解析：{jid_input}\n\n")
            f.write(f"**案由**：{data.get('JTITLE')}\n\n")
            f.write("## 判決全文\n\n")
            f.write(content)
        print(f"✅ 成功存檔至：{filename}")

# ==========================================
# 原有邏輯封裝：Streamlit UI
# ==========================================
def run_streamlit_app():
    # 頁面設定
    st.set_page_config(page_title="司法院裁判書查詢系統", layout="wide")

    # CSS 優化 (讓文字框更好閱讀)
    st.markdown("""
        <style>
        .stTextArea textarea { font-size: 16px !important; line-height: 1.6 !important; }
        </style>
    """, unsafe_allow_html=True)

    st.title("⚖️ 司法院裁判書查詢系統")

    # 1. 讀取 Secrets 帳號密碼
    if "judicial" in st.secrets:
        user_id = st.secrets["judicial"]["user"]
        user_pwd = st.secrets["judicial"]["password"]
        # 初始化 API 物件
        api = JudicialYuanAPI(user_id, user_pwd)
    else:
        st.error("⚠️ 請於 .streamlit/secrets.toml 設定 [judicial] 區塊之帳號密碼。")
        st.stop()

    # 2. URL 參數解析與搜尋條件初始化
    st.markdown("### 🔍 輸入查詢條件")
    st.info("請輸入判決書詳細資訊以進行精準查詢，或使用 URL 參數自動帶入。")

    # 初始化預設值
    today = datetime.date.today()
    defaults = {
        "court_index": 1,  # 預設：臺灣高等法院 (index 1)
        "year": today.year - 1911,
        "word": "重上更三",
        "no": "32",
        "date": today,
        "seq": "1",
        "auto_run": False
    }

    # 解析 URL 參數 (處理 jid)
    params = st.query_params
    if "jid" in params:
        try:
            jid_str = params["jid"]
            jid_parts = jid_str.split(",") if "," in jid_str else jid_str.split("%2C")
            
            if len(jid_parts) == 6:
                p_court_code, p_year, p_word, p_no, p_date_str, p_seq = jid_parts
                court_map_reverse = {v: k for k, v in api.court_map.items()}
                
                if p_court_code in court_map_reverse:
                    court_name = court_map_reverse[p_court_code]
                    court_keys = list(api.court_map.keys())
                    if court_name in court_keys:
                        defaults["court_index"] = court_keys.index(court_name)
                
                defaults["year"] = int(p_year)
                defaults["word"] = p_word
                defaults["no"] = p_no
                defaults["date"] = datetime.datetime.strptime(p_date_str, "%Y%m%d").date()
                defaults["seq"] = p_seq
                defaults["auto_run"] = True
                st.toast(f"已偵測 URL 參數，自動搜尋：{jid_str}")
                
        except Exception as e:
            st.error(f"URL 參數解析失敗: {e}")

    # 3. 搜尋表單
    with st.form("search_form"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            input_court = st.selectbox("法院", list(api.court_map.keys()), index=defaults["court_index"])
            input_year = st.number_input("年度 (民國)", min_value=1, max_value=200, value=defaults["year"])
            
        with col2:
            input_word = st.text_input("字別", value=defaults["word"], placeholder="例如：訴、上易")
            input_no = st.text_input("號次", value=defaults["no"])
            
        with col3:
            input_date = st.date_input("裁判日期", value=defaults["date"])
            input_seq = st.text_input("序號", value=defaults["seq"], help="同一案件同一日若有多筆裁判，請調整序號")

        submitted = st.form_submit_button("🚀 開始查詢", type="primary")

    # 4. 處理查詢結果
    if submitted or defaults["auto_run"]:
        with st.spinner("正在連線司法院資料庫..."):
            data, error_msg = api.get_judgment_content(
                input_court, 
                str(input_year), 
                input_word, 
                input_no, 
                input_date, 
                input_seq
            )
            
            if error_msg:
                st.error(f"❌ 查詢失敗: {error_msg}")
            elif isinstance(data, dict) and "error" in data:
                st.warning(f"⚠️ 系統回傳訊息: {data['error']}")
                st.caption("提示：請檢查日期、字號是否完全正確，或該案件可能尚未公開。")
            else:
                st.success("✅ 成功取得裁判書內容！")
                case_title = data.get("JTITLE", "(無案由資料)")
                full_content_obj = data.get("JFULLX", {})
                text_content = full_content_obj.get("JFULLCONTENT", "內容為空")
                pdf_link = full_content_obj.get("JFULLPDF", "")
                
                st.divider()
                st.subheader(f"📄 {input_court} {input_year}年度{input_word}字第{input_no}號")
                st.markdown(f"**【案由】**：{case_title}")
                st.markdown(f"**【裁判日期】**：{input_date.strftime('%Y-%m-%d')}")
                
                if pdf_link:
                    st.markdown(f"📥 **[點擊下載原始 PDF 檔案]({pdf_link})**")
                
                st.markdown("#### 📜 判決全文")
                st.text_area("全文內容", text_content, height=600)
                
                with st.expander("🛠️ 查看原始 JSON 資料 (Debug)"):
                    st.json(data)

# ==========================================
# 程式入口點：決定執行 UI 還是 CLI
# ==========================================
if __name__ == "__main__":
    # 如果指令中有 --jid 參數，則執行 CLI 模式
    if "--jid" in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument("--jid", help="判決書編號")
        args, unknown = parser.parse_known_args()
        run_cli_mode(args.jid)
    else:
        # 否則正常執行 Streamlit UI
        run_streamlit_app()