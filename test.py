import os
import requests


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")
API_KEY = os.getenv("API_KEY", "HELLO")


def test_api():
    database_uuid = None
    item_uuid = None

    try:
        response = requests.post(
            f"{API_BASE_URL}/DB_AddDatabase",
            params={"api_key": API_KEY},
            timeout=10,
        )
        response.raise_for_status()
        database_uuid = response.json()["DatabaseUUID"]

        item_data = {
            "api_key": API_KEY,
            "image_path": "test-image.jpg",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "source": "test.py",
            "confidence_score": 0.95,
            "trash_type": "plastic",
        }
        response = requests.post(
            f"{API_BASE_URL}/DB_AddItem/{database_uuid}",
            params=item_data,
            timeout=10,
        )
        response.raise_for_status()
        item_uuid = response.json()["item_uuid"]

        response = requests.get(
            f"{API_BASE_URL}/DB_GetDatabase/{database_uuid}",
            params={"limit": 10},
            timeout=10,
        )
        response.raise_for_status()
        found_data = response.json()["FoundData"]
        assert any(item["ID"] == item_uuid for item in found_data)

        edited_item_data = {
            **item_data,
            "item_uuid": item_uuid,
            "image_path": "edited-test-image.jpg",
            "trash_type": "paper",
        }
        response = requests.put(
            f"{API_BASE_URL}/DB_EditItem/{database_uuid}",
            params=edited_item_data,
            timeout=10,
        )
        response.raise_for_status()

        response = requests.get(
            f"{API_BASE_URL}/DB_GetDatabase/{database_uuid}",
            params={"limit": 10},
            timeout=10,
        )
        response.raise_for_status()
        edited_items = response.json()["FoundData"]
        assert any(
            item["ID"] == item_uuid
            and item["type"] == "paper"
            and item["image_path"] == "edited-test-image.jpg"
            for item in edited_items
        )

        response = requests.get(f"{API_BASE_URL}/DB_FindDB", timeout=10)
        response.raise_for_status()
        assert database_uuid in response.json()["Databases"]

        response = requests.delete(
            f"{API_BASE_URL}/DB_DeleteItem/{database_uuid}",
            params={"item_uuid": item_uuid, "api_key": API_KEY},
            timeout=10,
        )
        response.raise_for_status()
        deleted_item_uuid = item_uuid
        item_uuid = None

        response = requests.get(
            f"{API_BASE_URL}/DB_GetDatabase/{database_uuid}",
            params={"limit": 10},
            timeout=10,
        )
        response.raise_for_status()
        assert all(
            item["ID"] != deleted_item_uuid
            for item in response.json()["FoundData"]
        )

        response = requests.delete(
            f"{API_BASE_URL}/DB_DeleteDB/{database_uuid}",
            params={"api_key": API_KEY},
            timeout=10,
        )
        response.raise_for_status()
        database_uuid = None

        print("All API checks passed.")
    finally:
        if database_uuid is not None:
            if item_uuid is not None:
                requests.delete(
                    f"{API_BASE_URL}/DB_DeleteItem/{database_uuid}",
                    params={"item_uuid": item_uuid, "api_key": API_KEY},
                    timeout=10,
                )
            requests.delete(
                f"{API_BASE_URL}/DB_DeleteDB/{database_uuid}",
                params={"api_key": API_KEY},
                timeout=10,
            )


if __name__ == "__main__":
    test_api()
