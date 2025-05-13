import os
import jwt
import datetime
import requests
from dotenv import load_dotenv, find_dotenv

# Global variables to store credentials and token for the current session
session_username = None
session_password = None
session_bearer_token = None


def set_session_credentials(username, password):
    """Store credentials for the current session"""
    global session_username, session_password
    session_username = username
    session_password = password


def post_token_request():
    load_dotenv()  # Make sure we have current env vars
    url = f"{os.getenv('CENTRAL_APP_URL')}/token"  # Use string formatting instead of os.path.join

    username, password = get_user_data()

    payload = {
        "grant_type": "password",
        "username": username,
        "password": password,
    }

    # Define the headers
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # Make the POST request
    response = requests.post(url, data=payload, headers=headers)

    # Check the response
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def validate_token(token):
    try:
        # Decode token without signature verification
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp")
        if not exp:
            return False
        expiration = datetime.datetime.fromtimestamp(exp, tz=datetime.timezone.utc)
        return datetime.datetime.now(datetime.timezone.utc) < expiration
    except Exception:
        return False


def get_user_data():
    """Get user credentials from session, not from environment variables"""
    global session_username, session_password

    # Check if we have session credentials
    if not session_username or not session_password:
        raise ValueError("No active login session. Please log in first.")

    return session_username, session_password


def fetch_bearer_token():
    """Get a valid bearer token, requiring login if needed"""
    global session_bearer_token

    # Load env variables for API URLs
    load_dotenv()

    # Check if we have a valid token in memory
    if session_bearer_token and validate_token(session_bearer_token):
        return session_bearer_token

    # If no valid token, we'll need to get a new one via login
    new_token = post_token_request()
    if new_token:
        # Store the new token in memory only
        session_bearer_token = new_token
        return session_bearer_token

    return None


if __name__ == "__main__":
    fetch_bearer_token()
