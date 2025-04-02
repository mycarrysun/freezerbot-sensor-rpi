import os
import requests
from dotenv import load_dotenv, set_key

API_TOKEN = 'API_TOKEN'

def make_api_request(path, method='POST', json={}):
    load_dotenv(override=True)
    endpoint = f"{os.getenv('FREEZERBOT_API_HOST', 'https://freezerbot.nextwebtoday.com')}/api/{path}"
    headers = {
        'Authorization': f"Bearer {os.getenv(API_TOKEN)}",
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    return requests.request(method, endpoint, headers=headers, json=json)

def set_api_token(token):
    set_key('.env', API_TOKEN, token)