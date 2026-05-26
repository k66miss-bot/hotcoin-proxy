import hashlib
import hmac
import base64
import time
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

@app.route('/place_orders', methods=['POST'])
def place_orders():
    data = request.json
    contract_code = data.get('contract_code', 'ethusdt')
    orders = data.get('orders', [])
    results = []

    for order in orders:
        try:
            order_type = int(order.get('type', 10))
            is_conditional = order_type == 12 or bool(order.get('trigger_price'))
            is_market = order_type == 11

            if is_conditional:
                trigger_price = float(order['trigger_price'])
                current_price = float(order.get('current_price', trigger_price))
                body = {
                    'type': 12,
                    'side': order['side'],
                    'price': str(trigger_price),
                    'amount': int(order['amount']),
                    'triggerPrice': str(trigger_price),
                    'triggerBy': 'last',
                    'algoType': 10,
                    'currentPrice': str(current_price)
                }
            elif is_market:
                body = {
                    'type': 11,
                    'side': order['side'],
                    'amount': int(order['amount']),
                    'marketUnit': 'amount'
                }
            else:
                body = {
                    'type': 10,
                    'side': order['side'],
                    'price': str(order['price']),
                    'amount': int(order['amount'])
                }

            status_code, result = place_single_order(contract_code, body)
            results.append({
                'order_type': 'conditional' if is_conditional else ('market' if is_market else 'limit'),
                'side': order['side'],
                'price': order.get('price'),
                'trigger_price': order.get('trigger_price'),
                'body_sent': body,
                'result': result,
                'http_status': status_code,
                'success': status_code == 200 and 'id' in result
            })

        except Exception as e:
            results.append({'error': str(e), 'success': False, 'order': order})

    return jsonify({'results': results})

@app.route('/cancel_all', methods=['POST'])
def cancel_all():
    data = request.json
    contract_code = data.get('contract_code', 'ethusdt')
    try:
        path = f'/api/v1/perpetual/products/{contract_code}/orders'
        params = generate_signature('DELETE', path)
        url = f"{BASE_URL}{path}?" + urlencode(params)
        resp = requests.delete(url, timeout=10)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
