FROM python:3.11-slim

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Khắc phục lỗi in log của Python trong Docker
ENV PYTHONUNBUFFERED=1

# Copy file requirements và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn
COPY app/ ./app/
# Copy cấu hình alembic (sẽ được tạo ở bước sau)
# COPY alembic/ ./alembic/
# COPY alembic.ini .

# Mở port
EXPOSE 8000

# Khởi chạy server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
