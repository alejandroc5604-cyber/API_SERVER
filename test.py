import requests


API_BASE_URL = "http://127.0.0.1:8000"
API_KEY = "HELLO"

response = requests.post(
    f"{API_BASE_URL}/DB_AddDatabase",
    params={"api_key": API_KEY, "database_name": "TESTER"},
    timeout=10,
)
response.raise_for_status()
database_name = response.json()["DatabaseName"]
print("Database response:", response.json())

response = requests.post(
    f"{API_BASE_URL}/DB_AddItem/{database_name}",
    params={
        "api_key": API_KEY,
        "image_path": "test-image.jpg",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "source": "test.py",
        "confidence_score": 0.95,
        "trash_type": "plastic",
    },
    timeout=10,
)
response.raise_for_status()
print("Add item response:", response.json())

response = requests.get(
    f"{API_BASE_URL}/DB_GetDatabase/{database_name}",
    params={"limit": 10},
    timeout=10,
)
response.raise_for_status()
print("Database data:", response.json())
