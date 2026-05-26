import hashlib
import hmac
import base64
import time
import json
from urllib.parse import urlencode
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

ACCESS_KEY = os.environ.get('ACCESS_KEY', '')
SECRET_KEY = os.environ.get('SECRET_KEY', '')
BASE_URL = 'https://api-ct.hotcoin.fit'

def generate_signature(method, path, params):
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

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/place_orders', methods=['POST'])
def place_orders():
    data = request.json
    contract_code = data.get('contract_code', 'ethusdt')
    orders = data.get('orders', [])
    
    results = []
    for order in orders:
        try:
            path = f'/api/v1/perpetual/products/{contract_code}/order'
            params = generate_signature('POST', path, {})
            
            body = {
                'type': str(order.get('type', 10)),
                'side': order['side'],
                'price': str(order['price']),
                'amount': int(order['amount'])
            }
            
            # 条件单（止盈止损）
            if order.get('trigger_price'):
                path = f'/api/v1/perpetual/products/{contract_code}/order'
                body['type'] = '12'
                body['triggerPrice'] = str(order['trigger_price'])
                body['triggerBy'] = 'last'
                body['algoType'] = '10'
                body['currentPrice'] = str(order.get('current_price', order['price']))
            
            url = f"{BASE_URL}{path}?" + urlencode(params)
            resp = requests.post(url, json=body, timeout=10)
            result = resp.json()
            results.append({'order': order, 'result': result, 'success': True})
        except Exception as e:
            results.append({'order': order, 'error': str(e), 'success': False})
    
    return jsonify({'results': results})

@app.route('/cancel_all', methods=['POST'])
def cancel_all():
    data = request.json
    contract_code = data.get('contract_code', 'ethusdt')
    side = data.get('side', '')
    
    try:
        path = f'/api/v1/perpetual/products/{contract_code}/orders'
        params = generate_signature('DELETE', path, {})
        url = f"{BASE_URL}{path}?" + urlencode(params)
        body = {'side': side} if side else {}
        resp = requests.delete(url, json=body, timeout=10)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
