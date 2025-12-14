# Claude 工作記錄

## 2025-12-12 - Docker 環境設置與系統啟動

### 完成項目

1. **修正配置檔案**
   - 更新 `app/common/config.py` 使其與 `.env` 檔案匹配
   - 修正欄位名稱：`secret_key` → `jwt_secret_key`, `algorithm` → `jwt_algorithm`, `access_token_expire_minutes` → `jwt_expire_minutes`
   - 更新 `app/domain/auth_service.py` 中的 settings 引用
   - 添加 `cors_origins` 的 JSON 解析器
   - 設置 `extra = "ignore"` 以忽略額外的環境變數

2. **創建資料庫 Migration**
   - 修正 `.env` 中的 `DATABASE_URL` (localhost vs postgres)
   - 生成初始 migration: `2b8d7e700652_initial_database_schema.py`
   - 建立所有資料表：users, tokens, audit_logs, fcs_files, fcs_parameters
   - 成功執行 `alembic upgrade head`

3. **Docker Compose 配置**
   - 移除過時的 `version: '3.8'`
   - 使用 YAML anchors (`x-pat-image`, `x-pat-build`) 共享配置
   - 修正 volumes driver 配置
   - 為 migration service 添加必要的環境變數 (`JWT_SECRET_KEY`)
   - 配置三個服務：
     - postgres: PostgreSQL 16 with healthcheck
     - migration: 執行 alembic upgrade
     - app: FastAPI 應用 with hot reload

4. **系統成功啟動**
   - PostgreSQL: 運行中 (port 5432)
   - FastAPI App: 運行中 (port 8000)
   - Database Migration: 已執行完成
   - API endpoints 正常回應

### API 端點驗證

- Swagger UI: http://localhost:8000/docs ✓
- ReDoc: http://localhost:8000/redoc ✓
- Health Check: http://localhost:8000/health ✓

### 遇到的問題與解決方案

1. **Config 欄位名稱不匹配**
   - 問題：pydantic-settings 從 .env 讀取的欄位名稱與 Settings 類定義不一致
   - 解決：更新 Settings 類使用正確的欄位名稱 (snake_case with prefix)

2. **DATABASE_URL 主機名稱問題**
   - 問題：本地執行 alembic 需要 localhost，Docker 內需要 postgres
   - 解決：.env 使用 localhost (本地開發)，docker-compose.yml 覆蓋使用 postgres

3. **Migration service 缺少環境變數**
   - 問題：migration service 載入 config.py 時缺少必填的 jwt_secret_key
   - 解決：在 docker-compose.yml 中為 migration service 添加 JWT_SECRET_KEY

4. **Build vs Mount 權衡**
   - 嘗試：直接掛載 source code 避免 build image
   - 結果：每次啟動都要安裝依賴，反而更慢
   - 決定：使用 Dockerfile build image，掛載 ./app 支援熱重載

### 目前架構

```
pat/
├── app/                    # 掛載到容器支援熱重載
│   ├── api/v1/            # API 路由
│   ├── common/            # 配置與資料庫
│   ├── domain/            # 業務邏輯
│   ├── models/            # SQLAlchemy models
│   ├── repository/        # 資料存取層
│   ├── usecase/           # 應用邏輯層
│   └── main.py
├── migrations/            # Alembic migrations
├── uploads/               # FCS 檔案上傳目錄
├── docker-compose.yml     # 服務編排
├── Dockerfile             # 應用程式映像
├── .env                   # 環境變數 (本地)
└── .env.example          # 環境變數範例
```

### 下一步

系統已完全就緒，可以進行以下測試：
- 用戶註冊與登入
- PAT Token 管理
- 權限控制驗證
- FCS 檔案上傳與分析

## 2025-12-13 - Rate Limiting 實作

### 完成項目

1. **Rate Limiting 設置**
   - 使用 slowapi 實作 rate limiting
   - 基於 IP 地址的速率限制
   - 設定為每分鐘 60 次請求（可透過 .env 配置）
   - 創建 `app/common/rate_limit.py` 統一管理

2. **應用到關鍵 Endpoints**
   - Auth API (register, login) - 防止暴力攻擊
   - Tokens API (create_token) - 防止濫用
   - 其他 endpoints 因需要 JWT/PAT 認證，已有基本保護

3. **pgAdmin 自動配置**
   - 創建 pgadmin-servers.json 預設伺服器配置
   - 創建 pgadmin-pgpass 密碼檔案
   - 自動在首次啟動時載入 PostgreSQL 連接
   - 添加 pgadmin_data volume 持久化資料

### 實作細節

**Rate Limiting 配置**
```python
# app/common/rate_limit.py
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"]
)
```

**使用方式**
```python
@router.post("/auth/register")
@limiter.limit("60/minute")
async def register(request_obj: Request, ...):
    ...
```

### 目前進度

根據原始 10 階段計畫：
- ✅ Phase 1-7: 基礎架構、Models、Domain、Repository、Usecase、API、Migration、Docker
- ✅ Phase 8: Rate Limiting 實作
- ⏳ Phase 9: 測試（待執行）
- ⏳ Phase 10: 文檔與部署（待完成）

**完成度：約 80%**

## 2025-12-14 - Transaction Management 重構與 Rate Limiting 全局化

### 完成項目

1. **Rate Limiting 全局化**
   - 將 rate limiting 從僅 auth/token 的 3 個 endpoints 擴展到所有 17 個 API endpoints
   - 統一使用 60 requests/minute 限制
   - 實作自訂 429 response 格式，符合設計文件規範
   - 從 slowapi 提取實際 retry_after 時間

   **修改檔案：**
   - `app/api/v1/auth.py` - 2 endpoints
   - `app/api/v1/tokens.py` - 5 endpoints
   - `app/api/v1/workspaces.py` - 4 endpoints
   - `app/api/v1/users.py` - 2 endpoints
   - `app/api/v1/fcs.py` - 4 endpoints

2. **Transaction Management 架構重構**

   **問題診斷：**
   - 發現 `create_token` endpoint 失敗原因：dependency `get_current_user_from_jwt()` 中的 `authenticate_jwt()` 執行 DB query 觸發 autobegin
   - 當 usecase 再次嘗試 `session.begin()` 時報錯：`A transaction is already begun on this Session`

   **解決方案：**
   - 將**所有** DB operations 包在 `async with session.begin():` 中（包括只讀操作）
   - 遵循最小化 transaction scope 原則：
     - ✅ DB operations 在 transaction 內
     - ✅ 業務邏輯、驗證、計算在 transaction 外

   **重構內容：**

   a. **簡化 `get_db()`**
   ```python
   async def get_db() -> AsyncSession:
       async with async_session_maker() as session:
           yield session
   ```
   - 移除冗余的 `session.close()`（context manager 自動處理）
   - 移除 try-except-finally 塊

   b. **auth_usecase.py 重構**
   - `register()` - hash password 在外，create user 在 transaction 中
   - `login()` - DB query 在 transaction 中，密碼驗證和 JWT 生成在外
   - `authenticate_jwt()` - DB query 在 transaction 中，驗證在外
   - `authenticate_pat()` - 所有 DB operations（驗證 token、獲取 user、更新 last_used）在同一 transaction
   - `_log_failed_access()` - 已使用獨立 transaction

   c. **token_usecase.py 重構**
   - `create_token()` - scope 驗證和過期時間計算在外，DB create 在 transaction 中
   - `list_tokens()` - DB query 在 transaction 中，數據轉換在外
   - `get_token()` - DB query 在 transaction 中，權限驗證在外
   - `revoke_token()` - 讀取和撤銷在同一 transaction（確保原子性）
   - `get_token_logs()` - 所有 DB queries 在 transaction 中，格式化響應在外
   - `log_token_usage()` - 已使用獨立 transaction

3. **測試驗證**
   - ✅ 用戶註冊與登入
   - ✅ PAT token 創建
   - ✅ PAT token 認證與授權
   - ✅ Token 撤銷
   - ✅ 撤銷的 token 無法使用
   - ✅ Rate limiting (60/minute)
   - ✅ 無 autobegin 衝突

### 技術要點

**Transaction Management 最佳實踐：**
1. 所有 DB operations 必須包在 `session.begin()` 中
2. 最小化 transaction scope - 只包含必要的 DB operations
3. 業務邏輯、驗證、計算放在 transaction 外
4. 相關的多個 DB operations 應在同一 transaction 中（確保原子性）
5. 獨立的 audit logging 使用獨立 transaction

**避免 Autobegin 的關鍵：**
- SQLAlchemy async session 在第一次 DB operation 時會自動開始 transaction（autobegin）
- 如果某處 DB operation 觸發了 autobegin，後續的 `session.begin()` 會失敗
- 解決方案：確保所有 DB operations 都顯式包在 `session.begin()` 中

### Commits

1. `88eb8bb` - Apply rate limiting to all API endpoints
2. `0f9f3b8` - Refactor transaction management with minimal scope

### 架構優勢

1. **明確的 Transaction 邊界** - 所有 DB operations 顯式管理
2. **性能優化** - Transaction scope 最小化，減少鎖定時間
3. **代碼清晰** - DB 操作和業務邏輯明確分離
4. **自動管理** - Auto-commit on success, auto-rollback on exceptions
5. **防止錯誤** - 避免 autobegin 衝突和 transaction 管理錯誤

### 目前進度

根據原始 10 階段計畫：
- ✅ Phase 1-7: 基礎架構、Models、Domain、Repository、Usecase、API、Migration、Docker
- ✅ Phase 8: Rate Limiting 實作與測試
- ⏳ Phase 9: 測試（功能測試已完成，單元測試待實作）
- ⏳ Phase 10: 文檔與部署

**完成度：約 85%**
