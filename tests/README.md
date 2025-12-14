# PAT System Test Suite

## 测试覆盖范围

### 1. 权限阶层继承测试 (`test_permissions.py`)
- ✅ `workspaces:delete` 包含 `delete`/`write`/`read` 权限
- ✅ `workspaces:delete` 不包含 `workspaces:admin` 权限
- ✅ `workspaces:write` 包含 `read` 权限
- ✅ `workspaces:write` 不包含 `delete` 权限
- ✅ `workspaces:admin` 包含所有 workspace 权限
- ✅ 权限不可跨资源（例如 `workspaces:write` 不包含 `fcs:read`）

### 2. 使用者隔离测试 (`test_user_isolation.py`)
- ✅ User A 无法列出 User B 的 tokens
- ✅ User A 无法查看 User B 的 token 详情
- ✅ User A 无法撤销 User B 的 token
- ✅ User A 无法查看 User B 的 audit logs
- ✅ 用户只能访问自己的 tokens

### 3. Token 生命周期测试 (`test_token_lifecycle.py`)
- ✅ 已过期的 token 返回 401 TokenExpired
- ✅ 即将过期的 token 仍然有效
- ✅ 已撤销的 token 返回 401 TokenRevoked
- ✅ 撤销操作是幂等的
- ✅ 已撤销的 token 仍出现在 token 列表中
- ✅ 有效且有权限的 token 返回 200
- ✅ 有效但无权限的 token 返回 403

### 4. Token 安全存储测试 (`test_token_security.py`)
- ✅ 数据库中不存储明文 token（只有 hash 和 prefix）
- ✅ Token hash 一致性验证
- ✅ 有效 token 且有权限返回 200
- ✅ 无效 token 返回 401
- ✅ Prefix token 无法用于认证（返回 401 InvalidToken）
- ✅ 缺少 Authorization header 返回 401
- ✅ 无效的 Authorization header 格式返回 401
- ✅ 空 token 返回 401

### 5. API Status Codes 测试 (`test_api_status_codes.py`)
覆盖所有 API 端点的各种响应状态码：
- ✅ 200 OK - 成功响应
- ✅ 400 Bad Request - 验证错误
- ✅ 401 Unauthorized - 未认证
- ✅ 403 Forbidden - 权限不足
- ✅ 404 Not Found - 资源不存在
- ✅ 422 Unprocessable Entity - 请求格式错误
- ✅ 429 Too Many Requests - 超过速率限制

**测试的 API 端点：**
- Auth API: register, login
- Tokens API: create, list, get, revoke, logs
- Workspaces API: list, create, delete, update settings
- Users API: get me, update me
- FCS API: parameters, events, statistics, upload

## 运行测试

### 方法 1: 使用测试脚本（推荐）
```bash
./run_tests.sh
```

### 方法 2: 手动运行
```bash
# 安装测试依赖
pip install -r requirements-dev.txt

# 创建测试数据库
docker compose exec postgres psql -U postgres -c "CREATE DATABASE pat_test;"

# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_permissions.py -v
pytest tests/test_user_isolation.py -v
pytest tests/test_token_lifecycle.py -v
pytest tests/test_token_security.py -v
pytest tests/test_api_status_codes.py -v

# 运行带覆盖率的测试
pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

# 运行特定标记的测试
pytest -m permissions
pytest -m security
pytest -m isolation
```

## 测试结构

```
tests/
├── __init__.py
├── conftest.py                  # Pytest fixtures
├── test_permissions.py          # 权限继承测试
├── test_user_isolation.py       # 用户隔离测试
├── test_token_lifecycle.py      # Token 过期/撤销测试
├── test_token_security.py       # Token 安全存储测试
└── test_api_status_codes.py     # API 状态码测试
```

## Fixtures

### Database Fixtures
- `test_db` - 测试数据库 session factory
- `session` - 数据库 session
- `client` - HTTP 测试 client

### User Fixtures
- `user_a` - 测试用户 A
- `user_b` - 测试用户 B
- `user_a_jwt` - 用户 A 的 JWT token
- `user_b_jwt` - 用户 B 的 JWT token

### Token Fixtures
- `create_pat_token` - 创建 PAT token 的工厂函数
- `expired_token` - 已过期的 token

## 测试标记

- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.permissions` - 权限测试
- `@pytest.mark.security` - 安全测试
- `@pytest.mark.isolation` - 隔离测试

## 覆盖率报告

测试运行后会生成 HTML 覆盖率报告：
```bash
open htmlcov/index.html
```

## CI/CD Integration

测试可以集成到 CI/CD 流程：
```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    pip install -r requirements-dev.txt
    pytest tests/ --cov=app --cov-report=xml
```
