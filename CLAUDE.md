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
