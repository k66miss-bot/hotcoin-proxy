import hashlib
import hmac
import base64
import time
from urllib.parse import urlencode
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json

app = Flask(__name__)
CORS(app)

ACCESS_KEY = os.environ.get('ACCESS_KEY', '')
SECRET_KEY = os.environ.get('SECRET_KEY', '')
BASE_URL = 'https://api-ct.hotcoin.fit'

def generate_signature(method, path, params={}):
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    sorted_params = dict(sorted({
        'AccessKeyId': ACCESS_KEY,
        'SignatureMethod': 'HmacSHA256',
        'SignatureVersion': '2',
        'Timestamp': timestamp,
        **params
    }.items()))
    query_string = urlencode(sorted_params)
    host = 'api-ct.hotcoin.fit'
    string_to_sign = f"{method}\n{host}\n{path}\n{query_string}"
    signature = base64.b64encode(
        hmac.new(SECRET_KEY.encode(), string_to_sign.encode(), hashlib.sha256).digest()
    ).decode()
    sorted_params['Signature'] = signature
    return sorted_params

def place_single_order(contract_code, body):
    path = f'/api/v1/perpetual/products/{contract_code}/order'
    params = generate_signature('POST', path)
    url = f"{BASE_URL}{path}?" + urlencode(params)
    resp = requests.post(url, json=body, timeout=10)
    return resp.status_code, resp.json()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'access_key_set': bool(ACCESS_KEY)})

@app.route('/place_orders'
