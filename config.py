import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Defaults from .env
    SHOPIFY_SHOP = os.getenv("SHOPIFY_SHOP", "")
    SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID", "")
    SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET", "")
    API_VERSION = os.getenv("API_VERSION", "2024-04")
    
    # GUI runtime state
    STORE_URL = SHOPIFY_SHOP
    ACCESS_TOKEN = "OAUTH_MANAGED"
    
    SETTINGS_FILE = Path("user_settings.json")

    @classmethod
    def load_settings(cls):
        """Load settings from a local JSON file."""
        if cls.SETTINGS_FILE.exists():
            try:
                with open(cls.SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                    cls.STORE_URL = data.get("store_url", cls.STORE_URL)
                    cls.API_VERSION = data.get("api_version", cls.API_VERSION)
                    cls.ACCESS_TOKEN = data.get("access_token", cls.ACCESS_TOKEN)
            except Exception:
                pass

    @classmethod
    def save_settings(cls):
        """Save current settings to a local JSON file."""
        try:
            data = {
                "store_url": cls.STORE_URL,
                "api_version": cls.API_VERSION,
                "access_token": cls.ACCESS_TOKEN
            }
            with open(cls.SETTINGS_FILE, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

    @classmethod
    def validate_config(cls):
        shop = cls.STORE_URL or cls.SHOPIFY_SHOP
        if not shop:
            raise ValueError("Store URL is missing. Please provide it in .env or the GUI.")
        if not cls.SHOPIFY_CLIENT_ID or not cls.SHOPIFY_CLIENT_SECRET:
            raise ValueError("Shopify Client ID or Secret is missing in .env file.")
