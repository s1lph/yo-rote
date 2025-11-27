import requests

try:
    response = requests.post('http://127.0.0.1:5000/api/points', json={'address': 'Test Point API'})
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
