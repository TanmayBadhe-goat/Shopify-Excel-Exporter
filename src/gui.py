import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, simpledialog
import threading
from datetime import datetime, timedelta
from .config import Config
from .shopify_api import ShopifyAPI
from .image_downloader import ImageDownloader
from .excel_exporter import ExcelExporter
from .image_resolver import ProductImageResolver
from .excel_updater import update_excel
from .product_search import search_product_orders
from .remittance_processor import process_remittance_csv
from .database import DatabaseManager, get_db
from .database_sync import DatabaseSync
from .customer_search import DatabaseSearch
from .settings_window import SettingsWindow
from .column_selector import ColumnSelectorDialog, get_enabled_columns
from .image_cache_manager import get_image_cache
from .order_data_builder import OrderDataBuilder
from .utils import logger
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
        
        # Settings gear button (added to header, right-aligned)
        self.settings_button = ttk.Button(header_frame, text="⚙ Settings", command=self.open_settings, bootstyle=SECONDARY)
        self.settings_button.pack(side=RIGHT)

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
        
        # === NEW: Database Sync & Search Buttons ===
        ttk.Separator(actions_frame, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=15)
        
        self.sync_all_button = ttk.Button(actions_frame, text="Sync All Orders", command=self.sync_all_thread, bootstyle=PRIMARY)
        self.sync_all_button.pack(side=LEFT, padx=5)
        
        self.sync_latest_button = ttk.Button(actions_frame, text="Sync Latest Orders", command=self.sync_latest_thread, bootstyle=PRIMARY)
        self.sync_latest_button.pack(side=LEFT, padx=5)
        
        self.db_search_button = ttk.Button(actions_frame, text="Database Search", command=self.db_search_thread, bootstyle=SECONDARY)
        self.db_search_button.pack(side=LEFT, padx=5)

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
            
            # Use OrderDataBuilder for uniform data preparation
            image_tasks = OrderDataBuilder.collect_image_tasks(
                self.orders, resolver, include_images
            )
            
            image_paths = {}
            if include_images and image_tasks:
                self.log_to_console(f"Downloading {len(image_tasks)} images...")
                downloaded_paths = downloader.download_images_parallel(
                    image_tasks, log_fn=self.log_to_console
                )
                image_paths = OrderDataBuilder.build_image_paths(downloaded_paths)

            final_data = OrderDataBuilder.build_all_items(
                self.orders, resolver._product_cache
            )

            enabled_cols = get_enabled_columns()
            file_path = exporter.export_orders_to_excel(
                final_data, image_paths,
                include_images=include_images,
                enabled_columns=enabled_cols,
            )
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
            results, _ = search_product_orders(api=api, search_term=query, resolver=resolver, order_min=order_min, order_max=order_max, log_fn=self.log_to_console, progress_fn=self.progress_var.set, status_fn=lambda m: self.status_label.config(text=m))
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
                resolver = ProductImageResolver(api)
                downloader = ImageDownloader(max_workers=10)
                exporter = ExcelExporter()
                
                # Search results are flat dicts (not Shopify orders), so collect
                # image tasks directly from each result's 'line_item' key
                image_tasks = []
                if include_images:
                    for r in results:
                        line_item = r.get("line_item")
                        if line_item:
                            url = resolver.get_image_url(line_item)
                            if url:
                                image_tasks.append(
                                    (url, f"{r.get('product_id')}_{r.get('variant_id')}")
                                )
                
                search_image_paths = {}
                if include_images and image_tasks:
                    downloaded = downloader.download_images_parallel(
                        image_tasks, log_fn=self.log_to_console
                    )
                    search_image_paths = OrderDataBuilder.build_image_paths(downloaded)
                
                enabled_cols = get_enabled_columns()
                exporter.export_orders_to_excel(
                    results, search_image_paths,
                    include_images=include_images,
                    enabled_columns=enabled_cols,
                )
                messagebox.showinfo("Export Success", "Search results exported!")
                win.destroy()
            except Exception as e:
                logger.exception("Search export failed")
                messagebox.showerror("Export Error", str(e))

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
            
            image_tasks = OrderDataBuilder.collect_image_tasks(
                shopify_orders, resolver, include_images
            )
            orders_data = OrderDataBuilder.build_all_items(
                shopify_orders, resolver._product_cache
            )

            image_paths = {}
            if include_images and image_tasks:
                downloaded = downloader.download_images_parallel(
                    image_tasks, log_fn=self.log_to_console
                )
                image_paths = OrderDataBuilder.build_image_paths(downloaded)

            enabled_cols = get_enabled_columns()
            exporter.export_orders_to_excel(
                orders_data, image_paths,
                remittance_data=remittance_data,
                is_remittance_report=True,
                include_images=include_images,
                enabled_columns=enabled_cols,
            )
            messagebox.showinfo("Success", "Remittance Report generated!")
        except Exception as e:
            messagebox.showerror("Remittance Error", str(e))
        finally:
            self.remittance_button.config(state=NORMAL)
            self.progress_var.set(100)

    # ═══════════════════════════════════════════════════════════════════
    # NEW: Database Sync Methods
    # ═══════════════════════════════════════════════════════════════════

    def sync_all_thread(self):
        if self.is_fetching:
            return
        Config.STORE_URL = self.store_url_entry.get().strip()
        Config.ACCESS_TOKEN = self.token_entry.get().strip()
        Config.save_settings()
        threading.Thread(target=self.sync_all, daemon=True).start()

    def sync_all(self):
        self.is_fetching = True
        self.sync_all_button.config(state=DISABLED)
        self.progress_var.set(0)
        try:
            # Initialize database if needed
            get_db().initialize()
            
            api = ShopifyAPI()
            self._last_api = api
            resolver = ProductImageResolver(api)
            syncer = DatabaseSync(api=api, resolver=resolver)
            
            saved = syncer.sync_all(
                progress_fn=self.progress_var.set,
                log_fn=self.log_to_console,
                status_fn=lambda m: self.status_label.config(text=m),
            )
            if saved > 0:
                self.log_to_console(f"Sync complete: {saved} orders saved to local database.")
                self.status_label.config(text=f"Database: {saved} orders synced")
                messagebox.showinfo("Sync Complete", f"{saved} orders synchronized to local database.")
            else:
                self.log_to_console("No orders were synced.")
        except Exception as e:
            self.log_to_console(f"SYNC ERROR: {str(e)}")
            messagebox.showerror("Sync Error", str(e))
        finally:
            self.is_fetching = False
            self.sync_all_button.config(state=NORMAL)
            self.progress_var.set(100)

    def sync_latest_thread(self):
        if self.is_fetching:
            return
        Config.STORE_URL = self.store_url_entry.get().strip()
        Config.ACCESS_TOKEN = self.token_entry.get().strip()
        Config.save_settings()
        threading.Thread(target=self.sync_latest, daemon=True).start()

    def sync_latest(self):
        self.is_fetching = True
        self.sync_latest_button.config(state=DISABLED)
        self.progress_var.set(0)
        try:
            get_db().initialize()
            
            api = ShopifyAPI()
            self._last_api = api
            resolver = ProductImageResolver(api)
            syncer = DatabaseSync(api=api, resolver=resolver)
            
            saved = syncer.sync_latest(
                count=250,
                progress_fn=self.progress_var.set,
                log_fn=self.log_to_console,
                status_fn=lambda m: self.status_label.config(text=m),
            )
            if saved > 0:
                self.log_to_console(f"Sync complete: {saved} orders saved to local database.")
                self.status_label.config(text=f"Database: {saved} orders synced")
                messagebox.showinfo("Sync Complete", f"{saved} orders synchronized to local database.")
            else:
                self.log_to_console("No orders were synced.")
        except Exception as e:
            self.log_to_console(f"SYNC ERROR: {str(e)}")
            messagebox.showerror("Sync Error", str(e))
        finally:
            self.is_fetching = False
            self.sync_latest_button.config(state=NORMAL)
            self.progress_var.set(100)

    # ═══════════════════════════════════════════════════════════════════
    # NEW: Database Search Method
    # ═══════════════════════════════════════════════════════════════════

    def db_search_thread(self):
        """Open enhanced search dialog with database + API fallback."""
        search_win = tk.Toplevel(self.root)
        search_win.title("Database Search")
        search_win.geometry("650x500")
        search_win.transient(self.root)
        search_win.grab_set()

        frame = ttk.Frame(search_win, padding=15)
        frame.pack(fill="both", expand=True)

        # Search type selector
        ttk.Label(frame, text="Search by:", font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=5
        )
        search_type_var = tk.StringVar(value="product")
        type_combo = ttk.Combobox(
            frame,
            textvariable=search_type_var,
            values=["product", "customer", "order"],
            state="readonly",
            width=15,
        )
        type_combo.grid(row=0, column=1, sticky="w", pady=5, padx=5)

        # Query input
        ttk.Label(frame, text="Query:", font=("Helvetica", 10, "bold")).grid(
            row=1, column=0, sticky="w", pady=5
        )
        query_var = tk.StringVar()
        query_entry = ttk.Entry(frame, textvariable=query_var, width=50)
        query_entry.grid(row=1, column=1, columnspan=3, sticky="we", pady=5, padx=5)

        # Search button
        def do_search():
            search_type = search_type_var.get()
            query = query_var.get().strip()
            if not query:
                messagebox.showinfo("Search", "Please enter a search query.", parent=search_win)
                return

            threading.Thread(
                target=lambda: self._run_db_search(
                    search_type, query, search_win
                ),
                daemon=True,
            ).start()
            # Disable search button during search
            search_btn.config(state=DISABLED)
            status_lbl.config(text="Searching...")

        search_btn = ttk.Button(
            frame, text="Search", command=do_search, bootstyle=SUCCESS, width=15
        )
        search_btn.grid(row=1, column=4, sticky="w", pady=5, padx=10)

        # Status label
        status_lbl = ttk.Label(frame, text="", font=("Helvetica", 9, "italic"))
        status_lbl.grid(row=2, column=0, columnspan=5, sticky="w", pady=(0, 10))

        frame.columnconfigure(1, weight=1)

        # Results area
        result_frame = ttk.Frame(frame)
        result_frame.grid(row=3, column=0, columnspan=5, sticky="nsew", pady=5)
        frame.rowconfigure(3, weight=1)

        columns = ("Order", "Product", "Customer", "Details")
        tree = ttk.Treeview(
            result_frame, columns=columns, show="headings", height=15
        )
        tree.heading("Order", text="Order #")
        tree.heading("Product", text="Product")
        tree.heading("Customer", text="Customer")
        tree.heading("Details", text="Details")
        tree.column("Order", width=80)
        tree.column("Product", width=200)
        tree.column("Customer", width=150)
        tree.column("Details", width=180)

        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Store references for use in _run_db_search callback
        search_win._result_tree = tree
        search_win._status_label = status_lbl
        search_win._search_btn = search_btn
        search_results = []
        search_win._search_results = search_results

        # Export results button
        def export_search_results():
            if not search_results:
                messagebox.showinfo("Export", "No results to export.", parent=search_win)
                return
            try:
                from excel_exporter import ExcelExporter
                exporter = ExcelExporter()
                enabled_cols = get_enabled_columns()
                exporter.export_orders_to_excel(
                    search_results,
                    {},
                    include_images=False,
                    enabled_columns=enabled_cols,
                )
                messagebox.showinfo(
                    "Exported", "Search results exported to Excel.", parent=search_win
                )
            except Exception as e:
                messagebox.showerror("Export Error", str(e), parent=search_win)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=5, sticky="we", pady=(10, 0))

        ttk.Button(
            btn_frame,
            text="Export Results to Excel",
            command=export_search_results,
            bootstyle=SUCCESS,
        ).pack(side="left", padx=2)
        ttk.Button(
            btn_frame,
            text="Close",
            command=search_win.destroy,
            bootstyle=SECONDARY,
        ).pack(side="right", padx=2)

        # Center and show
        search_win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - search_win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - search_win.winfo_height()) // 2
        search_win.geometry(f"+{x}+{y}")
        query_entry.focus()

    def _run_db_search(self, search_type, query, search_win):
        """Execute search with DB → API fallback."""
        try:
            # Ensure database is initialized
            get_db().initialize()

            api = getattr(self, '_last_api', None) or ShopifyAPI()
            searcher = DatabaseSearch(api=api)

            if search_type == "product":
                # Try order range from search options if available
                min_val = self.search_min_entry.get().strip()
                max_val = self.search_max_entry.get().strip()
                order_min = int(min_val) if min_val else None
                order_max = int(max_val) if max_val else None

                results = searcher.search_products(
                    keyword=query,
                    order_min=order_min,
                    order_max=order_max,
                    log_fn=self.log_to_console,
                )
            elif search_type == "customer":
                results = searcher.search_customers(query=query, log_fn=self.log_to_console)
            elif search_type == "order":
                try:
                    order_num = int(query.lstrip("#"))
                    results = searcher.search_order(order_number=order_num, log_fn=self.log_to_console)
                except ValueError:
                    self.log_to_console("Invalid order number. Please enter a numeric value.")
                    search_win.after(0, lambda: messagebox.showerror(
                        "Invalid Input", "Order number must be numeric.", parent=search_win
                    ))
                    return
            else:
                results = []

            search_win.after(0, lambda r=results: self._display_db_results(r, search_win))

        except Exception as exc:
            self.log_to_console(f"Search error: {exc}")
            search_win.after(0, lambda: messagebox.showerror(
                "Search Error", str(exc), parent=search_win
            ))

    def _display_db_results(self, results, search_win):
        """Display search results in the search window's treeview."""
        tree = getattr(search_win, '_result_tree', None)
        if tree:
            tree.delete(*tree.get_children())
            for r in results:
                details = f"{r.get('color', '')} / {r.get('size', '')}".strip(" /")
                tree.insert(
                    "",
                    "end",
                    values=(
                        r.get("order_number", ""),
                        r.get("product_name", ""),
                        r.get("customer_name", ""),
                        details,
                    ),
                )
            # Store results for export
            if hasattr(search_win, '_search_results'):
                search_win._search_results.clear()
                search_win._search_results.extend(results)

        # Update status label
        status_lbl = getattr(search_win, '_status_label', None)
        if status_lbl:
            status_lbl.config(text=f"Found {len(results)} result(s)")

        # Re-enable the search button
        search_btn = getattr(search_win, '_search_btn', None)
        if search_btn:
            search_btn.config(state=NORMAL)

    # ═══════════════════════════════════════════════════════════════════
    # NEW: Settings Window
    # ═══════════════════════════════════════════════════════════════════

    def open_settings(self):
        """Open the settings dialog."""
        SettingsWindow(
            self.root,
            on_sync_all=self.sync_all_thread,
            on_sync_latest=self.sync_latest_thread,
        )


def main():
    root = ttk_boot.Window(themename="cosmo")
    app = ShopifyExporterGUI(root)
    root.mainloop()

if __name__ == "__main__": main()
