#!/bin/sh
# entrypoint.sh — chạy migration Alembic rồi khởi động uvicorn
# Được gọi bởi CMD trong Dockerfile khi Docker build.
# Đảm bảo DB luôn có schema và seed data khi container khởi động.

set -e

echo "[entrypoint] Chạy Alembic migration..."
alembic upgrade head

echo "[entrypoint] Migration hoàn thành. Khởi động server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
