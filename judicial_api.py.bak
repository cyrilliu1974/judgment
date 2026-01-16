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
            # 發送 POST 請求驗證 (設定 timeout 避免卡住)
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
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
            
            # 處理日期格是：如果是 datetime 物件則轉字串，字串則直接使用
            if isinstance(date_dt, str):
                ad_date_str = date_dt.replace("-", "").replace("/", "")
            else:
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
            
            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
            result = response.json()
            
            return result, None

        except Exception as e:
            return None, f"查詢過程發生錯誤: {str(e)}"
