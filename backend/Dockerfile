FROM python:3.11-slim

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Khắc phục lỗi in log của Python trong Docker
ENV PYTHONUNBUFFERED=1

# Copy file requirements và cài đặt trước (tận dụng Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy mã nguồn ứng dụng
COPY app/ ./app/

# Copy cấu hình Alembic và thư mục migrations
# (cần thiết để lifespan chạy 'alembic upgrade head' khi container khởi động)
COPY alembic.ini .
COPY alembic/ ./alembic/

# Mở port
EXPOSE 8000

# Khởi chạy server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
