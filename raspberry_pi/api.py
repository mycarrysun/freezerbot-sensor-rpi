import os
import requests
from dotenv import load_dotenv, set_key, unset_key

API_TOKEN = 'API_TOKEN'
API_HOST = 'FREEZERBOT_API_HOST'
DEFAULT_HOST = 'https://api.freezerbot.com'

def make_api_request_with_creds(credentials, path, method='POST', json={}):
    endpoint = f'{os.getenv(API_HOST, DEFAULT_HOST)}/api/{path}'
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    return requests.request(method, endpoint, headers=headers, json={**json, **credentials})

def make_api_request(path, method='POST', json={}):
    load_dotenv(override=True)
    endpoint = f"{os.getenv(API_HOST, DEFAULT_HOST)}/api/{path}"
    headers = {
        'Authorization': f"Bearer {os.getenv(API_TOKEN)}",
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    return requests.request(method, endpoint, headers=headers, json=json)

def set_api_token(token):
    set_key('.env', API_TOKEN, token)

def api_token_exists():
    load_dotenv(override=True)
    if os.getenv(API_TOKEN):
        return True
    else:
        return False

def clear_api_token():
    unset_key('.env', API_TOKEN)
