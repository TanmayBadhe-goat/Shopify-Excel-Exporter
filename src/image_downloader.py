import requests
from pathlib import Path
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from .utils import logger

class ImageDownloader:
    def __init__(self, image_dir="images", max_workers=10):
        self.image_dir = Path(image_dir)
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers

    def download_image(self, url, file_id):
        """
        Download a single image and return its local path.
        """
        if not url:
            return None

        file_path = self.image_dir / f"product_{file_id}.png"
        
        # Cache check
        if file_path.exists():
            return file_path

        try:
            logger.info(f"Downloading image: {url} -> {file_path.name}")
            # Strict timeout to prevent hanging
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Save and resize
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            with Image.open(file_path) as img:
                img.thumbnail((200, 200), Image.LANCZOS)
                img.save(file_path)
            
            logger.info(f"Successfully processed image: {file_path.name}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to download image {url}: {e}")
            # Clean up partial file if it exists
            if file_path.exists():
                try: file_path.unlink()
                except: pass
            return None

    def download_images_parallel(self, image_tasks, log_fn=None):
        """
        Download multiple images in parallel.
        image_tasks: List of tuples (url, file_id)
        log_fn: Optional function to log progress to GUI
        Returns: Dict of {file_id: local_path}
        """
        results = {}
        total = len(image_tasks)
        completed = 0
        
        if log_fn:
            log_fn(f"Starting parallel download of {total} images...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_id = {
                executor.submit(self.download_image, url, fid): fid 
                for url, fid in image_tasks
            }
            
            for future in future_to_id:
                fid = future_to_id[future]
                try:
                    path = future.result()
                    results[fid] = path
                    completed += 1
                    if log_fn and completed % 5 == 0:
                        log_fn(f"Progress: {completed}/{total} images downloaded...")
                except Exception as e:
                    logger.error(f"Parallel download error for {fid}: {e}")
                    results[fid] = None
        
        if log_fn:
            log_fn(f"Completed downloading {completed}/{total} images.")
        return results
