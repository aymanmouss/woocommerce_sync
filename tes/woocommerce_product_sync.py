import json
import logging
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import time
import re

# Configuration
WC_API_URL = 'https://lightgreen-grouse-876378.hostingersite.com/wp-json/wc/v3'
WC_API_KEY = 'ck_3e57ba3338b5b29e50eb450f0f746d810babb5d8'
WC_API_SECRET = 'cs_c304669ef6f0a3eb2915f96bd827391910516bc6'

# Logging Configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(f'woocommerce_sync_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WooCommerceSync:
    def __init__(self, api_url, api_key, api_secret):
        self.api_url = api_url
        self.auth = HTTPBasicAuth(api_key, api_secret)
        self.session = requests.Session()
        self.session.auth = self.auth

    def normalize_model_name(self, model):
        """Normalize model name for consistent matching."""
        # Remove 'Galaxy' and any connection type like 'Dual 5G'
        normalized = re.sub(r'^Galaxy\s*', '', model)
        normalized = re.sub(r'\s*(?:Dual\s*(?:5G|LTE))?$', '', normalized)
        return normalized.strip()

    def find_product_by_name(self, product_name):
        """Find a product by searching its name."""
        try:
            logger.debug(f"Searching for product with name: {product_name}")
            response = self.session.get(
                f"{self.api_url}/products",
                params={
                    'search': product_name,
                    'type': 'variable'
                }
            )
            response.raise_for_status()
            products = response.json()
            logger.debug(f"Found products: {products}")
            return products[0] if products else None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error finding product with name {product_name}: {e}")
            return None

    def create_product(self, product_data):
        """Create a new WooCommerce product."""
        try:
            normalized_model = self.normalize_model_name(product_data['model'])
            
            product_payload = {
                'name': product_data['name'],
                'type': 'variable',
                'meta_data': [
                    {'key': '_model', 'value': normalized_model}
                ],
                'attributes': [
                    {
                        'name': attr['name'], 
                        'options': attr['options'], 
                        'visible': True, 
                        'variation': True
                    } 
                    for attr in product_data.get('attributes', [])
                ]
            }
            
            logger.debug(f"Creating product payload: {json.dumps(product_payload, indent=2)}")
            
            response = self.session.post(
                f"{self.api_url}/products", 
                json=product_payload
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Product creation failed: {response.text}")
                return None
            
            product = response.json()
            logger.info(f"Created product: {product['name']} (ID: {product['id']})")
            return product
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating product {product_data['name']}: {e}")
            return None

    def create_variation(self, product_id, variation_data):
        """Create a new product variation with unique SKU handling."""
        try:
            # Generate a unique SKU to avoid duplicate errors
            unique_sku = f"{variation_data['sku']}-{int(time.time())}"
            
            payload = {
                'regular_price': variation_data.get('price', ''),
                'sku': unique_sku,
                'stock_quantity': variation_data.get('stock_quantity', 0),
                'attributes': [
                    {'name': 'Color', 'option': variation_data['attributes']['Color']},
                    {'name': 'Storage', 'option': variation_data['attributes']['Storage']}
                ]
            }
            
            response = self.session.post(
                f"{self.api_url}/products/{product_id}/variations", 
                json=payload
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Variation creation failed: {response.text}")
                logger.error(f"Payload: {payload}")
                return None
            
            variation = response.json()
            logger.info(f"Created variation for original SKU {variation_data['sku']} (New SKU: {unique_sku}, Variation ID: {variation['id']})")
            return variation
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating variation for SKU {variation_data['sku']}: {e}")
            return None

def main():
    # Find the latest JSON file
    import glob
    import os
    
    list_of_files = glob.glob('samsung_products_*.json')
    latest_file = max(list_of_files, key=os.path.getctime)
    
    logger.info(f"Processing file: {latest_file}")
    
    syncer = WooCommerceSync(WC_API_URL, WC_API_KEY, WC_API_SECRET)
    
    # Load JSON data
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    samsung_products = data.get('Products', {}).get('Samsung', [])
    
    logger.info(f"Total Samsung products to process: {len(samsung_products)}")
    
    for product_info in samsung_products:
        logger.info(f"Processing product: {product_info['name']}")
        
        # Find or create product
        existing_product = syncer.find_product_by_name(product_info['name'])
        
        if not existing_product:
            # Product doesn't exist, create it
            created_product = syncer.create_product(product_info)
            if not created_product:
                logger.error(f"Failed to create product: {product_info['name']}")
                continue
            
            product_id = created_product['id']
        else:
            product_id = existing_product['id']
            logger.info(f"Product already exists: {product_info['name']} (ID: {product_id})")

        # Process variations
        for variation in product_info['variations']:
            syncer.create_variation(product_id, variation)
    
    logger.info("Product synchronization complete!")

if __name__ == "__main__":
    main()