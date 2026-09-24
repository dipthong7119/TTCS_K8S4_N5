from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """
    Kiểm tra API /health trả về HTTP 200 và nội dung mong đợi.
    Test này dùng làm placeholder để xác nhận CI Pipeline hoạt động trơn tru.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Hệ thống đang hoạt động ổn định"}
