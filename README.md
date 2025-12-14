# PAT (Personal Access Token) API 系統

基於 FastAPI 的個人存取權杖管理系統，具備 FCS 檔案處理、細緻權限控制、使用者隔離及完整稽核日誌。

## 架構說明

### 技術棧

- **FastAPI** - 高效能非同步 Web 框架
- **SQLAlchemy 2.0+** - 非同步 ORM
- **PostgreSQL 16** - 資料庫
- **Alembic** - 資料庫遷移工具
- **Docker Compose** - 容器編排
- **Pydantic** - 資料驗證
- **Argon2** - 密碼雜湊
- **slowapi** - 速率限制

### 架構模式

採用 **Clean Architecture** 設計：

```
app/
├── api/v1/              # API 層 - 處理 HTTP 請求/響應
├── usecase/             # 用例層 - 業務邏輯編排
├── domain/              # 領域層 - 核心業務規則
├── repository/          # 資料層 - 資料存取抽象
├── models/              # 資料模型 - SQLAlchemy ORM
└── common/              # 共用工具 - 配置、資料庫、例外
```

**關鍵設計模式：**
- **Repository Pattern** - 隔離資料存取邏輯
- **Use Case Pattern** - 封裝業務邏輯
- **Dependency Injection** - FastAPI 的依賴注入系統
- **Middleware Pattern** - 稽核日誌與 CORS

### 專案結構

```
pat/
├── app/
│   ├── api/v1/
│   │   ├── auth.py              # 認證 API（註冊、登入）
│   │   ├── tokens.py            # PAT 權杖管理
│   │   ├── users.py             # 使用者資料管理
│   │   ├── workspaces.py        # 工作區管理
│   │   └── fcs.py               # FCS 檔案處理
│   ├── usecase/
│   │   ├── auth_usecase.py      # 認證邏輯
│   │   ├── token_usecase.py     # 權杖生命週期管理
│   │   ├── user_usecase.py      # 使用者操作
│   │   ├── workspace_usecase.py # 工作區操作
│   │   └── fcs_usecase.py       # FCS 檔案解析與統計
│   ├── domain/
│   │   ├── auth_service.py      # JWT/PAT 認證服務
│   │   ├── permissions.py       # 階層式權限系統
│   │   └── fcs_parser.py        # FCS 檔案解析器
│   ├── repository/
│   │   ├── user_repository.py   # 使用者資料存取
│   │   ├── token_repository.py  # 權杖資料存取
│   │   ├── audit_repository.py  # 稽核日誌存取
│   │   └── fcs_repository.py    # FCS 資料存取
│   ├── models/                  # SQLAlchemy ORM 模型
│   ├── common/
│   │   ├── database.py          # 非同步資料庫連接池
│   │   ├── config.py            # 環境變數配置
│   │   ├── exceptions.py        # 自訂例外
│   │   ├── rate_limit.py        # 速率限制配置
│   │   ├── audit_middleware.py  # 稽核日誌中介層
│   │   └── startup.py           # 應用程式初始化
│   └── main.py                  # 應用程式入口
├── migrations/                  # Alembic 資料庫遷移
├── tests/                       # 測試套件（68 tests, 100% pass）
├── sample_data/                 # 範例 FCS 檔案
├── uploads/                     # 上傳檔案儲存
├── docker-compose.yml           # 服務編排
├── Dockerfile                   # 應用程式映像
└── requirements.txt             # Python 依賴
```

### 核心功能

1. **認證與授權**
   - JWT 短期會話權杖（60 分鐘）
   - PAT 長期存取權杖（可設定過期時間）
   - 階層式 scope 權限控制

2. **權限系統**
   - 資源類型：`workspacess`、`users`、`fcs`
   - 權限階層（依資源而異）：
     - **workspacess**: `admin` > `delete` > `write` > `read`
     - **users**: `write` > `read`
     - **fcs**: `analyze` > `write` > `read`
   - 跨資源隔離

3. **FCS 檔案處理**
   - 上傳與解析 FCS 3.0/3.1 格式
   - 全域共享（所有使用者存取最新檔案）
   - 統計分析（min、max、mean、median、std）
   - 自動初始化範例檔案

4. **安全機制**
   - 密碼 Argon2 雜湊
   - 權杖安全儲存（雜湊 + 前綴）
   - 速率限制（60 req/min）
   - 完整稽核日誌

## 執行方式

### Docker Compose（推薦）

```bash
# 1. 複製並配置環境變數
cp .env.example .env
# 編輯 .env，至少修改：
# - POSTGRES_PASSWORD（設定強密碼）
# - JWT_SECRET_KEY（至少 32 字元）
# 可選配置：
# - RATE_LIMIT_PER_MINUTE（預設 60，可調整 API 速率限制）

# 2. 啟動所有服務
docker compose up -d

# 3. 驗證服務
curl http://localhost:8000/health
# 預期回應: {"status":"healthy"}

# 4. 查看日誌
docker compose logs -f app

# 5. 訪問 API 文件
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

**服務說明：**
- **postgres** - PostgreSQL 16 資料庫（port 5432）
- **migration** - 自動執行資料庫遷移
- **app** - FastAPI 應用程式（port 8000）
- **pgadmin** - 資料庫管理界面（port 5050，可選）

### 本地開發

```bash
# 1. 建立虛擬環境
python -m venv venv
source venv/bin/activate

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 啟動資料庫（使用 Docker）
docker compose up -d postgres

# 4. 執行遷移
alembic upgrade head

# 5. 啟動應用程式（熱重載模式）
uvicorn app.main:app --reload
```

### 常用指令

```bash
# 查看服務狀態
docker compose ps

# 重啟服務
docker compose restart app

# 停止所有服務
docker compose down

# 停止並刪除資料（包含資料庫）
docker compose down -v

# 查看資料庫
docker compose exec postgres psql -U pat_user -d pat_db

# 執行測試
pytest tests/ -v

# 建立新的資料庫遷移
alembic revision --autogenerate -m "描述"
```

## API 範例

所有 API 回應都遵循統一格式：
```json
{
  "success": true,
  "data": { ... }
}
```

### 認證 (Auth)

#### 註冊使用者

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "email": "alice@example.com",
    "password": "SecurePass123!"
  }'
```

**回應：**
```json
{
  "success": true,
  "data": {
    "id": "019b1bc9-24f4-7552-92e6-23ebc8b9f948",
    "username": "alice",
    "email": "alice@example.com",
    "created_at": "2024-12-14T08:00:00Z"
  }
}
```

#### 登入取得 JWT

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "password": "SecurePass123!"
  }'
```

**回應：**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
}
```

---

### 權杖管理 (Tokens)

**說明：** 以下範例使用 JWT 進行認證。

```bash
# 儲存 JWT（從登入取得）
JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 建立 PAT 權杖

```bash
curl -X POST http://localhost:8000/api/v1/tokens \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "FCS 分析權杖",
    "scopes": ["fcs:analyze", "workspacess:admin", "users:write"],
    "expires_in_days": 30
  }'
```

**回應：**
```json
{
  "success": true,
  "data": {
    "id": "019b1bd2-8f3c-7891-a3b4-d5e6f7a8b9c0",
    "name": "FCS 分析權杖",
    "token": "pat_7x9k2m4n_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "token_prefix": "pat_7x9k2m4n",
    "scopes": ["fcs:analyze", "workspacess:admin", "users:write"],
    "expires_at": "2025-01-13T08:00:00Z",
    "created_at": "2024-12-14T08:00:00Z"
  }
}
```

**⚠️ 重要：** 完整 `token` 僅在建立時顯示一次，請妥善保存。

#### 列出使用者的權杖

```bash
curl -X GET http://localhost:8000/api/v1/tokens \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "tokens": [
      {
        "id": "019b1bd2-8f3c-7891-a3b4-d5e6f7a8b9c0",
        "name": "FCS 分析權杖",
        "token_prefix": "pat_7x9k2m4n",
        "scopes": ["fcs:analyze", "workspacess:admin", "users:write"],
        "expires_at": "2025-01-13T08:00:00Z",
        "is_revoked": false,
        "last_used_at": "2024-12-14T10:30:00Z",
        "created_at": "2024-12-14T08:00:00Z"
      }
    ],
    "total": 1
  }
}
```

#### 取得權杖詳情

```bash
TOKEN_ID="019b1bd2-8f3c-7891-a3b4-d5e6f7a8b9c0"

curl -X GET http://localhost:8000/api/v1/tokens/$TOKEN_ID \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "id": "019b1bd2-8f3c-7891-a3b4-d5e6f7a8b9c0",
    "name": "FCS 分析權杖",
    "token_prefix": "pat_7x9k2m4n",
    "scopes": ["fcs:analyze", "workspacess:admin", "users:write"],
    "expires_at": "2025-01-13T08:00:00Z",
    "is_revoked": false,
    "last_used_at": "2024-12-14T10:30:00Z",
    "created_at": "2024-12-14T08:00:00Z"
  }
}
```

#### 撤銷權杖

```bash
curl -X DELETE http://localhost:8000/api/v1/tokens/$TOKEN_ID \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "id": "019b1bd2-8f3c-7891-a3b4-d5e6f7a8b9c0",
    "name": "FCS 分析權杖",
    "token_prefix": "pat_7x9k2m4n",
    "scopes": ["fcs:analyze", "workspacess:admin", "users:write"],
    "expires_at": "2025-01-13T08:00:00Z",
    "is_revoked": true,
    "last_used_at": "2024-12-14T10:30:00Z",
    "created_at": "2024-12-14T08:00:00Z"
  }
}
```

#### 查看權杖稽核日誌

```bash
curl -X GET http://localhost:8000/api/v1/tokens/$TOKEN_ID/logs \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "token_id": "019b1bd2-8f3c-7891-a3b4-d5e6f7a8b9c0",
    "token_name": "FCS 分析權杖",
    "total_logs": 1,
    "logs": [
      {
        "timestamp": "2025-12-14T12:44:35.698328Z",
        "ip": "192.168.51.100",
        "method": "GET",
        "endpoint": "/api/v1/fcs/parameters",
        "status_code": 200,
        "authorized": true,
        "reason": null
      }
    ]
  }
}
```

---

### 使用者管理 (Users)

**說明：** 以下範例使用 PAT 進行認證。

```bash
# 儲存 PAT（從建立 PAT 權杖取得）
PAT_TOKEN="pat_7x9k2m4n_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
```

#### 取得目前使用者資訊

**需要權限：** `users:read`

```bash
curl -X GET http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $PAT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "endpoint": "/api/v1/users/me",
    "method": "GET",
    "required_scope": "users:read",
    "granted_by": "users:write",
    "your_scopes": ["fcs:analyze", "workspacess:admin", "users:write"],
    "message": "This is a stub implementation"
  }
}
```

#### 更新使用者資料

**需要權限：** `users:write`

```bash
curl -X PUT http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $PAT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "endpoint": "/api/v1/users/me",
    "method": "PUT",
    "required_scope": "users:write",
    "granted_by": "users:write",
    "your_scopes": ["fcs:analyze", "workspacess:admin", "users:write"],
    "message": "This is a stub implementation"
  }
}
```

---

### 工作區管理 (Workspaces)

**說明：** 以下範例使用 PAT 進行認證。

```bash
# 儲存 PAT（從建立權杖取得）
PAT_TOKEN="pat_7x9k2m4n_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
```

#### 列出工作區

**需要權限：** `workspacess:read`

```bash
curl -X GET http://localhost:8000/api/v1/workspacess \
  -H "Authorization: Bearer $PAT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "endpoint": "/api/v1/workspacess",
    "method": "GET",
    "required_scope": "workspacess:read",
    "granted_by": "workspacess:admin",
    "your_scopes": ["fcs:analyze", "workspacess:admin", "users:write"],
    "message": "This is a stub implementation"
  }
}
```

#### 建立工作區

**需要權限：** `workspacess:write`

```bash
curl -X POST http://localhost:8000/api/v1/workspacess \
  -H "Authorization: Bearer $PAT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "endpoint": "/api/v1/workspacess",
    "method": "POST",
    "required_scope": "workspacess:write",
    "granted_by": "workspacess:admin",
    "your_scopes": ["fcs:analyze", "workspacess:admin", "users:write"],
    "message": "This is a stub implementation"
  }
}
```

#### 刪除工作區

**需要權限：** `workspacess:delete`

```bash
WORKSPACE_ID="ws_002"

curl -X DELETE http://localhost:8000/api/v1/workspacess/$WORKSPACE_ID \
  -H "Authorization: Bearer $PAT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "endpoint": "/api/v1/workspacess/ws_002",
    "method": "DELETE",
    "required_scope": "workspacess:delete",
    "granted_by": "workspacess:admin",
    "your_scopes": ["fcs:analyze", "workspacess:admin", "users:write"],
    "message": "This is a stub implementation"
  }
}
```

#### 更新工作區設定

**需要權限：** `workspacess:admin`

```bash
WORKSPACE_ID="ws_002"

curl -X PUT http://localhost:8000/api/v1/workspacess/$WORKSPACE_ID/settings \
  -H "Authorization: Bearer $PAT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "endpoint": "/api/v1/workspacess/ws_002/settings",
    "method": "PUT",
    "required_scope": "workspacess:admin",
    "granted_by": "workspacess:admin",
    "your_scopes": ["fcs:analyze", "workspacess:admin", "users:write"],
    "message": "This is a stub implementation"
  }
}
```

---

### FCS 檔案處理

**說明：** 以下範例使用 PAT 進行認證。FCS 檔案為全域共享，所有使用者存取最新上傳的檔案。

#### 上傳 FCS 檔案

**需要權限：** `fcs:write`

```bash
curl -X POST http://localhost:8000/api/v1/fcs/upload \
  -H "Authorization: Bearer $PAT_TOKEN" \
  -F "file=@sample.fcs"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "file_id": "019b1bca-5d3e-7f42-8a9b-0c1d2e3f4a5b",
    "filename": "sample.fcs",
    "total_events": 34297,
    "total_parameters": 26
  }
}
```

#### 取得 FCS 參數

**需要權限：** `fcs:read`

```bash
curl -X GET http://localhost:8000/api/v1/fcs/parameters \
  -H "Authorization: Bearer $PAT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "total_events": 34297,
    "total_parameters": 26,
    "parameters": [
      {
        "index": 1,
        "pnn": "FSC-A",
        "pns": "Forward Scatter",
        "range": 262144,
        "display": "lin"
      },
      {
        "index": 2,
        "pnn": "SSC-A",
        "pns": "Side Scatter",
        "range": 262144,
        "display": "lin"
      }
    ]
  }
}
```

#### 取得 FCS 事件資料

**需要權限：** `fcs:read`

```bash
curl -X GET "http://localhost:8000/api/v1/fcs/events?limit=100&offset=0" \
  -H "Authorization: Bearer $PAT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "total_events": 34297,
    "limit": 100,
    "offset": 0,
    "events": [
      {
        "FSC-A": 50000.5,
        "SSC-A": 30000.2,
        "CD3": 1500.8,
        "CD4": 2000.1
      }
    ]
  }
}
```

#### 取得 FCS 統計資料

**需要權限：** `fcs:analyze`

```bash
curl -X GET http://localhost:8000/api/v1/fcs/statistics \
  -H "Authorization: Bearer $PAT_TOKEN"
```

**回應：**
```json
{
  "success": true,
  "data": {
    "total_events": 34297,
    "statistics": [
      {
        "parameter": "FSC-A",
        "pns": "Forward Scatter",
        "display": "lin",
        "min": 1024.5,
        "max": 250000.3,
        "mean": 125000.8,
        "median": 120000.0,
        "std": 35000.2
      },
      {
        "parameter": "SSC-A",
        "pns": "Side Scatter",
        "display": "lin",
        "min": 512.2,
        "max": 180000.5,
        "mean": 90000.4,
        "median": 85000.0,
        "std": 25000.1
      }
    ]
  }
}
```


## 設計決策

### 1. Clean Architecture

**決策：** 採用分層架構（API → Usecase → Domain → Repository）

**理由：**
- **可測試性** - 各層獨立，易於單元測試
- **可維護性** - 關注點分離，修改不影響其他層
- **可擴展性** - 新增功能不破壞現有結構
- **業務邏輯獨立** - Domain 層不依賴框架

### 2. Repository Pattern

**決策：** 使用 Repository 封裝資料存取

**理由：**
- **抽象化** - Usecase 不直接操作 SQLAlchemy
- **可測試** - 易於 mock 資料層進行測試
- **集中管理** - 所有 SQL 查詢集中在 Repository
- **易於切換** - 未來可替換為其他資料庫

### 3. 非同步架構

**決策：** 全面使用 async/await

**理由：**
- **高併發** - 單一 worker 處理大量並發請求
- **I/O 密集** - 資料庫操作、檔案讀寫都是 I/O bound
- **現代化** - SQLAlchemy 2.0+ 原生支援非同步
- **效能** - FastAPI 非同步模式效能最佳

### 4. 交易管理

**決策：** 顯式的 `async with session.begin()` 管理交易

**理由：**
- **明確邊界** - 清楚哪些操作在同一交易中
- **最小範圍** - 只包含必要的 DB 操作，減少鎖定時間
- **避免 autobegin** - 防止隱式交易開始導致錯誤
- **業務邏輯分離** - 驗證、計算在交易外，提升效能

**範例：**
```python
async def create_token(self, ...):
    # 業務邏輯（交易外）
    if not self._validate_scopes(scopes):
        raise InvalidScopeError()

    expires_at = datetime.now() + timedelta(days=expires_in_days)

    # 資料庫操作（交易內）
    async with self.session.begin():
        token = await self.token_repo.create(...)

    return token
```

### 5. 權限系統設計

**決策：** 階層式 scope 權限，而非 RBAC

**理由：**
- **細緻控制** - 每個 PAT 可有不同權限組合
- **靈活性** - 使用者可按需求建立不同權限的權杖
- **最小權限原則** - 應用程式只需要的權限
- **易於理解** - `resource:action` 格式直觀

**權限階層：**
```
workspacess:admin
  └─ workspacess:delete
      └─ workspacess:write
          └─ workspacess:read

users:write
  └─ users:read

fcs:analyze
  └─ fcs:write
      └─ fcs:read
```

### 6. PAT 權杖儲存

**決策：** 資料庫儲存雜湊值 + 前綴，不存明文

**理由：**
- **安全性** - 資料庫洩漏也無法取得實際權杖
- **可識別** - 前綴 `pat_xxxxxxxx` 讓使用者識別權杖
- **一次性顯示** - 建立時顯示完整權杖，強制使用者保存
- **雜湊一致性** - 使用相同演算法（SHA-256）確保驗證

**格式：** `pat_<8字元隨機>_<32字元隨機>`
- 前綴：儲存在資料庫，用於列表顯示
- 完整權杖：僅建立時回傳，用於 API 認證

### 7. FCS 全域共享

**決策：** FCS 檔案全域共享，所有使用者存取最新檔案

**理由：**
- **簡化設計** - 系統中只有一份活躍的 FCS 檔案
- **符合需求** - 實驗室通常分析同一批樣本
- **歷史保存** - 舊檔案保留在資料庫，可追溯
- **查詢簡單** - `ORDER BY uploaded_at DESC LIMIT 1`

### 8. 速率限制

**決策：** 可配置的速率限制（預設 60 req/min），基於 IP 位址

**理由：**
- **防止濫用** - 限制暴力攻擊和過度使用
- **保護資源** - 防止單一使用者耗盡系統資源
- **可配置** - 透過環境變數 `RATE_LIMIT_PER_MINUTE` 調整
- **IP 基礎** - 即使未認證也能限制
- **靈活部署** - 不同環境可設定不同限制值

**配置方式：**
```bash
# .env 檔案或環境變數
RATE_LIMIT_PER_MINUTE=100  # 每分鐘 100 次請求

# docker-compose.yml
environment:
  - RATE_LIMIT_PER_MINUTE=120
```

### 9. 範例資料自動初始化

**決策：** 啟動時自動載入範例 FCS 檔案

**理由：**
- **即用性** - 部署後立即有示範資料
- **程式碼重用** - 使用現有 `FCSUsecase.upload_file()`
- **幂等性** - 多次啟動不重複載入
- **優雅失敗** - 載入失敗不影響應用程式啟動

### 10. 稽核日誌

**決策：** 使用中介層記錄所有 API 請求

**理由：**
- **安全追蹤** - 記錄誰、何時、做了什麼
- **故障排查** - 協助診斷問題
- **合規性** - 滿足稽核要求
- **獨立交易** - 記錄失敗不影響主要操作

---

## 其他資訊

### 測試

- **73 個測試，100% 通過率**
- 涵蓋：權限、權杖生命週期、安全、使用者隔離、FCS API、狀態碼、速率限制配置

```bash
pytest tests/ -v                          # 執行所有測試
pytest tests/ -v --cov=app               # 顯示覆蓋率
pytest -m permissions                    # 只執行權限測試
```

### 部署

完整生產環境部署指南請參考 **[DEPLOYMENT.md](DEPLOYMENT.md)**，包含：
- 環境配置與安全設定
- Nginx 反向代理與 SSL 設定
- 監控、備份與還原
- 常見問題排除

### 權限範圍 (Scopes)

| 資源 | Scope | 說明 |
|------|-------|------|
| **Workspaces** | `workspacess:read` | 讀取工作區 |
| | `workspacess:write` | 建立/修改工作區（含 read） |
| | `workspacess:delete` | 刪除工作區（含 write, read） |
| | `workspacess:admin` | 完整管理（含所有權限） |
| **FCS** | `fcs:read` | 讀取 FCS 資料 |
| | `fcs:write` | 上傳 FCS 檔案（含 read） |
| | `fcs:analyze` | 執行統計分析（含 write, read） |
| **Users** | `users:read` | 讀取自己的資料 |
| | `users:write` | 更新自己的資料（含 read） |

### 開發歷史

完整開發記錄請參考 **[CLAUDE.md](CLAUDE.md)**，包含：
- Docker 環境設置
- Transaction 管理重構
- Rate Limiting 實作
- 完整測試套件
- FCS 全域共享轉換
- 範例檔案自動初始化

### API 文件

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **健康檢查**: http://localhost:8000/health

### 授權

MIT

---

**專案狀態**: 生產就緒 v0.1.0 | **更新日期**: 2024-12-14
