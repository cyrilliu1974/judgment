import requests
import datetime

class JudicialYuanAPI:
    def __init__(self, user, password):
        self.base_url = "https://data.judicial.gov.tw/jdg/api"
        self.user = user
        self.password = password
        self.token = None
        self.session = requests.Session()  # 關鍵：建立連線池
        
        self.court_map = {
            "最高法院": "TPS", "臺灣高等法院": "TPHM", "臺中高分院": "TCH",
            "高雄高分院": "KSH", "臺北地方法院": "TPD", "新北地方法院": "PCD",
            "臺中地方法院": "TCD", "高雄地方法院": "KSD"
        }

    def authenticate(self):
        url = f"{self.base_url}/Auth"
        payload = {"user": self.user, "password": self.password}
        try:
            response = self.session.post(url, json=payload, timeout=10) # 使用 session
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "Token" in data:
                self.token = data["Token"]
                return True, "驗證成功"
            return False, data.get('error', '驗證失敗')
        except Exception as e:
            return False, f"連線錯誤: {str(e)}"

    def get_judgment_content(self, court, year, word, no, date, seq="1"):
        if not self.token:
            success, msg = self.authenticate()
            if not success: return None, msg
        try:
            # 支援法院名稱轉代碼
            court_code = self.court_map.get(court, court)
            # 格式化日期 YYYYMMDD
            if isinstance(date, (datetime.date, datetime.datetime)):
                fmt_date = date.strftime("%Y%m%d")
            else:
                fmt_date = str(date).replace("-", "").replace("/", "")
            
            jid = f"{court_code},{year},{word.strip()},{no.strip()},{fmt_date},{seq.strip()}"
            
            payload = {"token": self.token, "j": jid}
            response = self.session.post(f"{self.base_url}/JDoc", json=payload, timeout=20)
            response.raise_for_status()
            return response.json(), None
        except Exception as e:
            return None, str(e)