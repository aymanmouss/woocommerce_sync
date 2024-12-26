import requests
import json

# API Configuration
url = "https://restful.bluefinmobileshop.com/getStock/"
api_key = "d60e1ea2df4b9a4fbb8e017bb0ffba10b283dc876298b89365bfe72af93d3afa*75cab247bbee7e06c1921b4161d04c2803cd421b8308f275d125bba5d0926f91"

# Query Parameters
params = {
    "lang_id": 0,  # Language ID
    "price_drop": 0  # Filter for price drop
}

# Headers
headers = {
    "Authorization": api_key
}

# Make the GET request and save response
try:
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        # Save the JSON response to a file
        with open("stock_data.json", "w") as json_file:
            json.dump(response.json(), json_file, indent=4)
        print("JSON data successfully saved to 'stock_data.json'")
    else:
        print(f"Error: HTTP {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"An error occurred: {str(e)}")
