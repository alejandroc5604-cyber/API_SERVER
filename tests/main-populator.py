"""This script is going to populate the server directly with fake data"""

import random
import requests
import sys

ITEM_COUNT = random.randint(100, 400)
PORT = 8020
BASE_API_URL = f"http://localhost:{PORT}"
API_KEY = "HELLO"


trash_types = [
    ("Plastic", ["tests/Images/plastic-01.png", "tests/Images/plastic-02.png"]), 
    ("Metal",   ["tests/Images/metal-01.png", "tests/Images/metal-02png"]),
    ("Ceramic", ["test/Images/ceramic-01.png", "test/Images/ceramic-02.png"]),
    ("Cardboard", ["test/Images/cardboard-01.png", "test/Images/cardboard-02.png"])
]

IMAGE_DB_NAME = "TesterImageDatabase"
DATA_DB_NAME = "TesterImageDatabase"

# make the databases
print("Building Image DB")
url = f"{BASE_API_URL}/api/ImageDB/SetupDB"
params = {
    "api_key": str(API_KEY),
    "database_name": IMAGE_DB_NAME
}
response = requests.post(url, params=params)
if response.ok:
    ImageDB_NAME_Response = response.json()["DatabaseName"]
    print(f"Built ImageDB: {ImageDB_NAME_Response}")
else:
    print(f"Failed building ImageDB: {response.json()}")
    sys.exit()


print("Building Data DB")
url = f"{BASE_API_URL}/api/DB_AddDatabase"
params = {
    "api_key": str(API_KEY),
    "database_name": IMAGE_DB_NAME
}
response = requests.post(url, params=params)
if response.ok:
    DataDB_NAME_Response = response.json()["DatabaseName"]
    print(f"Built data DB: {ImageDB_NAME_Response}")
else:
    print(f"Failed data ImageDB: {response.json()}")
    sys.exit()

# first upload the images
for trash_name, images in trash_types:
    for image in images:
        params = {
            "api_key": "",
            "database_name": ImageDB_NAME_Response
        }
        with open(image, "r") as file:
            pas