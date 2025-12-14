# Rate Limiting 測試程式使用說明

這是一個獨立的測試程式，用於驗證 API 的 rate limiting 功能是否正常運作。

## 安裝依賴

```bash
pip install requests
```

## 基本使用

### 1. 測試預設配置（60 req/min）

```bash
python test_rate_limit.py
```

**輸出範例：**
```
======================================================================
Rate Limiting Test
======================================================================

Configuration:
  API URL:           http://localhost:8000
  Test Endpoint:     /api/v1/auth/login
  Expected Limit:    60 requests/minute
  Requests to Make:  70
  Wait Time:         0 seconds
  Verbose Mode:      False

======================================================================

Starting test...

  Completed 10/70 requests...
  Completed 20/70 requests...
  ...
  [14:23:45.123] Request  61: 429 (15.23ms)

  ✗ Rate limit triggered at request #61

======================================================================
Test Summary
======================================================================

Response Status Codes:
  200: 60 requests
  429: 10 requests

Rate Limiting:
  Status: ✓ Rate limiting is WORKING
  Triggered at: Request #61
  Expected: ~60 requests/minute
  Accuracy: Excellent (±1 requests)

Performance:
  Average response time: 12.45ms
  Min response time: 8.23ms
  Max response time: 25.67ms

======================================================================

✓ TEST PASSED: Rate limit triggered at request #61 (expected ~60)
```

### 2. 測試自訂 rate limit

如果你在 `.env` 中設定 `RATE_LIMIT_PER_MINUTE=100`：

```bash
python test_rate_limit.py --limit 100
```

### 3. 詳細模式（顯示每個請求）

```bash
python test_rate_limit.py --verbose
```

**輸出範例：**
```
  [14:23:45.001] Request   1: 200 (12.34ms)
  [14:23:45.015] Request   2: 200 (11.23ms)
  [14:23:45.028] Request   3: 200 (10.45ms)
  ...
  [14:23:46.123] Request  61: 429 (15.23ms)
    → Rate limited! Retry after: 60s
```

### 4. 測試不同的 endpoint

```bash
# 測試 health endpoint
python test_rate_limit.py --endpoint /health --verbose

# 測試 workspaces endpoint (需要認證)
python test_rate_limit.py --endpoint /api/v1/workspacess
```

### 5. 加入等待時間（模擬真實使用）

```bash
# 每個請求間隔 0.5 秒
python test_rate_limit.py --wait 0.5
```

### 6. 自訂請求數量

```bash
# 只發送 65 個請求
python test_rate_limit.py --requests 65
```

### 7. 測試遠端伺服器

```bash
python test_rate_limit.py --url http://production-server.com:8000 --limit 120
```

## 完整參數說明

```
--url URL           API base URL (預設: http://localhost:8000)
--limit LIMIT       預期的 rate limit 值 (預設: 60)
--endpoint PATH     要測試的 API endpoint (預設: /api/v1/auth/login)
--requests COUNT    發送的請求數量 (預設: limit + 10)
--verbose           顯示每個請求的詳細資訊
--wait SECONDS      請求之間的等待時間（秒）(預設: 0)
```

## 測試情境範例

### 情境 1: 驗證預設配置

```bash
# 啟動服務
docker compose up -d

# 執行測試
python test_rate_limit.py

# 預期結果: 在 60-65 個請求左右觸發 rate limit
```

### 情境 2: 驗證自訂配置

```bash
# 修改 .env
echo "RATE_LIMIT_PER_MINUTE=100" >> .env

# 重啟服務
docker compose restart app

# 執行測試
python test_rate_limit.py --limit 100

# 預期結果: 在 100-105 個請求左右觸發 rate limit
```

### 情境 3: 壓力測試

```bash
# 快速發送大量請求
python test_rate_limit.py --requests 200 --verbose

# 查看 rate limiting 在高負載下的表現
```

### 情境 4: 效能測試

```bash
# 加入等待時間，模擬真實使用
python test_rate_limit.py --wait 0.5 --requests 70 --verbose

# 觀察平均回應時間和 rate limiting 觸發點
```

## 解讀測試結果

### ✓ 測試通過

- Rate limit 在預期範圍內觸發（±5 個請求）
- 顯示 `✓ Rate limiting is WORKING`
- Accuracy 顯示 `Excellent` 或 `Good`

### ✗ 測試失敗

可能的原因：

1. **Rate limit 未觸發**
   - 檢查 `.env` 中的 `RATE_LIMIT_PER_MINUTE` 設定
   - 確認服務有重新啟動
   - 檢查 `app/common/rate_limit.py` 的 `RATE_LIMIT` 常數

2. **觸發時間點不符**
   - Rate limit 設定與測試參數不一致
   - 使用 `--limit` 參數指定正確的值

3. **連線錯誤**
   - 確認 API 服務正在運行
   - 檢查 URL 是否正確

## 疑難排解

### 問題: ImportError: No module named 'requests'

**解決:**
```bash
pip install requests
```

### 問題: 連線被拒絕

**解決:**
```bash
# 確認服務運行中
docker compose ps

# 啟動服務
docker compose up -d

# 檢查健康狀態
curl http://localhost:8000/health
```

### 問題: Rate limit 永遠不觸發

**解決:**
```bash
# 檢查 rate_limit.py
cat app/common/rate_limit.py | grep RATE_LIMIT

# 檢查設定
python -c "from app.common.config import settings; print(settings.rate_limit_per_minute)"

# 重新啟動服務
docker compose restart app
```

## 進階使用

### 自動化測試腳本

```bash
#!/bin/bash
# test_all_limits.sh

echo "Testing rate limit: 60 req/min"
python test_rate_limit.py --limit 60

echo "\nTesting rate limit: 100 req/min"
python test_rate_limit.py --limit 100

echo "\nTesting rate limit: 120 req/min"
python test_rate_limit.py --limit 120
```

### 持續監控

```bash
# 每 5 分鐘測試一次
watch -n 300 python test_rate_limit.py
```

## 輸出檔案

測試結果會即時顯示在終端機，如需儲存結果：

```bash
# 儲存測試結果
python test_rate_limit.py --verbose > test_results.log 2>&1

# 只儲存摘要
python test_rate_limit.py > test_summary.txt
```

## 整合到 CI/CD

```yaml
# .github/workflows/test.yml
- name: Test Rate Limiting
  run: |
    python test_rate_limit.py --url http://localhost:8000 --limit 60
```

## 注意事項

1. **快取影響**: 某些反向代理或 CDN 可能會快取請求，影響測試結果
2. **網路延遲**: 測試遠端伺服器時，網路延遲可能影響觸發時機
3. **並發限制**: 此腳本是循序發送請求，不測試並發限制
4. **時間窗口**: Rate limiting 是基於時間窗口，重複測試需要等待窗口重置

## 支援

如有問題，請檢查：
1. API 服務日誌: `docker compose logs app`
2. 速率限制設定: `cat .env | grep RATE_LIMIT`
3. 測試程式原始碼: `test_rate_limit.py`
