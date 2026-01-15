from fastapi import FastAPI, Query
from ..app_law import JudicialYuanAPI # 引用您的核心邏輯
import os

app = FastAPI()

@app.get("/fetch")
def fetch_judgment(jid: str = Query(..., description="輸入完整 JID")):
    # 從 Vercel 環境變數讀取帳密
    user = os.getenv("JUDICIALUSER")
    pwd = os.getenv("JUDICIALPWD")
    
    api = JudicialYuanAPI(user, pwd)
    parts = jid.split(",")
    if len(parts) != 6:
        return {"error": "JID 格式應為 6 段"}

    data, err = api.get_judgment_content(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])
    if err: return {"error": err}
    
    return {"content": data.get("JFULLX", {}).get("JFULLCONTENT", "無內容")}