import os
import requests
from urllib.parse import urljoin
from scripts.services.authentication import fetch_bearer_token
from datetime import datetime


def make_request(method, endpoint, token_necessary=True, payload=None):
    url = urljoin(os.getenv("CENTRAL_APP_URL"), endpoint)
    if token_necessary:
        token = fetch_bearer_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
    else:
        headers = {
            "Content-Type": "application/json",
        }

    if method.upper() == "POST":
        response = requests.post(url, json=payload, headers=headers)
    elif method.upper() == "GET":
        response = requests.get(url, params=payload, headers=headers)
    elif method.upper() == "DELETE":
        if payload is not None:
            response = requests.delete(url, json=payload, headers=headers)
        else:
            response = requests.delete(url, headers=headers)
    elif method.upper() == "PATCH":
        response = requests.patch(url, json=payload, headers=headers)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")

    return response


def post_matched_locations_request(article_id, location_name, frequency):
    payload = {
        "article_id": article_id,
        "location": location_name,
        "frequency": frequency,
        "latitude": 0,
        "longitude": 0,
    }
    return make_request("POST", "matched_locations", payload=payload)


def post_text_coordinates_request(article_id, latitude, longitude):
    payload = {
        "article_id": article_id,
        "text_latitude": latitude,
        "text_longitude": longitude,
    }
    return make_request("POST", "text_coordinates", payload=payload)


def post_central_repository(
    metadata_object: dict,
):
    payload = {
        "title": metadata_object.title,
        "authors": metadata_object.authors,
        "doi": metadata_object.doi,
        "journal": metadata_object.journal,
        "year": metadata_object.year,
        "keywords": metadata_object.keywords,
        "location_number": metadata_object.location_number,
        "page_number": metadata_object.page_number,
        "extraction_time": metadata_object.extraction_time,
    }
    return make_request("POST", "central_repository", payload=payload)


def check_if_doi_already_in_db(doi: str):
    payload = {"doi": doi}
    endpoint = "central_repository/doi"
    response = make_request("GET", endpoint=endpoint, payload=payload)
    # Return the opposite boolean value from the response JSON
    return response.json()


def patch_extraction_time(extraction_time, article_id):
    endpoint = f"central_repository/{article_id}/extraction_time"
    payload = {"extraction_time": extraction_time}
    return make_request("PATCH", endpoint=endpoint, payload=payload)


def get_account_verification_requests():
    response = make_request("GET", "pending_users")
    user_accounts = []

    if response.status_code == 200:
        users = response.json()
        print("\n=== Pending Account Verification Requests ===")
        for i, user in enumerate(users, 1):
            # Format the timestamp to a more readable format
            created_at = user["created_at"]
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, AttributeError):
                formatted_time = created_at  # Fallback to original format

            # Add username and ID to the dictionary
            user_accounts.append([user["username"], user["id"]])

            print(f"\nAccount #{i}:")
            print(f"  ID:         {user['id']}")
            print(f"  Username:   {user['username']}")
            print(f"  Full Name:  {user['name']}")
            print(f"  Admin:      {user['is_admin']}")
            print(f"  Verified:   {user['is_verified']}")
            print(f"  Created at: {formatted_time}")
        print("\n" + "=" * 45)

    return user_accounts


def verify_account(account_id):
    endpoint = f"verify_user/{account_id}"
    return make_request("POST", endpoint=endpoint)


def get_locations_marked_for_geocoding():
    endpoint = "geocoding/"
    return make_request("GET", endpoint=endpoint)


def patch_location_geocoding(coordinates, location_id, status):
    if not coordinates:
        latitude = 0
        longitude = 0
    else:
        latitude = coordinates[0]
        longitude = coordinates[1]

    endpoint = f"matched_locations/{location_id}"
    payload = {
        "latitude": latitude,
        "longitude": longitude,
        "geocoded_status": status,
    }

    return make_request("PATCH", endpoint=endpoint, payload=payload)


def check_if_coordinates_in_cache(location_name):
    endpoint = f"coordinates_cache/{location_name}"

    return make_request("Get", endpoint=endpoint)


def health_check():
    token_necessary = False
    return make_request("GET", "healthy", token_necessary=token_necessary)


if __name__ == "__main__":
    result = check_if_coordinates_in_cache("Braga")
    print(result.json())
