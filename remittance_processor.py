import csv
import re
from pathlib import Path
from utils import logger

# Robust aliases for column detection
# These will be matched against NORMALIZED headers
_ORDER_NUMBER_ALIASES = {"orderno", "ordernumber", "orderid", "order"}
_AMOUNT_ALIASES       = {"price", "amount", "remittanceamount", "codamount", "billingamount"}
_DATE_ALIASES         = {"remittancedate", "date", "paymentdate", "billingdate"}

def normalize_header(header: str) -> str:
    """
    Normalize header by:
    - Converting to lowercase
    - Removing all non-alphanumeric characters (punctuation, spaces, etc.)
    """
    if not header:
        return ""
    # Remove all non-alphanumeric characters and lowercase
    return re.sub(r'[^a-zA-Z0-9]', '', header).lower()

def process_remittance_csv(filepath: str):
    """
    Read the iThink Logistics Remittance CSV and create a lookup dictionary.
    Uses robust column detection via header normalization.
    
    Returns
    -------
    dict
        { "order_number": {"amount": float, "date": str} }
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Remittance CSV not found: {filepath}")

    logger.info("Reading Remittance CSV...")
    remittance_data = {}
    
    try:
        with open(path, mode='r', encoding='utf-8-sig') as f:
            # Use DictReader to handle headers automatically
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            if not headers:
                raise ValueError("CSV file is empty or has no headers.")

            # Detect columns using normalized aliases
            col_map = {}
            detected_names = {}
            
            for h in headers:
                norm_h = normalize_header(h)
                
                if norm_h in _ORDER_NUMBER_ALIASES and "order_number" not in col_map:
                    col_map["order_number"] = h
                    detected_names["Order Number"] = h
                elif norm_h in _AMOUNT_ALIASES and "amount" not in col_map:
                    col_map["amount"] = h
                    detected_names["Amount"] = h
                elif norm_h in _DATE_ALIASES and "date" not in col_map:
                    col_map["date"] = h
                    detected_names["Date"] = h

            # Log detected mappings
            for label, original in detected_names.items():
                logger.info(f"Detected {label} column: {original}")

            # Validate required columns
            if "order_number" not in col_map:
                logger.error(f"Available columns: {headers}")
                raise ValueError(f"Could not find Order Number column. (Tried aliases: {_ORDER_NUMBER_ALIASES})")
            
            # Read rows and populate dictionary
            for row in reader:
                raw_order = str(row.get(col_map["order_number"]) or "").strip()
                # Clean order number (remove # if present)
                order_num = raw_order.lstrip("#").strip()
                
                if not order_num:
                    continue
                
                amount = row.get(col_map.get("amount", "")) or "0"
                date = row.get(col_map.get("date", "")) or ""
                
                remittance_data[order_num] = {
                    "amount": amount,
                    "date": date
                }

        logger.info(f"Loaded {len(remittance_data)} remittance records.")
        return remittance_data

    except Exception as e:
        logger.error(f"Error processing Remittance CSV: {e}")
        raise
