import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, simpledialog
import threading
from datetime import datetime, timedelta
from config import Config
from shopify_api import ShopifyAPI
from image_downloader import ImageDownloader
from excel_exporter import ExcelExporter
from image_resolver import ProductImageResolver
from excel_updater import update_excel
from product_search import search_product_orders
from data_utils import extract_color_robust, extract_size_robust
from remittance_processor import process_remittance_csv
from utils import logger
import ttkbootstrap as ttk_boot
from ttkbootstrap.constants import *

class ShopifyExporterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Shopify Order Automator v3.5")
        self.root.geometry("1100x950")
        
        Config.load_settings()

        self.orders = []
        self.image_paths = {}
        self.is_fetching = False
        self.is_exporting = False
        
        self.setup_ui()

    def setup_ui(self):
        self.style = ttk_boot.Style(theme="cosmo")
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=BOTH, expand=YES)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 20))
        
        title_label = ttk.Label(header_frame, text="Shopify Order Automator", font=("Helvetica", 24, "bold"), bootstyle=PRIMARY)
        title_label.pack(side=LEFT)
        ttk.Label(header_frame, text="v3.5", font=("Helvetica", 10)).pack(side=LEFT, padx=10, pady=(10, 0))

        # Config Section
        config_frame = ttk.LabelFrame(main_frame, text=" Store Configuration ", padding=15)
        config_frame.pack(fill=X, pady=5)

        ttk.Label(config_frame, text="Store URL:").grid(row=0, column=0, sticky=W, pady=5)
        self.store_url_entry = ttk.Entry(config_frame)
        self.store_url_entry.insert(0, Config.STORE_URL or "")
        self.store_url_entry.grid(row=0, column=1, sticky=(W, E), pady=5, padx=5)

        ttk.Label(config_frame, text="Access Token:").grid(row=0, column=2, sticky=W, pady=5, padx=(20, 0))
        self.token_entry = ttk.Entry(config_frame, show="*")
        self.token_entry.insert(0, Config.ACCESS_TOKEN or "OAUTH_MANAGED")
        self.token_entry.grid(row=0, column=3, sticky=(W, E), pady=5, padx=5)
        
        config_frame.columnconfigure(1, weight=1)
        config_frame.columnconfigure(3, weight=1)

        # Mode Selection & Filters
        middle_frame = ttk.Frame(main_frame)
        middle_frame.pack(fill=X, pady=10)

        # Left: Fetching Mode
        mode_frame = ttk.LabelFrame(middle_frame, text=" Fetching Mode ", padding=15)
        mode_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, 10))

        self.fetch_mode = tk.StringVar(value="latest")
        
        rb_latest = ttk.Radiobutton(mode_frame, text="Latest Orders", variable=self.fetch_mode, value="latest", bootstyle=INFO)
        rb_latest.grid(row=0, column=0, sticky=W, pady=5)
        self.limit_spinbox = ttk.Spinbox(mode_frame, from_=1, to=10000, width=10)
        self.limit_spinbox.set(50)
        self.limit_spinbox.grid(row=0, column=1, sticky=W, padx=10)
        ttk.Label(mode_frame, text="orders").grid(row=0, column=2, sticky=W)

        rb_date = ttk.Radiobutton(mode_frame, text="Date Range", variable=self.fetch_mode, value="date", bootstyle=INFO)
        rb_date.grid(row=1, column=0, sticky=W, pady=5)
        date_inputs = ttk.Frame(mode_frame)
        date_inputs.grid(row=1, column=1, columnspan=2, sticky=W, padx=10)
        ttk.Label(date_inputs, text="From:").pack(side=LEFT)
        self.date_from_entry = ttk.Entry(date_inputs, width=12)
        self.date_from_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))
        self.date_from_entry.pack(side=LEFT, padx=5)
        ttk.Label(date_inputs, text="To:").pack(side=LEFT, padx=(5, 0))
        self.date_to_entry = ttk.Entry(date_inputs, width=12)
        self.date_to_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.date_to_entry.pack(side=LEFT, padx=5)

        rb_order_range = ttk.Radiobutton(mode_frame, text="Order Range", variable=self.fetch_mode, value="order_range", bootstyle=INFO)
        rb_order_range.grid(row=2, column=0, sticky=W, pady=5)
        order_inputs = ttk.Frame(mode_frame)
        order_inputs.grid(row=2, column=1, columnspan=2, sticky=W, padx=10)
        ttk.Label(order_inputs, text="From:").pack(side=LEFT)
        self.order_from_entry = ttk.Entry(order_inputs, width=10)
        self.order_from_entry.pack(side=LEFT, padx=5)
        ttk.Label(order_inputs, text="To:").pack(side=LEFT, padx=(5, 0))
        self.order_to_entry = ttk.Entry(order_inputs, width=10)
        self.order_to_entry.pack(side=LEFT, padx=5)

        # Right: Filters & Options
        filters_frame = ttk.LabelFrame(middle_frame, text=" Export Filters & Options ", padding=15)
        filters_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=(10, 0))

        ttk.Label(filters_frame, text="Order Status:").grid(row=0, column=0, sticky=W, pady=5)
        self.status_var = tk.StringVar(value="any")
        ttk.Combobox(filters_frame, textvariable=self.status_var, values=["any", "unfulfilled", "fulfilled", "cancelled", "archived"], state="readonly").grid(row=0, column=1, sticky=(W, E), pady=5, padx=5)

        ttk.Label(filters_frame, text="Financial:").grid(row=1, column=0, sticky=W, pady=5)
        self.financial_status_var = tk.StringVar(value="any")
        ttk.Combobox(filters_frame, textvariable=self.financial_status_var, values=["any", "authorized", "pending", "paid", "refunded", "voided"], state="readonly").grid(row=1, column=1, sticky=(W, E), pady=5, padx=5)
        
        # Image Checkbox (NEW)
        self.include_images_var = tk.BooleanVar(value=True)
        self.img_checkbox = ttk.Checkbutton(filters_frame, text="Include Product Images", variable=self.include_images_var, bootstyle="round-toggle")
        self.img_checkbox.grid(row=2, column=0, columnspan=2, sticky=W, pady=10)
        
        filters_frame.columnconfigure(1, weight=1)

        # Search Options Section
        search_opt_frame = ttk.LabelFrame(main_frame, text=" Search Product Options (Order Range) ", padding=15)
        search_opt_frame.pack(fill=X, pady=5)

        ttk.Label(search_opt_frame, text="Order Min:").grid(row=0, column=0, sticky=W, pady=5)
        self.search_min_entry = ttk.Entry(search_opt_frame, width=15)
        self.search_min_entry.grid(row=0, column=1, sticky=W, pady=5, padx=5)

        ttk.Label(search_opt_frame, text="Order Max:").grid(row=0, column=2, sticky=W, pady=5, padx=(20, 0))
        self.search_max_entry = ttk.Entry(search_opt_frame, width=15)
        self.search_max_entry.grid(row=0, column=3, sticky=W, pady=5, padx=5)
        
        ttk.Label(search_opt_frame, text="(Leave blank for no limit)", font=("Helvetica", 8, "italic")).grid(row=0, column=4, sticky=W, padx=10)

        # Action Buttons
        actions_frame = ttk.Frame(main_frame, padding=10)
        actions_frame.pack(fill=X, pady=5)
        
        self.fetch_button = ttk.Button(actions_frame, text="1. Fetch Orders", command=self.fetch_orders_thread, bootstyle=INFO, width=25)
        self.fetch_button.pack(side=LEFT, padx=5)

        self.export_button = ttk.Button(actions_frame, text="2. Export to Excel", command=self.export_excel_thread, state=DISABLED, bootstyle=SUCCESS, width=25)
        self.export_button.pack(side=LEFT, padx=5)

        ttk.Separator(actions_frame, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=15)

        self.update_button = ttk.Button(actions_frame, text="Update Existing File", command=self.update_excel_thread, bootstyle=WARNING)
        self.update_button.pack(side=LEFT, padx=5)

        self.search_button = ttk.Button(actions_frame, text="Search Products", command=self.search_product_thread, bootstyle=SECONDARY)
        self.search_button.pack(side=LEFT, padx=5)
        
        self.remittance_button = ttk.Button(actions_frame, text="Generate Remittance Report", command=self.remittance_report_thread, bootstyle=DANGER)
        self.remittance_button.pack(side=LEFT, padx=5)

        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100, bootstyle=(SUCCESS, STRIPED))
        self.progress_bar.pack(fill=X, pady=10)
        
        self.status_label = ttk.Label(main_frame, text="Ready", font=("Helvetica", 10, "italic"))
        self.status_label.pack(anchor=W)

        # Logs
        log_frame = ttk.LabelFrame(main_frame, text=" System Logs ", padding=10)
        log_frame.pack(fill=BOTH, expand=YES, pady=10)
        self.console_log = scrolledtext.ScrolledText(log_frame, height=12, font=("Consolas", 9))
        self.console_log.pack(fill=BOTH, expand=YES)
        self.console_log.config(state=DISABLED)

    def log_to_console(self, message):
        self.console_log.config(state=NORMAL)
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.console_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.console_log.see(tk.END)
        self.console_log.config(state=DISABLED)
        self.root.update_idletasks()

    def fetch_orders_thread(self):
        if self.is_fetching: return
        Config.STORE_URL = self.store_url_entry.get().strip()
        Config.ACCESS_TOKEN = self.token_entry.get().strip()
        Config.save_settings()
        threading.Thread(target=self.fetch_orders, daemon=True).start()

    def fetch_orders(self):
        self.is_fetching = True
        self.fetch_button.config(state=DISABLED)
        self.progress_var.set(0)
        
        mode = self.fetch_mode.get()
        self.log_to_console(f"Fetching orders using mode: {mode}...")
        
        try:
            api = ShopifyAPI()
            self._last_api = api
            
            if mode == "latest":
                limit = int(self.limit_spinbox.get())
                self.orders = api.get_orders(count=limit, status=self.status_var.get(), financial_status=self.financial_status_var.get())
            elif mode == "date":
                date_min = self.date_from_entry.get().strip()
                date_max = self.date_to_entry.get().strip()
                self.orders = api.get_orders(count=10000, status=self.status_var.get(), financial_status=self.financial_status_var.get(), created_at_min=f"{date_min}T00:00:00Z", created_at_max=f"{date_max}T23:59:59Z")
            elif mode == "order_range":
                o_from = int(self.order_from_entry.get().strip())
                o_to = int(self.order_to_entry.get().strip())
                self.orders = api.get_orders(status=self.status_var.get(), financial_status=self.financial_status_var.get(), order_min=o_from, order_max=o_to)
            
            self.log_to_console(f"Successfully retrieved {len(self.orders)} orders.")
            self.status_label.config(text=f"Fetched {len(self.orders)} orders")
            self.progress_var.set(100)
            self.export_button.config(state=NORMAL)
        except Exception as e:
            self.log_to_console(f"ERROR: {str(e)}")
            messagebox.showerror("Fetch Error", str(e))
        finally:
            self.is_fetching = False
            self.fetch_button.config(state=NORMAL)

    def export_excel_thread(self):
        if self.is_exporting: return
        threading.Thread(target=self.export_excel, daemon=True).start()

    def export_excel(self):
        self.is_exporting = True
        self.export_button.config(state=DISABLED)
        include_images = self.include_images_var.get()
        self.log_to_console(f"Starting Export (Images: {'YES' if include_images else 'NO'})...")
        
        try:
            downloader = ImageDownloader(max_workers=10)
            exporter = ExcelExporter()
            api = getattr(self, '_last_api', ShopifyAPI())
            resolver = ProductImageResolver(api)
            
            image_tasks = []
            orders_data_temp = []
            
            for order in self.orders:
                for item in order.get("line_items", []):
                    p_id = item.get("product_id")
                    v_id = item.get("variant_id")
                    
                    if include_images and p_id:
                        url = resolver.get_image_url(item)
                        if url: image_tasks.append((url, f"{p_id}_{v_id}"))
                    
                    orders_data_temp.append((order, item))

            image_paths = {}
            if include_images and image_tasks:
                self.log_to_console(f"Downloading {len(image_tasks)} images...")
                downloaded_paths = downloader.download_images_parallel(image_tasks, log_fn=self.log_to_console)
                for fid, path in downloaded_paths.items():
                    parts = fid.split("_")
                    p_id, v_id = int(parts[0]), int(parts[1]) if len(parts) > 1 else None
                    image_paths[(p_id, v_id)] = str(path) if path else None

            final_data = []
            for order, item in orders_data_temp:
                p_id = item.get("product_id")
                product = resolver._product_cache.get(p_id) if p_id else None
                final_data.append({
                    "order_number": f"#{order.get('order_number')}",
                    "customer_name": f"{order.get('customer', {}).get('first_name', '')} {order.get('customer', {}).get('last_name', '')}".strip(),
                    "customer_email": order.get("customer", {}).get("email", ""),
                    "phone_number": order.get("customer", {}).get("phone", ""),
                    "product_name": item.get("title"),
                    "variant_name": item.get("variant_title"),
                    "color": extract_color_robust(item, product),
                    "size": extract_size_robust(item, product),
                    "price": item.get("price"),
                    "payment_status": order.get("financial_status", ""),
                    "product_id": p_id,
                    "variant_id": item.get("variant_id")
                })

            file_path = exporter.export_orders_to_excel(final_data, image_paths, include_images=include_images)
            messagebox.showinfo("Export Success", f"Excel file generated successfully!")
            
        except Exception as e:
            self.log_to_console(f"EXPORT ERROR: {str(e)}")
            messagebox.showerror("Export Error", str(e))
        finally:
            self.is_exporting = False
            self.export_button.config(state=NORMAL)

    def update_excel_thread(self):
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        if not path: return
        threading.Thread(target=self.run_update_excel, args=(path,), daemon=True).start()

    def run_update_excel(self, path):
        self.update_button.config(state=DISABLED)
        try:
            update_excel(path, log_fn=self.log_to_console, progress_fn=self.progress_var.set, status_fn=lambda m: self.status_label.config(text=m))
            messagebox.showinfo("Update Success", "File updated successfully!")
        except Exception as e:
            messagebox.showerror("Update Error", str(e))
        finally:
            self.update_button.config(state=NORMAL)

    def search_product_thread(self):
        query = simpledialog.askstring("Search", "Product name or keyword:")
        if not query: return
        try:
            min_val, max_val = self.search_min_entry.get().strip(), self.search_max_entry.get().strip()
            order_min, order_max = int(min_val) if min_val else None, int(max_val) if max_val else None
        except ValueError:
            messagebox.showerror("Input Error", "Order range must be numeric.")
            return
        threading.Thread(target=self.run_search, args=(query, order_min, order_max), daemon=True).start()

    def run_search(self, query, order_min, order_max):
        self.log_to_console(f"Searching for '{query}'...")
        try:
            api = getattr(self, '_last_api', ShopifyAPI())
            resolver, downloader = ProductImageResolver(api), ImageDownloader()
            results, _ = search_product_orders(api=api, search_term=query, resolver=resolver, downloader=downloader, order_min=order_min, order_max=order_max, log_fn=self.log_to_console, progress_fn=self.progress_var.set, status_fn=lambda m: self.status_label.config(text=m))
            if results: self.show_search_results(results)
            else: messagebox.showinfo("Search", "No matches found.")
        except Exception as e:
            messagebox.showerror("Search Error", str(e))

    def show_search_results(self, results):
        win = tk.Toplevel(self.root)
        win.title(f"Search Results: {len(results)} found")
        win.geometry("900x600")
        frame = ttk.Frame(win, padding=20)
        frame.pack(fill=BOTH, expand=YES)
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=BOTH, expand=YES, pady=(0, 15))
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        tree = ttk.Treeview(tree_frame, columns=("Order", "Date", "Product", "Variant", "Customer"), show="headings", yscrollcommand=scrollbar.set)
        for col in ("Order", "Date", "Product", "Variant", "Customer"): tree.heading(col, text=col)
        for r in results: tree.insert("", tk.END, values=(r.get("order_number"), r.get("order_date"), r.get("product_name"), r.get("variant_name"), r.get("customer_name")))
        tree.pack(fill=BOTH, expand=YES)
        scrollbar.config(command=tree.yview)
        
        def export_search_results():
            try:
                include_images = self.include_images_var.get()
                api = getattr(self, '_last_api', ShopifyAPI())
                resolver, downloader, exporter = ProductImageResolver(api), ImageDownloader(max_workers=10), ExcelExporter()
                
                image_tasks = []
                if include_images:
                    for r in results:
                        url = resolver.get_image_url(r.get("line_item"))
                        if url: image_tasks.append((url, f"{r.get('product_id')}_{r.get('variant_id')}"))
                
                search_image_paths = {}
                if include_images and image_tasks:
                    downloaded = downloader.download_images_parallel(image_tasks, log_fn=self.log_to_console)
                    for fid, path in downloaded.items():
                        parts = fid.split("_")
                        search_image_paths[(int(parts[0]), int(parts[1]) if len(parts) > 1 else None)] = str(path) if path else None
                
                exporter.export_orders_to_excel(results, search_image_paths, include_images=include_images)
                messagebox.showinfo("Export Success", "Search results exported!")
                win.destroy()
            except Exception as e: messagebox.showerror("Export Error", str(e))

        ttk.Button(frame, text="Export to Excel", command=lambda: threading.Thread(target=export_search_results, daemon=True).start(), bootstyle=SUCCESS).pack(side=LEFT)
        ttk.Button(frame, text="Close", command=win.destroy, bootstyle=SECONDARY).pack(side=RIGHT)

    def remittance_report_thread(self):
        o_from = simpledialog.askstring("Remittance Report", "Starting Order Number (e.g. 1600):")
        if not o_from: return
        o_to = simpledialog.askstring("Remittance Report", "Ending Order Number (Optional, leave blank for latest):")
        csv_path = filedialog.askopenfilename(title="Select iThink Logistics Remittance CSV", filetypes=[("CSV files", "*.csv")])
        if not csv_path: return
        threading.Thread(target=self.run_remittance_report, args=(o_from, o_to, csv_path), daemon=True).start()

    def run_remittance_report(self, o_from, o_to, csv_path):
        self.remittance_button.config(state=DISABLED)
        self.progress_var.set(0)
        include_images = self.include_images_var.get()
        try:
            remittance_data = process_remittance_csv(csv_path)
            api = ShopifyAPI()
            self._last_api = api
            resolver, downloader, exporter = ProductImageResolver(api), ImageDownloader(max_workers=10), ExcelExporter()
            
            shopify_orders = api.get_orders(order_min=int(o_from), order_max=int(o_to) if o_to else None)
            
            image_tasks, orders_data = [], []
            for order in shopify_orders:
                for item in order.get("line_items", []):
                    p_id, v_id = item.get("product_id"), item.get("variant_id")
                    if include_images and p_id:
                        url = resolver.get_image_url(item)
                        if url: image_tasks.append((url, f"{p_id}_{v_id}"))
                    
                    product = resolver._product_cache.get(p_id)
                    orders_data.append({
                        "order_number": f"#{order.get('order_number')}",
                        "customer_name": f"{order.get('customer', {}).get('first_name', '')} {order.get('customer', {}).get('last_name', '')}".strip(),
                        "customer_email": order.get("customer", {}).get("email", ""),
                        "phone_number": order.get("customer", {}).get("phone", ""),
                        "product_name": item.get("title"),
                        "variant_name": item.get("variant_title"),
                        "color": extract_color_robust(item, product),
                        "size": extract_size_robust(item, product),
                        "price": item.get("price"),
                        "payment_status": order.get("financial_status", ""),
                        "product_id": p_id,
                        "variant_id": v_id
                    })

            image_paths = {}
            if include_images and image_tasks:
                downloaded = downloader.download_images_parallel(image_tasks, log_fn=self.log_to_console)
                for fid, path in downloaded.items():
                    parts = fid.split("_")
                    image_paths[(int(parts[0]), int(parts[1]) if len(parts) > 1 else None)] = str(path) if path else None

            exporter.export_orders_to_excel(orders_data, image_paths, remittance_data=remittance_data, is_remittance_report=True, include_images=include_images)
            messagebox.showinfo("Success", "Remittance Report generated!")
        except Exception as e: messagebox.showerror("Remittance Error", str(e))
        finally:
            self.remittance_button.config(state=NORMAL)
            self.progress_var.set(100)

def main():
    root = ttk_boot.Window(themename="cosmo")
    app = ShopifyExporterGUI(root)
    root.mainloop()

if __name__ == "__main__": main()
