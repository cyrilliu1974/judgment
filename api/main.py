from fastapi import FastAPI, Query
from app_law import JudicialYuanAPI # 確保檔名正確
import os

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Legal API is running", "usage": "/fetch?jid=法院,年度,字別,號次,日期,序號"}

@app.get("/fetch")
def fetch_judgment(jid: str = Query(..., description="輸入完整 JID")):
    user = os.getenv("JUDICIALUSER")
    pwd = os.getenv("JUDICIALPWD")
    
    api = JudicialYuanAPI(user, pwd)
    parts = jid.split(",")
    if len(parts) != 6:
        return {"error": "JID 格式應為 6 段"}

    # 執行即時抓取
    data, err = api.get_judgment_content(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])
    
    if err:
        return {"error": err}
    
    # 直接吐出純文字全文
    full_content = data.get("JFULLX", {}).get("JFULLCONTENT", "無內容")
    return {"jid": jid, "content": full_content}