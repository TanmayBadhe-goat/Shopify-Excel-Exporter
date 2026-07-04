# Shopify Order Automator v3.0

A professional, modular Python desktop application designed to streamline Shopify order management. This tool connects to your Shopify store via the Admin API to generate beautifully formatted Excel reports, complete with product images and enriched data.

## 🚀 New in v3.0: Dual Fetching Modes

- **Latest Orders Mode**: Fetch exactly the number of recent orders you need (e.g., the last 50, 100, or 500 orders), regardless of when they were placed.
- **Date Range Mode**: Fetch all orders within a specific date range (e.g., from `2026-06-01` to `2026-06-30`) with no arbitrary limit.
- **Improved Date Handling**: Switched to a more robust YYYY-MM-DD input format to eliminate warnings and ensure 100% compatibility with the Shopify API.

## ✨ Advanced Features

- **Parallel Image Processing**: Uses `ThreadPoolExecutor` to download multiple product images simultaneously, reducing export time by up to 80%.
- **Configuration Persistence**: Automatically saves and loads your Store URL and API settings.
- **Enhanced Search Experience**: A dedicated search results window for finding specific products in your order history.
- **Smart Image Resolution**: Automatically finds the correct variant-specific image for every line item.
- **Existing File Enrichment**: Update your own Excel files by adding missing images, colors, and sizes based on order numbers.

## 🛠 Technology Stack

- **Python 3.12+**
- **requests**: Robust HTTP communication with retry logic.
- **openpyxl**: Advanced Excel manipulation and image embedding.
- **Pillow**: Image processing and optimization.
- **ttkbootstrap**: Modern, themed desktop GUI components.
- **python-dotenv**: Secure environment variable management.
- **concurrent.futures**: Multi-threaded processing for high-speed downloads.

## 📥 Installation

### Prerequisites
- Python 3.12 or higher.
- A Shopify Store with Admin API access.
- Shopify App credentials (Client ID & Secret) with `read_orders` and `read_products` scopes.

### Setup
1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd ShopifyOrderExporter
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure environment**:
   - Copy `.env.example` to `.env`.
   - Fill in your `SHOPIFY_SHOP`, `SHOPIFY_CLIENT_ID`, and `SHOPIFY_CLIENT_SECRET`.

## 📖 Usage

### Running the App
```bash
python main.py
```

### Main Workflows
1. **Standard Export**:
   - Choose your **Fetching Mode** (Latest Orders or Date Range).
   - Click **Fetch Orders** to retrieve data.
   - Click **Export to Excel** to generate the file.
2. **Update Existing File**:
   - Click **Update Existing File** and select your `.xlsx` file.
   - The app will match order numbers and fill in missing data.
3. **Search**:
   - Use the **Search Products** button to find specific items.

---
