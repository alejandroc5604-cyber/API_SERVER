# Populate the database with random data
import requests


API_KEY = ""
API_BASE_URL = "" # preferable to run this locally, toa void wasting data
ItemCount = 100
Latitude_Min, Latitude_max = 0,0
Longitude_Min, Longitude_max = 0,0
items = ["plastic", "bottle", "cigarette", "metal", "can", "bio-waste", "can", "wrapper", "plastic bag"]

def populate():
    #clear database if it exists, then add 100 items
    pass

if __name__ == "__main__":
    populate()
