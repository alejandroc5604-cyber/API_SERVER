import requests


API_BASE_URL = "http://127.0.0.1:8020"
API_KEY = "MYAPIKEY2579437698346"


def print_json(label, response):
    try:
        payload = response.json()
    except ValueError:
        payload = {"text": response.text}
    print(f"{label}: {payload}")


response = requests.post(
    f"{API_BASE_URL}/api/DB_AddDatabase",
    params={"api_key": API_KEY, "database_name": "TESTER"},
    timeout=10,
)
response.raise_for_status()
database_name = response.json()["DatabaseName"]
print_json("DB_AddDatabase", response)

response = requests.post(
    f"{API_BASE_URL}/api/DB_AddItem/{database_name}",
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
item_uuid = response.json()["item_uuid"]
print_json("DB_AddItem", response)

response = requests.get(
    f"{API_BASE_URL}/api/DB_GetDatabase/{database_name}",
    params={"limit": 10},
    timeout=10,
)
response.raise_for_status()
print_json("DB_GetDatabase", response)

response = requests.get(f"{API_BASE_URL}/api/DB_FindDB", timeout=10)
response.raise_for_status()
print_json("DB_FindDB", response)

response = requests.put(
    f"{API_BASE_URL}/api/DB_EditItem/{database_name}",
    params={
        "api_key": API_KEY,
        "item_uuid": item_uuid,
        "image_path": "updated-test-image.jpg",
        "latitude": 40.7306,
        "longitude": -73.9352,
        "source": "updated-test.py",
        "confidence_score": 0.87,
        "trash_type": "metal",
    },
    timeout=10,
)
response.raise_for_status()
print_json("DB_EditItem", response)

response = requests.get(
    f"{API_BASE_URL}/api/DB_GetDatabase/{database_name}",
    params={"limit": 10},
    timeout=10,
)
response.raise_for_status()
print_json("DB_GetDatabase after edit", response)

response = requests.delete(
    f"{API_BASE_URL}/api/DB_DeleteItem/{database_name}",
    params={"api_key": API_KEY, "item_uuid": item_uuid},
    timeout=10,
)
response.raise_for_status()
print_json("DB_DeleteItem", response)

response = requests.post(
    f"{API_BASE_URL}/api/ImageDB/SetupDB",
    params={"api_key": API_KEY, "database_name": "IMAGE_TESTER"},
    timeout=10,
)
response.raise_for_status()
image_database_name = response.json()["DatabaseName"]
print_json("ImageDB_SetupDB", response)

with open("../nginx/html/map/trash.jpg", "rb") as image_file:
    response = requests.post(
        f"{API_BASE_URL}/api/ImageDB/AddImage",
        params={"api_key": API_KEY, "database_name": image_database_name},
        files={"image": ("trash.jpg", image_file, "image/jpeg")},
        timeout=20,
    )
response.raise_for_status()
image_id = response.json()["image_id"]
print_json("ImageDB_AddImage", response)

response = requests.get(
    f"{API_BASE_URL}/api/ImageDB/FindDB",
    params={"limit": 20},
    timeout=10,
)
response.raise_for_status()
print_json("ImageDB_FindDB", response)

response = requests.get(
    f"{API_BASE_URL}/api/ImageDB/FindImages/{image_database_name}",
    params={"image_limit": 20},
    timeout=10,
)
response.raise_for_status()
print_json("ImageDB_FindImages", response)

image_response = requests.get(
    f"{API_BASE_URL}/api/ImageDB/GetImage/{image_database_name}/{image_id}",
    timeout=20,
)
image_response.raise_for_status()
print("Image retrieval status:", image_response.status_code)
print("Image bytes retrieved:", len(image_response.content))
with open("./retrieved_test_image.png", "wb") as output:
    output.write(image_response.content)
print("Saved retrieved image to ./retrieved_test_image.png")

response = requests.delete(
    f"{API_BASE_URL}/api/ImageDB/DeleteImage/{image_database_name}/{image_id}",
    params={"api_key": API_KEY},
    timeout=10,
)
response.raise_for_status()
print_json("ImageDB_DeleteImage", response)

response = requests.delete(
    f"{API_BASE_URL}/api/DB_DeleteDB/{database_name}",
    params={"api_key": API_KEY},
    timeout=10,
)
response.raise_for_status()
print_json("DB_DeleteDB", response)

print("All API tests completed successfully.")
