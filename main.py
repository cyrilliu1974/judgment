import os
import ssl
import urllib3
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from judicial_api import JudicialYuanAPI  # 確保此檔案存在於同目錄

# =========================================================
# SSL 強制修正區塊 (解決政府網站連線等級過低導致的錯誤)
# 核心邏輯參考自 app_law.py 原始實作
# =========================================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class UnsafeSSLAdapter(HTTPAdapter):
    """
    自定義 SSL Adapter，強制將加密等級調降至 SECLEVEL=1，
    並忽略憑證驗證，以確保能成功連線至司法院伺服器。
    """
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        # 強制設定加密演算法 (避開部分政府網站不支援新版加密的問題)
        try:
            ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        except Exception:
            # 如果系統不支援 SECLEVEL 設定，則使用預設值
            pass
            
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx
        )

# =========================================================
# FastAPI 初始化與全域設定
# =========================================================
app = FastAPI(
    title="司法院裁判書查詢 API",
    description="透過 FastAPI 封裝司法院 API，支援 Render 部署環境",
    version="1.0.0"
)

# 從 Render 環境變數中讀取帳號密碼
USER = os.getenv("JUDICIALUSER")
PWD = os.getenv("JUDICIALPWD")

if not USER or not PWD:
    print("❌ 錯誤：未設定環境變數 JUDICIALUSER 或 JUDICIALPWD，連線將失敗。")

# 初始化 API 實例並掛載 SSL 修正
# 必須確保 judicial_api.py 內使用的是 self.session
api = JudicialYuanAPI(USER, PWD)

if hasattr(api, 'session'):
    api.session.mount("https://", UnsafeSSLAdapter())
    api.session.verify = False

# =========================================================
# API 路由定義 (Endpoints)
# =========================================================

@app.get("/", tags=["Health Check"])
def health_check():
    """服務健康檢查，Render 部署時需確保此路徑可連通"""
    return {"status": "healthy", "service": "Judicial API Server"}

@app.get("/get_judgment", response_class=PlainTextResponse, tags=["Query"])
def get_judgment(
    court: str = Query(..., description="法院代碼，例如：TPH (臺灣高等法院)"),
    year: str = Query(..., description="裁判年度 (民國)，例如：112"),
    word: str = Query(..., description="字別，例如：重上更三"),
    no: str = Query(..., description="案號次，例如：32"),
    date: str = Query(..., description="裁判日期，格式 YYYYMMDD，例如：20231025"),
    seq: str = Query("1", description="序號，通常為 1")
):
    """
    🔍 查詢裁判書全文
    會將輸入參數組合成 JID 並向司法院伺服器請求內容。
    """
    try:
        # 執行核心查詢邏輯
        data, err = api.get_judgment_content(court, year, word, no, date, seq)
        
        # 處理 API 層級的連線或權限錯誤
        if err:
            raise HTTPException(status_code=400, detail=f"API 查詢錯誤：{err}")
        
        if not data:
            raise HTTPException(status_code=404, detail="司法院資料庫未回傳資料")

        # 根據原始規格提取全文內容
        content_obj = data.get("JFULLX", {})
        text_content = content_obj.get("JFULLCONTENT")
        
        # 檢查內容是否為空或包含錯誤訊息
        if not text_content:
            error_hint = data.get("error", "找不到判決書全文，請檢查字號與日期是否正確。")
            return f"系統提示：{error_hint}"
        
        return text_content

    except Exception as e:
        # 捕捉未預期的程式錯誤，避免服務崩潰
        raise HTTPException(status_code=500, detail=f"伺服器內部異常：{str(e)}")

# =========================================================
# Render 執行入口與埠號設定
# =========================================================
if __name__ == "__main__":
    import uvicorn
    # Render 會自動注入 PORT 環境變數，若無則預設為 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)