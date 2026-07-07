import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import auth
from config import Config
from utils import logger


class ShopifyAPI:
    def __init__(self):
        Config.validate_config()

        shop = Config.STORE_URL or Config.SHOPIFY_SHOP or ""
        store_url = (
            shop.replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
        )

        self.base_url = f"https://{store_url}/admin/api/{Config.API_VERSION}"
        self.session = self._setup_session()

    def _setup_session(self):
        """Setup a requests session with retry logic."""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get_headers(self):
        token = auth.get_access_token()

        return {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _make_request(self, endpoint, params=None, retry_auth=True):
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers()

        try:
            response = self.session.get(
                url,
                headers=headers,
                params=params,
                timeout=30
            )

            # Handle token expiration
            if response.status_code == 401 and retry_auth:
                logger.warning("Token expired or invalid. Re-authenticating...")
                auth.clear_token()
                headers = self._get_headers()
                response = self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=30
                )

            response.raise_for_status()
            return response

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection Error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in API request: {str(e)}")
            raise

    def get_orders(
        self,
        count=50,
        created_at_min=None,
        created_at_max=None,
        status="any",
        fulfillment_status="any",
        financial_status="any",
        order_min=None,
        order_max=None
    ):
        """Fetch orders with optional filters and pagination."""
        orders = []
        page_info = None
        page_size = 250 if (order_min or order_max) else min(count, 250)

        # For order number range, we iterate until we hit the range boundaries
        while True:
            if page_info:
                params = {
                    "limit": page_size,
                    "page_info": page_info,
                }
            else:
                params = {
                    "limit": page_size,
                    "status": status,
                    "fulfillment_status": fulfillment_status,
                    "financial_status": financial_status,
                    "order": "created_at desc",
                }
                if created_at_min:
                    params["created_at_min"] = created_at_min
                if created_at_max:
                    params["created_at_max"] = created_at_max

            logger.info(f"Fetching batch of orders... (Current count: {len(orders)})")
            response = self._make_request("orders.json", params=params)
            data = response.json()
            batch = data.get("orders", [])
            
            if not batch:
                break
            
            # Filter by order number range if specified
            if order_min is not None or order_max is not None:
                in_range_batch = []
                stop_fetching = False
                
                # Normalize range
                mn = min(order_min, order_max) if (order_min and order_max) else (order_min or 0)
                mx = max(order_min, order_max) if (order_min and order_max) else (order_max or 999999999)

                for o in batch:
                    num = o.get("order_number")
                    if num is not None:
                        if mn <= num <= mx:
                            in_range_batch.append(o)
                        elif num < mn:
                            # Since orders are desc, if we're below mn, we can stop
                            stop_fetching = True
                            break
                
                orders.extend(in_range_batch)
                if stop_fetching:
                    break
            else:
                orders.extend(batch)
                if len(orders) >= count:
                    orders = orders[:count]
                    break

            link_header = response.headers.get("Link")
            page_info = self._get_next_page_info(link_header)
            if not page_info:
                break

        logger.info(f"Successfully fetched {len(orders)} orders.")
        return orders

    def _get_next_page_info(self, link_header):
        if not link_header:
            return None

        links = link_header.split(",")
        for link in links:
            if 'rel="next"' in link:
                start = link.find("page_info=")
                if start == -1:
                    continue
                start += len("page_info=")
                end = link.find(">")
                value = link[start:end]
                value = value.split("&")[0]
                return value
        return None

    def get_product(self, product_id):
        if not product_id:
            return None
        try:
            response = self._make_request(f"products/{product_id}.json")
            return response.json().get("product")
        except Exception as e:
            logger.error(f"Failed to fetch product {product_id}: {e}")
            return None
