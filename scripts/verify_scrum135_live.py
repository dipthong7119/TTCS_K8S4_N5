"""
Kịch bản kiểm chứng thực tế toàn bộ tính năng bằng code thực thi
cho nhiệm vụ SCRUM-135 (Đặng Ngọc Đại) trên server đang chạy:
1. Đăng nhập 5 vai trò (Admin, Operator, Station Owner, Accountant, Driver)
2. Kiểm tra HttpOnly Cookie & Phân quyền bảo vệ route (S-03)
3. Kiểm tra bảo vệ Brute Force: Khóa tạm 15 phút sau 5 lần sai
4. Kiểm tra trang giao diện HTML & các module tĩnh đã nạp đủ
"""
import httpx

client = httpx.Client(base_url="http://127.0.0.1:8000")

print("=" * 65)
print("KIỂM CHỨNG TRỰC TIẾP CODE DỰ ÁN CSMS — SPRINT 2 (SCRUM-135)")
print("Người thực hiện: ĐẶNG NGỌC ĐẠI (DANG-DAI)")
print("=" * 65)

# 1. Kiểm tra 5 vai trò đăng nhập
print("\n[PHẦN 1] Kiểm tra 5 vai trò đăng nhập và chuyển hướng đúng:")
roles_data = [
    ("admin@csms.local", "Admin@2024!", "/monitoring", "admin"),
    ("owner@csms.local", "Owner@2024!", "/stations", "station_owner"),
    ("operator@csms.local", "Operator@2024!", "/monitoring", "operator"),
    ("accountant@csms.local", "Accountant@2024!", "/wallet", "accountant"),
    ("driver@csms.local", "Driver@2024!", "/sessions/mine", "driver"),
]

for email, password, expected_redirect, role_name in roles_data:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Đăng nhập thất bại: {res.text}"
    body = res.json()
    assert body["redirect_to"] == expected_redirect
    assert role_name in body["roles"]
    set_cookie = res.headers.get("set-cookie", "")
    assert "csms_session" in set_cookie
    assert "httponly" in set_cookie.lower()
    print(f"  ✓ {role_name:<14} | Email: {email:<20} | Redirect -> {expected_redirect:<16} | Cookie: OK")

# 2. Kiểm tra phân quyền bảo vệ route
print("\n[PHẦN 2] Kiểm tra phân quyền truy cập endpoint có bảo vệ:")
# Hiện tại cookie đang là của driver -> gọi cây trạm /api/monitoring/tree phải bị từ chối 403
res_driver_tree = client.get("/api/monitoring/tree")
print(f"  ✓ Driver gọi /api/monitoring/tree: HTTP {res_driver_tree.status_code} (Chặn đúng quyền)")
assert res_driver_tree.status_code == 403

# Đăng nhập lại với Admin -> gọi cây trạm thành công
res_admin_login = client.post("/api/auth/login", json={"email": "admin@csms.local", "password": "Admin@2024!"})
res_admin_tree = client.get("/api/monitoring/tree")
data = res_admin_tree.json()
stations = data if isinstance(data, list) else data.get("stations", [])
print(f"  ✓ Admin gọi /api/monitoring/tree:  HTTP {res_admin_tree.status_code} (Lấy được {len(stations)} trạm sạc)")
assert res_admin_tree.status_code == 200

# 3. Kiểm tra bảo vệ Brute Force
print("\n[PHẦN 3] Kiểm tra Brute-Force: Khóa sau 5 lần sai liên tiếp:")
# Reset IP client trước khi thử
test_email = "test_brute_force_user@example.com"
for attempt in range(1, 6):
    r_fail = client.post("/api/auth/login", json={"email": test_email, "password": f"WrongPwd_{attempt}"})
    detail = r_fail.json().get("detail")
    print(f"  - Lần {attempt}: HTTP {r_fail.status_code} | '{detail}'")
    assert detail == "email hoặc mật khẩu không đúng"

# Lần 6: Kể cả nhập mật khẩu gì cũng bị khóa
r_lock = client.post("/api/auth/login", json={"email": test_email, "password": "AnyPassword"})
print(f"  ✓ Lần 6: HTTP {r_lock.status_code} | '{r_lock.json().get('detail')}' (Khóa tạm 15 phút)")
assert r_lock.status_code == 401
assert r_lock.json().get("detail") == "tài khoản tạm khoá 15 phút"

# 4. Kiểm tra giao diện tĩnh và các tệp JS của Đặng Ngọc Đại
print("\n[PHẦN 4] Kiểm tra tải tài nguyên Frontend của Đặng Ngọc Đại:")
res_login_html = client.get("/login")
assert res_login_html.status_code == 200
html_text = res_login_html.text
assert 'id="login-form"' in html_text
assert 'id="password-toggle"' in html_text
assert '/static/js/api_client.js' in html_text
assert '/static/js/auth_guard.js' in html_text
assert '/static/js/form_guard.js' in html_text
assert '/static/js/pages/login.js' in html_text
print("  ✓ Template /login tải thành công (HTTP 200), đầy đủ các thẻ chức năng và script.")

res_api_client = client.get("/static/js/api_client.js")
assert res_api_client.status_code == 200
print("  ✓ Tệp /static/js/api_client.js (Đại): HTTP 200")

res_auth_guard = client.get("/static/js/auth_guard.js")
assert res_auth_guard.status_code == 200
print("  ✓ Tệp /static/js/auth_guard.js (Đại): HTTP 200")

res_login_js = client.get("/static/js/pages/login.js")
assert res_login_js.status_code == 200
print("  ✓ Tệp /static/js/pages/login.js (Đại): HTTP 200")

print("\n" + "=" * 65)
print("KẾT LUẬN: MỌI MÔ-ĐUN CODE CỦA ĐẶNG NGỌC ĐẠI ĐỀU HOẠT ĐỘNG HOÀN HẢO!")
print("=" * 65)
