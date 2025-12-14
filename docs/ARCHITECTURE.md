# PAT 權限控管系統 - 架構設計文檔

## 專案概述

**目標**: 建立一個 PAT (Personal Access Token) 權限控管系統

**核心功能**:
1. 使用者登入 → 取得 JWT session token
2. 使用 JWT token → 建立 PAT
3. 使用 PAT → 存取受保護資源（workspaces, users, fcs）

## 技術架構

### 技術選型
- **框架**: FastAPI
- **資料庫**: PostgreSQL + SQLAlchemy (async)
- **Migration**: Alembic
- **認證**: JWT (session) + PAT (API access)
- **密碼**: Argon2
- **Token**: SHA-256 hash
- **ID**: UUIDv7 (time-sortable)
- **FCS 解析**: fcsparser

### 分層架構
```
API Layer (FastAPI routers)
    ↓
Usecase Layer (業務流程編排)
    ↓
Repository Layer (資料存取)
    ↓
Models Layer (資料庫 schema)

Domain Layer (純業務邏輯，不依賴任何層)
```

## 重要架構決策與討論

### 1. 分層架構原則 ⭐ 核心討論

**問題**: dependencies.py 應該放在哪一層？

**錯誤觀點**: "FastAPI 的慣例是在 dependencies 直接操作 repository"

**正確觀點**: "框架應該服從架構，不是架構服從框架"

**決策**:
- `dependencies.py` 是 API 層的特殊實作（處理 HTTP request → 業務邏輯的轉換）
- API 層只負責：解析 HTTP、調用 usecase、處理 HTTP response
- Usecase 層負責：業務邏輯、事務管理、編排 repositories
- Domain 層負責：純業務邏輯（如 hash_password, verify_password）
- Repository 使用應該在 Usecase，不應該在 Domain Service

**依賴方向**:
```
✅ 正確: API → Usecase → Repository
✅ 正確: API → Usecase → Domain Service
❌ 錯誤: API → Repository (繞過 usecase)
❌ 錯誤: Domain Service → Repository (混入技術細節)
```

**實作範例**:
```python
# API Layer (dependencies.py)
async def get_current_token_from_pat(
    request: Request,
    authorization: str | None = Header(None),
    session: AsyncSession = Depends(get_db),
) -> tuple[Token, User]:
    # 1. 解析 HTTP header（API 層職責）
    if not authorization:
        raise UnauthorizedException("Missing authorization header")

    parts = authorization.split()
    pat_token = parts[1]

    # 2. 提取 HTTP context
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    endpoint = str(request.url.path)

    # 3. 調用 usecase（不是 repository！）
    auth_usecase = AuthUsecase(session)
    token, user = await auth_usecase.authenticate_pat(
        pat_token=pat_token,
        client_ip=client_ip,
        method=method,
        endpoint=endpoint,
    )

    return token, user

# Usecase Layer (auth_usecase.py)
async def authenticate_pat(
    self,
    pat_token: str,
    client_ip: str,
    method: str,
    endpoint: str,
) -> tuple[Token, User]:
    # 使用 domain service 處理 token hash
    token_hash = hash_token(pat_token)

    # 使用 repository 查詢
    is_valid, token = await self.token_repo.is_valid(token_hash)

    # 業務邏輯處理
    if not is_valid or not token:
        await self._log_failed_access(...)
        raise TokenExpiredException()

    # 更新使用記錄
    await self.token_repo.update_last_used(token.id)

    # 記錄 audit log
    await self.audit_repo.create(...)

    return token, user
```

### 2. Exception 處理架構 ⭐ 核心討論

**問題**: Exception 應該在哪裡處理？

**初始錯誤**: 在 main.py 處理所有 DB exceptions，導致越來越臃腫

**決策**:
1. **Repository 層**: 捕捉 SQLAlchemy exceptions → 拋出 RepositoryException
2. **Usecase 層**: 捕捉 RepositoryException → 轉譯為 AppException (業務異常)
3. **API 層**: 只處理 AppException → HTTP response

**問題**: Usecase 要指定 status_code 是否違反分層原則？

**解決**: 創建特定業務異常類別（如 ServiceUnavailableException），在 exception 類別內部封裝 status_code

**實作範例**:
```python
# Repository Layer
async def create(self, username: str, email: str, password_hash: str) -> User:
    try:
        user = User(username=username, email=email, password_hash=password_hash)
        self.session.add(user)
        await self.session.flush()
        return user
    except IntegrityError as e:
        # 捕捉 DB exception，轉換為 repository exception
        if "unique" in str(e.orig).lower():
            raise DuplicateRecordException(f"Username '{username}' already exists")
        raise DatabaseOperationException("Failed to create user")
    except OperationalError as e:
        raise DatabaseConnectionException()

# Usecase Layer
async def register(self, request: UserRegisterRequest) -> UserResponse:
    try:
        password_hash = hash_password(request.password)
        user = await self.user_repo.create(...)
        return UserResponse.model_validate(user)
    except DuplicateRecordException as e:
        # 轉譯為業務異常
        raise ValidationException(e.message)
    except DatabaseConnectionException:
        # 使用封裝 status_code 的業務異常
        raise ServiceUnavailableException()
    except DatabaseOperationException:
        raise InternalServerException("Failed to create user")

# Exception Class
class ServiceUnavailableException(AppException):
    """Raised when service is temporarily unavailable."""
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(message, status_code=503)  # status_code 封裝在 class 內部
```

### 3. Import 策略

**決策**:
- **模組內部**: 使用相對路徑 `from .exceptions import ...`
- **跨模組**: 使用絕對路徑 `from app.models.user import User`

**理由**: 清晰、避免循環依賴

### 4. 時間處理

**決策**:
- **Python 代碼**: `datetime.now(timezone.utc)`
- **DB 欄位預設值**: `server_default=text("CURRENT_TIMESTAMP")`

**理由**: 確保時區一致性、DB 層面的預設值

### 5. ID 生成

**演變過程**:
```
UUID → ULID → UUIDv7
```

**最終決策**: UUIDv7

**理由**: 時間可排序、標準化、效能好

**實作**:
```python
from uuid6 import uuid7

def generate_uuid7() -> UUID:
    """Generate a UUIDv7 (time-sortable UUID)."""
    return uuid7()
```

### 6. typing.List 過時

**決策**: 使用 `list[str]` 而不是 `List[str]`

**理由**: Python 3.9+ 內建支援，不需要 typing

### 7. FCS 檔案設計 ⭐ 重要討論

**問題**: API 設計沒有 file_id 參數，如何指定檔案？

**討論的方案**:
- **方案 1**: 每個 User 一個"當前"檔案 (添加 `is_current` 欄位)
- **方案 2**: 每個 User 只能有一個檔案 (覆蓋模式)
- **方案 3**: 使用 `created_at` 取最新

**最終決策**: 使用 `created_at` 取最新檔案

**理由**:
- ✅ 不需要額外欄位
- ✅ 不需要維護 `is_current` 狀態
- ✅ 保留歷史記錄
- ✅ 簡單直觀 (`ORDER BY created_at DESC LIMIT 1`)

**用戶評語**: "太笨！" (指 `is_current` 方案)

**實作**:
```python
# Repository
async def get_latest_file(self, user_id: UUID) -> FCSFile | None:
    """Get the latest FCS file for a user."""
    result = await self.session.execute(
        select(FCSFile)
        .where(FCSFile.user_id == user_id)
        .order_by(FCSFile.uploaded_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()

# Usecase
async def get_parameters(self, user_id: UUID, scopes: list[str]) -> dict:
    """Get FCS file parameters from latest file."""
    fcs_file = await self.fcs_repo.get_latest_file_with_parameters(user_id)
    if not fcs_file:
        raise NotFoundException("No FCS file found")
    # ... 處理參數
```

## 資料庫設計

### Models

#### 1. User
```python
id: UUID (UUIDv7)
username: str (unique)
email: str (unique)
password_hash: str
created_at: datetime (server_default)
```

#### 2. Token
```python
id: UUID (UUIDv7)
user_id: UUID (FK to User)
name: str
token_hash: str (unique, SHA-256)
prefix: str (前 8 字元)
scopes: JSON (list[str])
expires_at: datetime
is_revoked: bool
last_used_at: datetime (nullable)
created_at: datetime (server_default)
```

#### 3. AuditLog
```python
id: UUID (UUIDv7)
token_id: UUID (FK to Token)
timestamp: datetime (server_default)
ip_address: str
method: str
endpoint: str
status_code: int
authorized: bool
reason: str (nullable)
```

#### 4. FCSFile
```python
id: UUID (UUIDv7)
user_id: UUID (FK to User)
file_id: str (short ID for API, unique)
filename: str
file_path: str
total_events: int
total_parameters: int
uploaded_at: datetime (server_default)
```

#### 5. FCSParameter
```python
id: UUID (UUIDv7)
file_id: UUID (FK to FCSFile)
index: int
pnn: str (parameter name)
pns: str (parameter short name)
range: int
display: str (LIN or LOG)
```

### 關鍵設計
- 所有 ID 使用 UUIDv7
- 時間欄位使用 `server_default=text("CURRENT_TIMESTAMP")`
- Token scopes 儲存為 JSON array
- FCS 使用最新檔案策略（基於 `uploaded_at`）

## 權限系統設計

### 階層式權限
```python
PERMISSION_HIERARCHY = {
    "workspaces": ["admin", "delete", "write", "read"],
    "users": ["write", "read"],
    "fcs": ["analyze", "write", "read"],
}
```

### 規則
- 高階權限包含低階權限 (admin > delete > write > read)
- 各資源之間權限獨立
- 例如：`workspaces:admin` 包含 `workspaces:delete`、`workspaces:write`、`workspaces:read`

### 實作
```python
def has_permission(user_scopes: list[str], required_scope: str) -> bool:
    """Check if user has required permission."""
    required_resource, required_permission = parse_scope(required_scope)

    for scope in user_scopes:
        resource, permission = parse_scope(scope)
        if resource != required_resource:
            continue

        # 取得該權限包含的所有權限
        implied_permissions = get_implied_permissions(resource, permission)
        if required_permission in implied_permissions:
            return True

    return False
```

## API 設計

### 認證 (JWT)
```
POST /api/v1/auth/register  # 註冊新用戶
POST /api/v1/auth/login     # 登入取得 JWT
```

### Token 管理 (需要 JWT)
```
POST   /api/v1/tokens            # 建立 PAT
GET    /api/v1/tokens            # 列出所有 PAT
GET    /api/v1/tokens/{id}       # 取得單一 PAT
DELETE /api/v1/tokens/{id}       # 撤銷 PAT
GET    /api/v1/tokens/{id}/logs  # 取得 PAT 使用記錄
```

### 資源存取 (需要 PAT)

#### Workspaces (stub 實作)
```
GET    /api/v1/workspaces                  # workspaces:read
GET    /api/v1/workspaces/{id}             # workspaces:read
PUT    /api/v1/workspaces/{id}             # workspaces:write
DELETE /api/v1/workspaces/{id}             # workspaces:delete
PUT    /api/v1/workspaces/{id}/settings    # workspaces:admin
```

#### Users (stub 實作)
```
GET /api/v1/users/me  # users:read (使用 PAT，不是 JWT)
PUT /api/v1/users/me  # users:write
```

**注意**: Users API 使用 PAT 認證（CurrentTokenUser），不是 JWT（CurrentUser）

#### FCS (完整實作)
```
POST /api/v1/fcs/upload       # fcs:write
GET  /api/v1/fcs/parameters   # fcs:read (操作最新檔案)
GET  /api/v1/fcs/events       # fcs:read (操作最新檔案)
GET  /api/v1/fcs/statistics   # fcs:analyze (操作最新檔案)
```

**注意**: 所有 FCS API 都操作用戶最新上傳的檔案，不需要指定 file_id

## 安全性設計

### Token 儲存
- **格式**: `pat_` + 隨機字串（32字元）
- **儲存**:
  - `token_hash`: SHA-256 hash (用於驗證)
  - `prefix`: 前 8 字元明文 (用於顯示和檢索)
- **顯示**: 僅在建立時顯示一次完整 token

### 密碼儲存
- 使用 Argon2 hash
- `verify_password()` 驗證

### Audit Log
記錄每次 PAT 使用：
- `token_id`: 使用的 token
- `timestamp`: 使用時間
- `ip_address`: 來源 IP
- `method`: HTTP method
- `endpoint`: API endpoint
- `status_code`: 回應狀態碼
- `authorized`: 是否授權成功
- `reason`: 失敗原因（可選）

### Rate Limiting (待實作)
- 基於 IP
- 每分鐘 60 次請求

## 專案結構

```
pat/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── auth.py           # 認證端點
│   │       ├── dependencies.py   # API 層依賴（遵循分層架構）
│   │       ├── fcs.py            # FCS 端點
│   │       ├── tokens.py         # Token 管理端點
│   │       ├── users.py          # User 端點
│   │       └── workspaces.py     # Workspace 端點
│   ├── common/
│   │   ├── config.py             # 配置
│   │   ├── database.py           # 資料庫連線
│   │   ├── exceptions.py         # 業務異常
│   │   ├── id_utils.py           # UUIDv7 生成
│   │   └── responses.py          # 統一回應格式
│   ├── domain/
│   │   ├── auth_service.py       # JWT 相關（純業務邏輯）
│   │   ├── permissions.py        # 權限系統
│   │   ├── schemas.py            # Pydantic schemas
│   │   └── token_service.py      # Token 生成和 hash
│   ├── models/
│   │   ├── audit_log.py
│   │   ├── fcs.py
│   │   ├── token.py
│   │   └── user.py
│   ├── repository/
│   │   ├── audit_log_repository.py
│   │   ├── exceptions.py         # Repository 異常
│   │   ├── fcs_repository.py
│   │   ├── token_repository.py
│   │   └── user_repository.py
│   ├── usecase/
│   │   ├── auth_usecase.py       # 認證業務邏輯
│   │   ├── fcs_usecase.py        # FCS 業務邏輯
│   │   ├── token_usecase.py      # Token 業務邏輯
│   │   ├── user_usecase.py       # User 業務邏輯 (stub)
│   │   └── workspace_usecase.py  # Workspace 業務邏輯 (stub)
│   └── main.py                   # FastAPI 應用入口
├── migrations/                   # Alembic migrations
├── tests/                        # 測試
├── uploads/                      # FCS 檔案上傳目錄
├── .env                          # 環境變數
├── alembic.ini                   # Alembic 配置
├── requirements.txt              # 依賴清單
└── design.txt                    # 原始設計文檔
```

## 目前完成狀態

### ✅ 已完成
1. 專案結構和依賴設定
2. 資料庫 Models (使用 UUIDv7)
3. Domain 層 (權限系統、認證服務、Token 服務)
4. Repository 層 (包含完整的 exception 處理)
5. Usecase 層 (Auth, Token, Workspace, User, FCS)
6. **重構 dependencies.py** (遵循分層架構原則)
7. API 層 (所有路由端點實作完成)
8. 路由註冊到 main.py
9. 應用程式能夠成功 import

### ⏳ 待完成
1. 建立資料庫 migration (需要先啟動 PostgreSQL)
2. 執行 migration
3. 測試應用程式運行
4. 實作 Rate limiting (每分鐘 60 次)
5. 撰寫測試 (pytest)
6. API 文件和使用範例

## 關鍵學習與原則

### 1. 架構原則優先於框架慣例
> "框架應該服從架構，不是架構服從框架"

框架（如 FastAPI）是外層的實作細節，不應該影響核心架構設計。業務邏輯應該獨立於框架，這樣才能：
- 易於測試
- 易於維護
- 易於替換技術選型

### 2. Exception 處理要分層
每一層都有自己的責任：
- **Repository**: 處理技術異常 (DB errors)
- **Usecase**: 處理業務異常 (business logic errors)
- **API**: 處理 HTTP 相關 (status codes, response format)

### 3. 簡單即是美
> "DB schema 的時間欄位，如需有預設值，請用 server default 的方式"
> "DB schema FCSModel 裡已經有記錄建立時間，直接拿最新建立的 fcs 來用就好，不需要多 is_current 欄位，還需要多餘的維護成本，太笨！"

避免過度設計：
- 能用現有機制就不要新增欄位
- 能用簡單方案就不要複雜化
- 優先考慮維護成本

### 4. 依賴方向要清晰
```
外層 → 內層
API → Usecase → Repository → Models
API → Usecase → Domain (純業務邏輯)
```

內層不應該知道外層的存在：
- Domain 不依賴 Repository
- Usecase 不依賴 API
- 不依賴 HTTP、資料庫等技術細節

### 5. 分離關注點
- **API 層**: HTTP 相關（request parsing, response formatting）
- **Usecase 層**: 業務流程編排
- **Domain 層**: 核心業務規則
- **Repository 層**: 資料存取

每一層專注於自己的職責，不越界。

## 開發建議

### 新增功能時
1. 先在 Domain 層定義業務邏輯
2. 在 Repository 層實作資料存取
3. 在 Usecase 層編排流程
4. 最後在 API 層暴露端點

### 修改現有功能時
1. 確認修改影響哪些層
2. 從內層往外層修改
3. 保持依賴方向正確

### 測試策略
1. Domain 層: 單元測試（不需要 DB）
2. Repository 層: 整合測試（需要 DB）
3. Usecase 層: 可以 mock repository
4. API 層: 端到端測試

## 參考資料

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
