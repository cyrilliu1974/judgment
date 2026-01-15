import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query
from judicial_api import JudicialYuanAPI 

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Legal API is Online", "instruction": "Use /fetch?jid=..."}

@app.get("/fetch")
def fetch(jid: str = Query(..., description="法院,年度,字別,案號,日期,序號")):
    user = os.getenv("JUDICIALUSER")
    pwd = os.getenv("JUDICIALPWD")
    
    api = JudicialYuanAPI(user, pwd)
    parts = jid.split(",")
    if len(parts) != 6:
        return {"error": "Invalid JID format"}

    data, err = api.get_judgment_content(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])
    if err:
        return {"error": err}
    
    # 僅回傳純文字內容，讓 AI 夥伴好讀取
    return {"content": data.get("JFULLX", {}).get("JFULLCONTENT", "No content")}