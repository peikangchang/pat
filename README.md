# PAT 權限控管系統

個人存取權杖 (Personal Access Token) 權限控管系統，提供細緻的 API 存取控制。

## 功能特性

- 使用者註冊與登入（JWT）
- PAT Token 管理（建立、撤銷、查看）
- 階層式權限控制（workspaces, users, fcs）
- Audit Log 記錄所有 API 存取
- FCS 檔案上傳與分析

## 快速開始

### 使用 Docker Compose（推薦）

1. **複製環境變數範例**
```bash
cp .env.example .env
```

2. **編輯 `.env` 檔案，設定安全的密碼和金鑰**
```bash
# 至少修改以下項目：
# - POSTGRES_PASSWORD
# - JWT_SECRET_KEY (至少 32 字元)
vim .env
```

3. **啟動所有服務**
```bash
docker-compose up -d
```

這會啟動：
- PostgreSQL 資料庫（port 5432）
- 自動執行 database migration
- FastAPI 應用程式（port 8000）

4. **查看 logs**
```bash
docker-compose logs -f app
```

5. **訪問 API 文檔**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 啟動 pgAdmin（資料庫管理界面）

```bash
docker-compose --profile tools up -d pgadmin
```

訪問 http://localhost:5050，使用 `.env` 中設定的帳密登入。

### 本地開發（不使用 Docker）

1. **建立 conda 環境**
```bash
conda create -n pat python=3.12
conda activate pat
```

2. **安裝依賴**
```bash
pip install -r requirements.txt
```

3. **設定環境變數**
```bash
cp .env.example .env
# 編輯 .env，修改 DATABASE_URL 為本地資料庫
```

4. **啟動 PostgreSQL**（使用 Docker 或本地安裝）
```bash
# 使用 Docker 啟動資料庫
docker-compose up -d postgres
```

5. **執行 migration**
```bash
alembic upgrade head
```

6. **啟動應用程式**
```bash
uvicorn app.main:app --reload
```

## API 使用範例

### 1. 註冊使用者
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "securepassword"
  }'
```

### 2. 登入取得 JWT
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepassword"
  }'
```

### 3. 建立 PAT Token
```bash
curl -X POST "http://localhost:8000/api/v1/tokens" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My API Token",
    "scopes": ["workspaces:read", "fcs:write"],
    "expires_in_days": 30
  }'
```

### 4. 使用 PAT 存取 API
```bash
curl -X GET "http://localhost:8000/api/v1/workspaces" \
  -H "Authorization: Bearer YOUR_PAT_TOKEN"
```

## 權限說明

### 階層式權限
- **workspaces**: `admin` > `delete` > `write` > `read`
- **users**: `write` > `read`
- **fcs**: `analyze` > `write` > `read`

高階權限包含所有低階權限。例如：`workspaces:admin` 包含 `delete`、`write`、`read`。

## Docker 指令參考

```bash
# 啟動所有服務
docker-compose up -d

# 查看 logs
docker-compose logs -f

# 停止所有服務
docker-compose down

# 停止並刪除資料（包含資料庫資料）
docker-compose down -v

# 重建 image
docker-compose build

# 只啟動特定服務
docker-compose up -d postgres

# 進入容器
docker-compose exec app bash
docker-compose exec postgres psql -U pat_user -d pat_db

# 執行 migration
docker-compose run --rm migration alembic upgrade head

# 建立新的 migration
docker-compose run --rm migration alembic revision --autogenerate -m "description"
```

## 開發指令

```bash
# 執行測試
pytest

# 檢查程式碼格式
ruff check .

# 格式化程式碼
ruff format .

# 建立新的 migration
alembic revision --autogenerate -m "description"

# 執行 migration
alembic upgrade head

# 回退 migration
alembic downgrade -1
```

## 專案結構

詳見 [ARCHITECTURE.md](ARCHITECTURE.md)

## License

MIT
