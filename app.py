import phonenumbers
from phonenumbers import geocoder, carrier, timezone, PhoneNumberType
import requests
from base64 import b64encode
from opencage.geocoder import OpenCageGeocode
import folium
import os
import re
import logging
from flask import Flask, request, jsonify, render_template_string
from threading import Thread

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== API KEYS ==========
TWILIO_ACCOUNT_SID = "ACff2fb863284d10539a3b5e6c8cd39681"
TWILIO_AUTH_TOKEN = "92904da85dc95b64f6e429e53e351065"
OPENCAGE_API_KEY = "5da5dc29873941f8966fda54b873688f"

# Initialize Flask app
app = Flask(__name__)

# ========== 📞 PHONENUMBER INFO ==========
def get_phonenumbers_info(phone_number: str, region: str = None):
    try:
        parsed = phonenumbers.parse(phone_number, region)
        if not phonenumbers.is_valid_number(parsed):
            return {"❌ Invalid Number": "Phone number format is not valid."}, None

        number_type_map = {  
            PhoneNumberType.MOBILE: "📱 Mobile",  
            PhoneNumberType.FIXED_LINE: "🏠 Fixed Line",  
            PhoneNumberType.FIXED_LINE_OR_MOBILE: "📞 Fixed Line or Mobile",  
            PhoneNumberType.TOLL_FREE: "🆓 Toll-Free",  
            PhoneNumberType.PREMIUM_RATE: "💎 Premium Rate",  
            PhoneNumberType.VOIP: "🌐 VoIP",  
            PhoneNumberType.PERSONAL_NUMBER: "👤 Personal Number",  
            PhoneNumberType.PAGER: "📟 Pager",  
            PhoneNumberType.UAN: "🏢 UAN",  
            PhoneNumberType.VOICEMAIL: "📩 Voicemail",  
            PhoneNumberType.UNKNOWN: "❓ Unknown"  
        }  

        location = geocoder.description_for_number(parsed, "en") or "Unknown"

        return {  
            "🌍 International Format": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),  
            "🇺🇳 National Format": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),  
            "📞 Country Code": str(parsed.country_code),  
            "🔢 National Number": str(parsed.national_number),  
            "📊 Number Type": number_type_map.get(phonenumbers.number_type(parsed), "❓ Unknown"),  
            "🗺️ Country": location,  
            "🏢 Carrier": carrier.name_for_number(parsed, "en") or "Unknown",  
            "⏰ Time Zone": ", ".join(timezone.time_zones_for_number(parsed)) or "Unknown"  
        }, location  
    except phonenumbers.NumberParseException as e:
        logger.error(f"Phone number parsing error: {e}")
        return {"❌ Parse Error": f"Could not parse phone number: {str(e)}"}, None
    except Exception as e:
        logger.error(f"Unexpected error in get_phonenumbers_info: {e}")
        return {"❌ Unexpected Error": "An unexpected error occurred while processing the phone number."}, None

# ========== TWILIO LOOKUP INFO ==========
def get_twilio_info(phone_number: str):
    try:
        # Validate phone number format first
        try:
            parsed = phonenumbers.parse(phone_number)
            if not phonenumbers.is_valid_number(parsed):
                return {"⚠️ Twilio Warning": "Number format invalid for Twilio lookup"}
        except:
            return {"⚠️ Twilio Warning": "Number format invalid for Twilio lookup"}
        
        url = f"https://lookups.twilio.com/v2/PhoneNumbers/{phone_number}?Fields=line_type_intelligence,caller_name"
        auth_str = f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}"
        headers = {
            "Authorization": f"Basic {b64encode(auth_str.encode()).decode()}"
        }

        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()

        result = {}
        if data.get("country_code"):
            result["🌍 Country Code"] = data.get("country_code")
        if data.get("line_type_intelligence", {}).get("type"):
            result["📞 Line Type"] = data.get("line_type_intelligence", {}).get("type")
        if data.get("carrier", {}).get("name"):
            result["🏢 Carrier"] = data.get("carrier", {}).get("name")
        if data.get("caller_name", {}).get("caller_name"):
            result["👤 Caller Name"] = data.get("caller_name", {}).get("caller_name")
            
        return result if result else {"ℹ️ Twilio Info": "No additional information available from Twilio"}
        
    except requests.exceptions.Timeout:
        logger.warning("Twilio API timeout")
        return {"⚠️ Twilio Warning": "Request timed out"}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return {"⚠️ Twilio Warning": "Number not found in Twilio database"}
        elif e.response.status_code == 401:
            logger.error("Twilio authentication failed")
            return {"❌ Twilio Error": "Authentication failed - check API credentials"}
        else:
            logger.error(f"Twilio HTTP error: {e}")
            return {"⚠️ Twilio Warning": f"API error: {e.response.status_code}"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Twilio request error: {e}")
        return {"⚠️ Twilio Warning": "Network error connecting to Twilio"}
    except Exception as e:
        logger.error(f"Unexpected error in get_twilio_info: {e}")
        return {"⚠️ Twilio Warning": "An unexpected error occurred with Twilio lookup"}

# ========== OPENCAGE MAP LOCATION ==========
def get_opencage_map(location: str):
    try:
        if not location or location == "Unknown":
            return None, None, None
            
        geocoder = OpenCageGeocode(OPENCAGE_API_KEY)
        result = geocoder.geocode(location, timeout=10)
        
        if not result or len(result) == 0:
            return None, None, None

        lat = result[0]['geometry']['lat']  
        lng = result[0]['geometry']['lng']  

        my_map = folium.Map(location=[lat, lng], zoom_start=9)  
        folium.Marker([lat, lng], popup=location, tooltip="Approximate Location").add_to(my_map)  
        map_filename = f"static/map_{hash(location)}.html"
        os.makedirs("static", exist_ok=True)
        my_map.save(map_filename)  

        return lat, lng, map_filename
    except Exception as e:
        logger.error(f"OpenCage geocoding error: {e}")
        return None, None, None

# ========== MERGE AND DEDUPLICATE INFO ==========
def merge_and_deduplicate_info(*dicts):
    result = {}
    priority_fields = {
        "Carrier": "🏢 Carrier",  # Prefer offline carrier info as it's more reliable
        "Country Code": "📞 Country Code"
    }
    
    for d in dicts:
        for key, value in d.items():
            if value and value not in ["Unknown", "None", None]:
                # Check for duplicates and prioritize
                if "Carrier" in key and "🏢 Carrier" not in result:
                    result["🏢 Carrier"] = value
                elif "Country Code" in key and "📞 Country Code" not in result:
                    result["📞 Country Code"] = value
                elif key not in result:
                    result[key] = value
    
    return result

# ========== EXTRACT PHONE NUMBER FROM TEXT ==========
def extract_phone_number(text):
    # Remove all non-digit characters except plus sign
    cleaned = re.sub(r'[^\d+]', '', text)
    
    # Check if it starts with + followed by digits
    if cleaned.startswith('+') and len(cleaned) > 1:
        return cleaned
    
    # Check if it's a valid international number without +
    if len(cleaned) >= 10 and cleaned.isdigit():
        return '+' + cleaned
    
    return None

# ========== FLASK ROUTES ==========
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phone Number Analysis - {{ phone_number }}</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .info-item {
            margin: 15px 0;
            padding: 10px;
            border-left: 4px solid #007bff;
            background-color: #f8f9fa;
        }
        .error {
            border-left-color: #dc3545;
            background-color: #f8d7da;
        }
        .warning {
            border-left-color: #ffc107;
            background-color: #fff3cd;
        }
        .map-container {
            margin-top: 30px;
            text-align: center;
        }
        .map-frame {
            width: 100%;
            height: 400px;
            border: none;
            border-radius: 8px;
        }
        .note {
            font-size: 0.9em;
            color: #666;
            margin-top: 20px;
            padding: 10px;
            background-color: #e9ecef;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 Phone Number Analysis Report</h1>
            <h2>Number: {{ phone_number }}</h2>
        </div>
        
        {% if error %}
            <div class="info-item error">
                <h3>❌ Error</h3>
                <p>{{ error }}</p>
            </div>
        {% else %}
            {% for key, value in info.items() %}
                <div class="info-item {% if '❌' in key %}error{% elif '⚠️' in key %}warning{% endif %}">
                    <strong>{{ key }}:</strong> {{ value }}
                </div>
            {% endfor %}
            
            {% if map_filename %}
            <div class="map-container">
                <h3>🗺️ Approximate Location</h3>
                <iframe src="/{{ map_filename }}" class="map-frame"></iframe>
                <p class="note">Note: Location data is approximate and may not be exact</p>
            </div>
            {% endif %}
        {% endif %}
        
        <div class="note">
            🔍 <strong>Note:</strong> Location data is approximate. Carrier information may vary. 
            Some data might not be available for all numbers.
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <a href="/" style="color: #007bff; text-decoration: none;">← Analyze another number</a>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Phone Number Lookup API</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .container { background: #f9f9f9; padding: 30px; border-radius: 10px; }
            input, button { padding: 10px; margin: 5px; font-size: 16px; }
            input { width: 300px; }
            button { background: #007bff; color: white; border: none; cursor: pointer; }
            .example { background: #e9ecef; padding: 10px; border-radius: 5px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Phone Number Lookup API</h1>
            <p>Enter a phone number with country code to analyze it:</p>
            
            <form action="/look" method="GET">
                <input type="text" name="pnum" placeholder="+14155552671" required>
                <button type="submit">Analyze</button>
            </form>
            
            <div class="example">
                <h3>📖 Usage Examples:</h3>
                <p><strong>Direct API call:</strong> <code>/look?pnum=+14155552671</code></p>
                <p><strong>Supported formats:</strong> +14155552671, +44 20 7946 0958, +1 (415) 555-2671</p>
            </div>
            
            <div class="example">
                <h3>🌐 API Endpoint:</h3>
                <p><code>GET /look?pnum=PHONE_NUMBER</code></p>
                <p>Returns: HTML page with detailed phone number analysis</p>
            </div>
        </div>
    </body>
    </html>
    """)

@app.route('/look')
def look_up_phone():
    phone_input = request.args.get('pnum', '').strip()
    
    if not phone_input:
        return jsonify({"error": "Missing phone number parameter. Use: /look?pnum=+14155552671"}), 400
    
    phone_number = extract_phone_number(phone_input)
    
    if not phone_number:
        return render_template_string(HTML_TEMPLATE, 
                                   phone_number=phone_input,
                                   error="❌ Invalid phone number format. Please include country code (e.g., +14155552671)")
    
    try:
        # Get phone information
        info1, raw_location = get_phonenumbers_info(phone_number)
        info3 = get_twilio_info(phone_number)
        
        # Get location map if available
        map_filename = None
        if raw_location and raw_location != "Unknown":
            lat, lng, map_filename = get_opencage_map(raw_location)
            if lat and lng:
                info1["📍 Latitude"] = str(lat)
                info1["📍 Longitude"] = str(lng)
        
        # Merge all information with deduplication
        all_info = merge_and_deduplicate_info(info1, info3)
        
        return render_template_string(HTML_TEMPLATE, 
                                   phone_number=phone_number,
                                   info=all_info,
                                   map_filename=map_filename)
        
    except Exception as e:
        logger.error(f"Error processing phone number: {e}")
        return render_template_string(HTML_TEMPLATE,
                                   phone_number=phone_number,
                                   error=f"❌ Sorry, I encountered an error processing this phone number: {str(e)}")

# JSON API endpoint
@app.route('/api/look')
def api_look_up_phone():
    phone_input = request.args.get('pnum', '').strip()
    
    if not phone_input:
        return jsonify({"error": "Missing phone number parameter. Use: /api/look?pnum=+14155552671"}), 400
    
    phone_number = extract_phone_number(phone_input)
    
    if not phone_number:
        return jsonify({"error": "Invalid phone number format. Please include country code (e.g., +14155552671)"}), 400
    
    try:
        # Get phone information
        info1, raw_location = get_phonenumbers_info(phone_number)
        info3 = get_twilio_info(phone_number)
        
        # Get location map if available
        map_data = None
        if raw_location and raw_location != "Unknown":
            lat, lng, map_filename = get_opencage_map(raw_location)
            if lat and lng:
                info1["latitude"] = lat
                info1["longitude"] = lng
                map_data = {"latitude": lat, "longitude": lng, "map_file": map_filename}
        
        # Merge all information with deduplication
        all_info = merge_and_deduplicate_info(info1, info3)
        
        # Convert to clean JSON (remove emojis from keys for better API consumption)
        clean_info = {}
        for key, value in all_info.items():
            # Remove emojis and special characters for clean keys
            clean_key = re.sub(r'[^\w\s]', '', key).strip()
            clean_info[clean_key] = value
        
        response_data = {
            "phone_number": phone_number,
            "data": clean_info,
            "location": map_data,
            "success": True
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error processing phone number: {e}")
        return jsonify({
            "phone_number": phone_number,
            "error": f"Error processing phone number: {str(e)}",
            "success": False
        }), 500

def run():
    # Create static directory for maps
    os.makedirs("static", exist_ok=True)
    
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting PhoneInsight API Server on port {port}...")
    print("📧 Endpoints:")
    print("   • GET /              - Homepage with form")
    print("   • GET /look?pnum=+... - HTML response with phone analysis")
    print("   • GET /api/look?pnum=+... - JSON API response")
    print(f"\n💡 Example: http://localhost:{port}/look?pnum=+8801970343966")
    
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    t = Thread(target=run)
    t.start()

if __name__ == "__main__":
    run()
