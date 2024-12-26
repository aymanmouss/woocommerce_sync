import requests
import json

def get_reservations():
    # API endpoint
    url = "https://restful.bluefinmobileshop.com/reserveArticle/get/"
    
    # Request headers with the provided API key
    headers = {
        'Authorization': 'd60e1ea2df4b9a4fbb8e017bb0ffba10b283dc876298b89365bfe72af93d3afa*75cab247bbee7e06c1921b4161d04c2803cd421b8308f275d125bba5d0926f91'
    }
    
    try:
        # Make GET request
        response = requests.get(url, headers=headers)
        
        # Print response details
        print(f"Status Code: {response.status_code}")
        print("\nResponse Headers:")
        for key, value in response.headers.items():
            print(f"{key}: {value}")
            
        # Try to parse and pretty print JSON response
        try:
            response_json = response.json()
            print("\nResponse Body:")
            print(json.dumps(response_json, indent=2))
            
            if response.status_code == 200:
                print("\nReservations retrieved successfully!")
                return response_json
            
        except json.JSONDecodeError:
            print("\nResponse Body (non-JSON):")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"\nError making request: {e}")
        return None

if __name__ == "__main__":
    result = get_reservations()