# 使用 Python 3.12 作為基礎映像
FROM python:3.12-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements.txt 並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案檔案
COPY . .

# 建立 uploads 目錄
RUN mkdir -p uploads

# 暴露應用程式端口
EXPOSE 8000

# 預設命令（會被 docker-compose.yml 覆蓋）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
