FROM python:3.13-slim

WORKDIR /app

# 装系统依赖(pymilvus/pymysql/pypdf 等可能需要)
# libreoffice-writer/-impress/-calc: Word/PPT/Excel 转 PDF（走 MinerU 链路）
# fontconfig + 常用开源中文字体包: 保证 LibreOffice headless 转 PDF 时中文不乱码/变方块
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    fontconfig \
    libreoffice-writer \
    libreoffice-impress \
    libreoffice-calc \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# 复制自定义 Windows / macOS 专有字体包及 Fontconfig 别名映射配置
COPY assets/fonts/ /usr/share/fonts/truetype/custom/
RUN if [ -f /usr/share/fonts/truetype/custom/fonts.conf ]; then \
        cp /usr/share/fonts/truetype/custom/fonts.conf /etc/fonts/local.conf; \
    fi && fc-cache -fv

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
