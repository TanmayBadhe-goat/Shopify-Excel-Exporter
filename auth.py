import os
import json
import urllib.parse
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from config import Config
from utils import logger

TOKEN_FILE = "shopify_token.json"

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == '/callback':
            query_components = urllib.parse.parse_qs(parsed_path.query)
            if 'code' in query_components:
                self.server.auth_code = query_components['code'][0]
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"<html><body><h2>Authentication successful!</h2><p>You can close this window and return to the application.</p></body></html>")
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"<html><body><h2>Authentication failed!</h2><p>No code returned.</p></body></html>")
            
            # Stop the server after receiving the callback
            threading.Thread(target=self.server.shutdown).start()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress standard logging to keep console clean
        pass

class ShopifyAuth:
    def __init__(self):
        self.scopes = "read_orders,read_products"
        self.port = 8080
        self.redirect_uri = f"http://localhost:{self.port}/callback"
        self.token_cache = self._load_token()

    def _load_token(self):
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading token cache: {e}")
        return None

    def _save_token(self, token_data):
        try:
            with open(TOKEN_FILE, 'w') as f:
                json.dump(token_data, f)
            self.token_cache = token_data
        except Exception as e:
            logger.error(f"Error saving token cache: {e}")

    def clear_token(self):
        self.token_cache = None
        if os.path.exists(TOKEN_FILE):
            try:
                os.remove(TOKEN_FILE)
                logger.info("Cleared cached authentication token.")
            except Exception as e:
                logger.error(f"Error removing token file: {e}")

    def get_shop(self):
        # The GUI writes the store URL to Config.STORE_URL, but it can also come from .env
        shop = Config.STORE_URL or Config.SHOPIFY_SHOP
        if not shop:
            raise ValueError("Store URL (SHOPIFY_SHOP) must be provided in the configuration.")
        return shop.replace("https://", "").replace("http://", "").split("/")[0]

    def authenticate(self):
        shop = self.get_shop()
        client_id = Config.SHOPIFY_CLIENT_ID
        client_secret = Config.SHOPIFY_CLIENT_SECRET
        
        if not client_id or not client_secret:
            raise ValueError("SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET must be configured in the .env file.")

        auth_url = f"https://{shop}/admin/oauth/authorize?client_id={client_id}&scope={self.scopes}&redirect_uri={self.redirect_uri}"
        
        logger.info(f"Opening browser for authentication: {auth_url}")
        
        server = HTTPServer(('localhost', self.port), OAuthCallbackHandler)
        server.auth_code = None
        
        webbrowser.open(auth_url)
        
        logger.info(f"Waiting for authorization callback on port {self.port}...")
        # serve_forever blocks until server.shutdown() is called in the handler
        server.serve_forever()
        
        if not server.auth_code:
            raise Exception("Failed to get authorization code. Authentication aborted.")
            
        logger.info("Authorization code received. Exchanging for access token...")
        
        token_url = f"https://{shop}/admin/oauth/access_token"
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": server.auth_code
        }
        
        response = requests.post(token_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            self._save_token(token_data)
            logger.info("Access token successfully acquired and saved.")
            return token_data.get("access_token")
        else:
            error_msg = f"Failed to get access token: {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def get_access_token(self):
        # Return cached token if available
        if self.token_cache and "access_token" in self.token_cache:
            return self.token_cache["access_token"]
            
        logger.info("No valid access token found in cache. Starting authentication flow.")
        return self.authenticate()

# Singleton instance
auth_manager = ShopifyAuth()

def get_access_token():
    return auth_manager.get_access_token()

def clear_token():
    auth_manager.clear_token()
