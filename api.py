from fastapi import FastAPI, Query
from app_law import JudicialYuanAPI # 引用您原本寫好的 API 類別
import os

app = FastAPI()

@app.get("/fetch")
def fetch_judgment(jid: str = Query(..., description="法院,年度,字別,號次,日期,序號")):
    # 從環境變數讀取帳密 (Vercel 設定中提供)
    user = os.getenv("JUDICIALUSER")
    pwd = os.getenv("JUDICIALPWD")
    
    api = JudicialYuanAPI(user, pwd)
    parts = jid.split(",")
    if len(parts) != 6:
        return {"error": "JID 格式錯誤"}

    # 調用您原本的函數
    data, err = api.get_judgment_content(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])
    
    if err:
        return {"error": err}
    
    # 僅回傳 AI 需要的純文字內容
    content = data.get("JFULLX", {}).get("JFULLCONTENT", "內容為空")
    return {"jid": jid, "content": content}