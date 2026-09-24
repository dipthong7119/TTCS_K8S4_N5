FROM python:3.11-slim

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Không buffer stdout/stderr — log hiện ngay trong Docker
ENV PYTHONUNBUFFERED=1

# Cài đặt curl để healthcheck hoạt động
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements và cài đặt trước (tận dụng Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn backend
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY entrypoint.sh .

# Mở port
EXPOSE 8000

# entrypoint.sh: chạy migration rồi mới khởi động uvicorn
# Đảm bảo DB luôn có schema + seed data khi container start
CMD ["sh", "entrypoint.sh"]
