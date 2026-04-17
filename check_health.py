import requests
r = requests.get('http://localhost:8000/health')
print('Status:', r.status_code)
print('Response:', r.json())
