import streamlit as st
import requests
import datetime

# ==========================================
# 核心邏輯：司法院 API 串接類別
# 依據 PDF 規格書實作
# ==========================================
class JudicialYuanAPI:
    def __init__(self, user, password):
        # 基礎 API 路徑
        self.base_url = "https://data.judicial.gov.tw/jdg/api"
        self.user = user
        self.password = password
        self.token = None
        
        # 法院代碼對照表 (可依需求擴充)
        self.court_map = {
            "最高法院": "TPS",
            "臺灣高等法院": "TPHM",
            "臺中高分院": "TCH",
            "高雄高分院": "KSH",
            "臺北地方法院": "TPD",
            "新北地方法院": "PCD",
            "臺中地方法院": "TCD",
            "高雄地方法院": "KSD"
        }

    def authenticate(self):
        """
        驗證權限並取得 Token
        
        """
        url = f"{self.base_url}/Auth"
        payload = {
            "user": self.user,
            "password": self.password
        }
        
        try:
            # 發送 POST 請求驗證
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            response.raise_for_status()
            data = response.json()
            
            # 若成功回傳 Token，否則回傳錯誤
            if "Token" in data:
                self.token = data["Token"]
                return True, "驗證成功"
            else:
                return False, data.get('error', '驗證失敗')
                
        except Exception as e:
            return False, f"連線錯誤: {str(e)}"

    def get_judgment_content(self, court_name, roc_year, case_word, case_no, date_dt, seq_no="1"):
        """
        組合 JID 並取得裁判書內容
        
        """
        # 1. 檢查 Token
        if not self.token:
            success, msg = self.authenticate()
            if not success:
                return None, msg

        try:
            # 2. 參數轉換與 JID 組合
            # JID 格式：法院代碼,年度,字別,號次,裁判日期(西元YYYYMMDD),序號
            
            if court_name not in self.court_map:
                return None, f"未知的法院名稱：{court_name}"
            
            court_code = self.court_map[court_name]
            ad_date_str = date_dt.strftime("%Y%m%d") # 將 datetime 轉為 YYYYMMDD
            
            # 組合 JID 字串
            jid_raw = f"{court_code},{roc_year},{case_word},{case_no},{ad_date_str},{seq_no}"
            
            # 3. 呼叫 API 取得內容
            # POST /JDoc, body: {token, j}
            url = f"{self.base_url}/JDoc"
            payload = {
                "token": self.token,
                "j": jid_raw
            }
            
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            return result, None

        except Exception as e:
            return None, f"查詢過程發生錯誤: {str(e)}"

# ==========================================
# 前端介面：Streamlit UI
# ==========================================

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

# 2. 搜尋條件輸入區
st.markdown("### 🔍 輸入查詢條件")
st.info("請輸入判決書詳細資訊以進行精準查詢。")

with st.form("search_form"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 法院選單
        input_court = st.selectbox("法院", list(api.court_map.keys()), index=1)
        # 年度
        input_year = st.number_input("年度 (民國)", min_value=1, max_value=200, value=113)
        
    with col2:
        # 字別
        input_word = st.text_input("字別", value="重上更三", placeholder="例如：訴、上易")
        # 號次
        input_no = st.text_input("號次", value="32")
        
    with col3:
        # 日期選擇器 (回傳 datetime.date 物件)
        input_date = st.date_input("裁判日期", value=datetime.date(2025, 5, 6))
        # 序號 (預設 1)
        input_seq = st.text_input("序號", value="1", help="同一案件同一日若有多筆裁判，請調整序號")

    submitted = st.form_submit_button("🚀 開始查詢", type="primary")

# 3. 處理查詢結果
if submitted:
    with st.spinner("正在連線司法院資料庫..."):
        # 呼叫 API
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
        
        # 檢查 API 是否回傳錯誤訊息 (如查無資料)
        elif "error" in data:
            st.warning(f"⚠️ 系統回傳訊息: {data['error']}")
            st.caption("提示：請檢查日期、字號是否完全正確，或該案件可能尚未公開。")
            
        else:
            st.success("✅ 成功取得裁判書內容！")
            
            # 解析回傳欄位
            # JTITLE: 案由
            # JFULLX -> JFULLCONTENT: 全文內容
            # JFULLX -> JFULLPDF: PDF 下載連結
            
            case_title = data.get("JTITLE", "(無案由資料)")
            full_content_obj = data.get("JFULLX", {})
            text_content = full_content_obj.get("JFULLCONTENT", "內容為空")
            pdf_link = full_content_obj.get("JFULLPDF", "")
            
            # 顯示標題與基本資訊
            st.divider()
            st.subheader(f"📄 {input_court} {input_year}年度{input_word}字第{input_no}號")
            st.markdown(f"**【案由】**：{case_title}")
            st.markdown(f"**【裁判日期】**：{input_date.strftime('%Y-%m-%d')}")
            
            # 若有 PDF 連結則顯示
            if pdf_link:
                st.markdown(f"📥 **[點擊下載原始 PDF 檔案]({pdf_link})**")
            
            # 顯示全文內容
            st.markdown("#### 📜 判決全文")
            st.text_area("全文內容", text_content, height=600)
            
            # 除錯用：顯示原始 JSON 結構
            with st.expander("🛠️ 查看原始 JSON 資料 (Debug)"):
                st.json(data)