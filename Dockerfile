FROM python:3.13-slim

WORKDIR /app

# 装系统依赖(pymilvus/pymysql/pypdf 等可能需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 装 uv
RUN pip install --no-cache-dir uv

# 先拷依赖文件(利用缓存层)
COPY pyproject.toml uv.lock ./
COPY third_party/ ./third_party/

# 装依赖
RUN uv sync --frozen --no-dev

# 再拷代码
COPY . .

# 默认启动 API
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
