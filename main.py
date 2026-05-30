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
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

ACCESS_KEY = os.environ.get('ACCESS_KEY', '')
SECRET_KEY = os.environ.get('SECRET_KEY', '')
BASE_URL = 'https://api-ct.hotcoin.fit'

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

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

@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    return jsonify({'status': 'ok', 'access_key_set': bool(ACCESS_KEY)})

@app.route('/get_positions', methods=['POST', 'OPTIONS'])
def get_positions():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    data = request.json
    contract_code = data.get('contract_code', 'ethusdt')
    try:
        path = f'/api/v1/perpetual/position/{contract_code}/list'
        params = generate_signature('GET', path)
        url = f"{BASE_URL}{path}?" + urlencode(params)
        resp = requests.get(url, timeout=10)
        result = resp.json()
        print(f"Positions: {json.dumps(result, ensure_ascii=False)}")
        positions = []
        if isinstance(result, list):
            raw = result
        elif isinstance(result, dict):
            raw = result.get('data', result.get('list', []))
        else:
            raw = []
        for p in raw:
            if float(p.get('amount', 0)) > 0:
                positions.append({
                    'side': p.get('side', ''),
                    'amount': p.get('amount', '0'),
                    'avgPrice': p.get('avgPrice', p.get('openPrice', '0')),
                    'unrealizedPnl': p.get('unrealizedPnl', p.get('unRealizedSurplus', '0')),
                    'positionId': p.get('id', ''),
                    'openTime': p.get('openTime', p.get('createdDate', p.get('createDate', 0))),
                    'updatedDate': p.get('updatedDate', 0)
                })
        return jsonify({'positions': positions, 'raw': result})
    except Exception as e:
        return jsonify({'error': str(e), 'positions': []}), 500

@app.route('/place_orders', methods=['POST', 'OPTIONS'])
def place_orders():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    data = request.json
    contract_code = data.get('contract_code', 'ethusdt')
    orders = data.get('orders', [])
    results = []
    for order in orders:
        try:
            order_type = int(order.get('type', 10))
            is_market = order_type == 11
            is_plan = order_type == 12
            if is_plan:
                trigger_price = float(order['trigger_price'])
                body = {
                    'type': 12,
                    'side': order['side'],
                    'price': str(trigger_price),
                    'amount': int(order['amount']),
                    'triggerPrice': str(trigger_price),
                    'triggerBy': 'last',
                    'algoType': 11
                }
            elif is_market:
                body = {
                    'type': 11,
                    'sid
