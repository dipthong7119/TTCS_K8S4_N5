import requests

def test_login_10_times():
    url = "http://localhost:8000/api/auth/login"
    data = {
        "email": "admin@csms.local",
        "password": "Admin@2024!"
    }
    
    success_count = 0
    for i in range(10):
        try:
            resp = requests.post(url, json=data)
            if resp.status_code == 200:
                success_count += 1
            else:
                print(f"Failed at {i+1}. Status: {resp.status_code}, Resp: {resp.text}")
        except Exception as e:
            print(f"Error at {i+1}: {e}")
            
    print(f"Success {success_count}/10 times.")
    if success_count != 10:
        raise Exception("Login failed!")

if __name__ == "__main__":
    test_login_10_times()
