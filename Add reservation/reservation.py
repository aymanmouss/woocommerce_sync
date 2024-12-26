import requests

def make_reservation(api_key):
    # API endpoint
    url = "https://restful.bluefinmobileshop.com/reserveArticle/new/"
    
    # Request headers
    headers = {
        'Authorization': "d60e1ea2df4b9a4fbb8e017bb0ffba10b283dc876298b89365bfe72af93d3afa*75cab247bbee7e06c1921b4161d04c2803cd421b8308f275d125bba5d0926f91"
    }
    
    # Form data
    form_data = {
        'sku': '1003-131236-20999_HU03',
        'qty': '1',
        'warranty': '1'
    }
    
    try:
        # Make POST request with form data
        response = requests.post(url, headers=headers, data=form_data)
        
        # Print response details
        print(f"Status Code: {response.status_code}")
        print("\nResponse Headers:")
        for key, value in response.headers.items():
            print(f"{key}: {value}")
        print("\nResponse Body:")
        print(response.text)
        
        # Check if request was successful
        if response.status_code == 200:
            print("\nReservation successfully created!")
            return response.text
        else:
            print(f"\nError creating reservation: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"\nError making request: {e}")
        return None

if __name__ == "__main__":
    # Replace 'YOUR_API_KEY' with your actual API key
    API_KEY = "YOUR_API_KEY"
    result = make_reservation(API_KEY)