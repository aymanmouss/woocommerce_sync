import requests
import json
import logging
from typing import List, Dict, Optional, Set
from woocommerce import API
import configparser
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from ratelimit import limits, sleep_and_retry
import time
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('woocommerce_sync.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Config:
    woo_url: str
    woo_key: str
    woo_secret: str
    bluefin_url: str
    bluefin_key: str
    add_photos: bool
    set_missing_sku_to_zero: bool
    set_no_sku_to_zero: bool
    add_short_description: bool
    add_long_description: bool
    blacklist_skus: Set[str]
    track_cost_price: bool
    cost_price_field: str

    @classmethod
    def from_file(cls, filename: str = 'config.ini') -> 'Config':
        """Load configuration from file with error handling."""
        try:
            config = configparser.ConfigParser()
            config.read(filename)
            
            # Parse blacklisted SKUs from comma-separated string
            blacklist_skus_str = config['settings'].get('blacklist_skus', '')
            blacklist_skus = {sku.strip() for sku in blacklist_skus_str.split(',') if sku.strip()}
            
            return cls(
                woo_url=config['woocommerce']['url'],
                woo_key=config['woocommerce']['consumer_key'],
                woo_secret=config['woocommerce']['consumer_secret'],
                bluefin_url=config['bluefin']['url'],
                bluefin_key=config['bluefin']['api_key'],
                add_photos=config['settings'].getboolean('add_photos', fallback=True),
                set_missing_sku_to_zero=config['settings'].getboolean('set_missing_sku_to_zero', fallback=True),
                set_no_sku_to_zero=config['settings'].getboolean('set_no_sku_to_zero', fallback=True),
                add_short_description=config['settings'].getboolean('add_short_description', fallback=True),
                add_long_description=config['settings'].getboolean('add_long_description', fallback=True),
                blacklist_skus=blacklist_skus,
                track_cost_price=config['settings'].getboolean('track_cost_price', fallback=True),
                cost_price_field=config['settings'].get('cost_price_field', '_supplier_cost')
            )
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            raise

class WooCommerceSync:
    def __init__(self, config: Config):
        self.config = config
        self.wcapi = API(
            url=config.woo_url,
            consumer_key=config.woo_key,
            consumer_secret=config.woo_secret,
            version="wc/v3",
            timeout=30
        )
        self.session = requests.Session()
        self.session.headers.update({"Authorization": config.bluefin_key})

    @staticmethod
    def validate_sku(sku: str) -> bool:
        """Validate SKU format."""
        import re
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", sku))

    def is_blacklisted(self, sku: str) -> bool:
        """Check if a SKU is blacklisted."""
        return sku in self.config.blacklist_skus

    @sleep_and_retry
    @limits(calls=2, period=1)  # Rate limit to 2 calls per second
    def fetch_stock_data(self) -> Dict:
        """Fetch stock data from Bluefin API with rate limiting and retry logic."""
        params = {"lang_id": 0, "price_drop": 0}
        
        try:
            response = self.session.get(self.config.bluefin_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch stock data: {str(e)}")
            raise

    def filter_stock(self, data: Dict) -> List[Dict]:
        """Filter stock with specific specifications and exclude blacklisted SKUs."""
        return [
            item for item in data.get("stock", [])
            if (item.get("properties", {}).get("item_spec") in ["EU Spec", "Global spec"] and
                not self.is_blacklisted(item.get("sku", "")))
        ]

    def fetch_all_woo_products(self) -> List[Dict]:
        """Fetch all products from WooCommerce with pagination."""
        all_products = []
        page = 1
        
        while True:
            try:
                products = self.wcapi.get("products", params={"per_page": 100, "page": page}).json()
                if not products:
                    break
                all_products.extend(products)
                page += 1
            except Exception as e:
                logger.error(f"Failed to fetch WooCommerce products page {page}: {str(e)}")
                raise
            
        return all_products

    def prepare_product_data(self, product: Dict) -> Dict:
        """Prepare product data for WooCommerce API."""
        data = {
            "name": f"{product['model']} {product['color']}",
            "type": "simple",
            "regular_price": str(product["price"]),
            "categories": [{"name": product["cat_name"]}],
            "stock_quantity": int(product["in_stock"]),
            "manage_stock": True,
            "sku": product["sku"]
        }

        if self.config.add_long_description:
            data["description"] = product["properties"]["full_name"]
        
        if self.config.add_short_description:
            data["short_description"] = f"SKU: {product['sku']} | EAN: {product['ean']}"

        if self.config.add_photos:
            data["images"] = [{"src": product["image"]}]

        # Add cost price as meta data if enabled
        if self.config.track_cost_price:
            data["meta_data"] = [
                {
                    "key": self.config.cost_price_field,
                    "value": str(product["price"]),
                }
            ]

        return data

    def update_product(self, product_id: int, stock_quantity: int, cost_price: Optional[str] = None) -> None:
        """Update product stock and cost price with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                update_data = {"stock_quantity": stock_quantity}
                
                # Add cost price update if provided and tracking is enabled
                if cost_price is not None and self.config.track_cost_price:
                    update_data["meta_data"] = [
                        {
                            "key": self.config.cost_price_field,
                            "value": str(cost_price),
                        }
                    ]
                
                self.wcapi.put(f"products/{product_id}", update_data)
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to update product {product_id} after {max_retries} attempts: {str(e)}")
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff

    def sync_products(self):
        """Main synchronization logic."""
        try:
            # Fetch and filter stock data
            stock_data = self.fetch_stock_data()
            filtered_stock = self.filter_stock(stock_data)
            logger.info(f"Fetched {len(filtered_stock)} products from Bluefin (excluding {len(self.config.blacklist_skus)} blacklisted SKUs)")

            # Get existing WooCommerce products
            existing_products = self.fetch_all_woo_products()
            logger.info(f"Fetched {len(existing_products)} products from WooCommerce")

            # Create lookup dictionary for existing products (excluding blacklisted SKUs)
            existing_product_map = {
                p["sku"]: p for p in existing_products 
                if p.get("sku") and not self.is_blacklisted(p["sku"])
            }

            # Process products in parallel
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                
                # Update or create products
                for product in filtered_stock:
                    if not self.validate_sku(product["sku"]):
                        logger.warning(f"Invalid SKU format: {product['sku']}")
                        continue

                    if product["sku"] in existing_product_map:
                        futures.append(
                            executor.submit(
                                self.update_product,
                                existing_product_map[product["sku"]]["id"],
                                product["in_stock"],
                                product["price"] if self.config.track_cost_price else None
                            )
                        )
                    else:
                        futures.append(
                            executor.submit(
                                self.wcapi.post,
                                "products",
                                self.prepare_product_data(product)
                            )
                        )

                # Handle missing SKUs (excluding blacklisted ones)
                if self.config.set_missing_sku_to_zero:
                    json_skus = {p["sku"] for p in filtered_stock}
                    for existing_product in existing_products:
                        if (existing_product.get("sku") and 
                            existing_product["sku"] not in json_skus and
                            not self.is_blacklisted(existing_product["sku"])):
                            futures.append(
                                executor.submit(
                                    self.update_product,
                                    existing_product["id"],
                                    0
                                )
                            )

                # Handle products with no SKU
                if self.config.set_no_sku_to_zero:
                    for existing_product in existing_products:
                        if not existing_product.get("sku"):
                            futures.append(
                                executor.submit(
                                    self.update_product,
                                    existing_product["id"],
                                    0
                                )
                            )

                # Wait for all operations to complete
                for future in futures:
                    future.result()

            logger.info("Synchronization completed successfully")

        except Exception as e:
            logger.error(f"Synchronization failed: {str(e)}")
            raise

def main():
    try:
        config = Config.from_file()
        syncer = WooCommerceSync(config)
        syncer.sync_products()
    except Exception as e:
        logger.error(f"Program failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()