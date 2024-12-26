import requests
import json

# API Configuration
url = "https://restful.bluefinmobileshop.com/getStock/"
api_key = "d60e1ea2df4b9a4fbb8e017bb0ffba10b283dc876298b89365bfe72af93d3afa*75cab247bbee7e06c1921b4161d04c2803cd421b8308f275d125bba5d0926f91"

# Query Parameters
params = {
    "lang_id": 0, 
    "price_drop": 0
}

# Headers
headers = {
    "Authorization": api_key
}

# Make the GET request
try:
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        # Save JSON response to a file
        with open("product_stock.json", "w") as file:
            json.dump(response.json(), file, indent=4)
        print("JSON data successfully saved to 'product_stock.json'")
    else:
        print(f"Error: HTTP {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"An error occurred: {str(e)}")
