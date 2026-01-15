import streamlit as st
import requests
import datetime
import urllib3
import ssl
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
        
        # 法院代碼對照表
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

        # 初始化 Session 並掛載不安全的 Adapter
        self.session = requests.Session()
        adapter = UnsafeSSLAdapter()
        self.session.mount("https://", adapter)
        self.session.verify = False  # 全域設定不驗證 (雙重保險)

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
            # 改用 self.session 發送請求
            response = self.session.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 若成功回傳 Token，否則回傳錯誤
            if isinstance(data, dict) and "Token" in data:
                self.token = data["Token"]
                return True, "驗證成功"
            else:
                return False, data.get('error', '驗證失敗') if isinstance(data, dict) else "回傳格式錯誤"
                
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
            
            # 移除輸入可能包含的空白
            case_word = case_word.strip()
            case_no = case_no.strip()
            seq_no = seq_no.strip()
            
            # 組合 JID 字串
            jid_raw = f"{court_code},{roc_year},{case_word},{case_no},{ad_date_str},{seq_no}"
            
            # 3. 呼叫 API 取得內容
            # POST /JDoc, body: {token, j}
            url = f"{self.base_url}/JDoc"
            payload = {
                "token": self.token,
                "j": jid_raw
            }
            
            # 改用 self.session 發送請求
            response = self.session.post(url, json=payload, timeout=20)
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
# 格式: jid={法院代碼},{年度},{字別},{案號},{YYYYMMDD},{序號}
# 範例: ?jid=TPS,110,台上,123,20210101,1
params = st.query_params
if "jid" in params:
    try:
        jid_str = params["jid"]
        # 處理可能被 URL encoding 的逗號
        jid_parts = jid_str.split(",") if "," in jid_str else jid_str.split("%2C")
        
        if len(jid_parts) == 6:
            p_court_code, p_year, p_word, p_no, p_date_str, p_seq = jid_parts
            
            # 1. 反查法院名稱
            # 建立 代碼->名稱 的反向對照表
            court_map_reverse = {v: k for k, v in api.court_map.items()}
            
            # 若代碼存在於對照表中，更新 UI index
            if p_court_code in court_map_reverse:
                court_name = court_map_reverse[p_court_code]
                court_keys = list(api.court_map.keys())
                if court_name in court_keys:
                    defaults["court_index"] = court_keys.index(court_name)
            
            # 2. 設定其他欄位
            defaults["year"] = int(p_year)
            defaults["word"] = p_word
            defaults["no"] = p_no
            # 將 YYYYMMDD 字串轉為 datetime.date
            defaults["date"] = datetime.datetime.strptime(p_date_str, "%Y%m%d").date()
            defaults["seq"] = p_seq
            
            # 3. 標記自動執行
            defaults["auto_run"] = True
            st.toast(f"已偵測 URL 參數，自動搜尋：{jid_str}")
            
    except Exception as e:
        st.error(f"URL 參數解析失敗: {e}")

# 3. 搜尋表單 (使用 defaults 設定預設值)
with st.form("search_form"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 法院選單
        input_court = st.selectbox("法院", list(api.court_map.keys()), index=defaults["court_index"])
        # 年度
        input_year = st.number_input("年度 (民國)", min_value=1, max_value=200, value=defaults["year"])
        
    with col2:
        # 字別
        input_word = st.text_input("字別", value=defaults["word"], placeholder="例如：訴、上易")
        # 號次
        input_no = st.text_input("號次", value=defaults["no"])
        
    with col3:
        # 日期選擇器
        input_date = st.date_input("裁判日期", value=defaults["date"])
        # 序號
        input_seq = st.text_input("序號", value=defaults["seq"], help="同一案件同一日若有多筆裁判，請調整序號")

    submitted = st.form_submit_button("🚀 開始查詢", type="primary")

# 4. 處理查詢結果 (點擊按鈕 或 URL 自動觸發)
if submitted or defaults["auto_run"]:
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