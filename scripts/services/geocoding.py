import requests
from dotenv import load_dotenv
import os

from scripts.services.endpoints import (
    check_if_coordinates_in_cache,
    patch_location_geocoding,
)


def geocode_location_nominatim(location):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": location, "format": "json", "limit": 1}
    headers = {"User-Agent": "GeocodingApp/1.0"}
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    try:
        data = response.json()[0]

        return [data["lat"], data["lon"]]
    except:
        return None


def geocode_location_google(location):
    load_dotenv()
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_GEOCODING_API_KEY")

    # Check if API key is available
    if not GOOGLE_MAPS_API_KEY:
        print("Google Maps API key not found in environment variables")
        return None

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": location, "key": GOOGLE_MAPS_API_KEY}
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    try:
        if data["status"] == "OK" and len(data["results"]) > 0:
            location = data["results"][0]["geometry"]["location"]
            return [str(location["lat"]), str(location["lng"])]
        return None
    except:
        return None


def geocode_location_cache(location):
    result = check_if_coordinates_in_cache(location)
    try:
        result = result.json()[0]
        if result["longitude"] and result["latitude"]:
            return [result["latitude"], result["longitude"]]
    except:
        return None


def geocode_location(location):
    location_name = location["location"]
    location_id = location["id"]

    # First lets check is the locations hasn't been added to the location cache
    if location["geocoded_status"] not in [
        "Cache geocoded",
        "Nominatim geocoded",
        "Google geocoded",
    ]:
        coordinates = geocode_location_cache(location_name)
        if coordinates:
            patch_location_geocoding(coordinates, location_id, "Cache geocoded")

    if location["geocoded_status"] in ["Cache geocoding failed", "Cache geocoded"]:
        coordinates = geocode_location_nominatim(location_name)
        if coordinates:
            patch_location_geocoding(coordinates, location_id, "Nominatim geocoded")
        else:
            patch_location_geocoding({}, location_id, "Nominatim geocoding failed")

    if location["geocoded_status"] in [
        "Nominatim geocoding failed",
        "Nominatim geocoded",
    ]:
        coordinates = geocode_location_google(location_name)
        if coordinates:
            patch_location_geocoding(coordinates, location_id, "Google geocoded")
        else:
            patch_location_geocoding({}, location_id, "Google geocoding failed")

    if location["geocoded_status"] == "Google geocoding failed":
        coordinates = geocode_location_cache(location_name)
        if coordinates:
            patch_location_geocoding(coordinates, location_id, "Cache geocoded")
        else:
            return "No geocoding found, try manual geocoding in the api"
    if coordinates:
        return coordinates
