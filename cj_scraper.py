import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
from typing import Dict, List
import os
import urllib.parse
import time

class CJScraper:
    def __init__(self):
        self.base_url = "https://cjdropshipping.com/detail.html?sku="  # Updated URL format
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        # Create images directory if it doesn't exist
        self.images_dir = "product_images"
        os.makedirs(self.images_dir, exist_ok=True)
        
    def download_image(self, image_url: str, sku: str, index: int) -> str:
        """
        Download an image and save it to the images directory
        Returns the local path to the saved image
        """
        try:
            # Create SKU-specific directory
            sku_dir = os.path.join(self.images_dir, sku)
            os.makedirs(sku_dir, exist_ok=True)
            
            # Get file extension from URL
            parsed_url = urllib.parse.urlparse(image_url)
            ext = os.path.splitext(parsed_url.path)[1]
            if not ext:
                ext = '.jpg'  # Default to jpg if no extension found
                
            # Create filename
            filename = f"{sku}_image_{index}{ext}"
            local_path = os.path.join(sku_dir, filename)
            
            # Download and save image
            response = requests.get(image_url, headers=self.headers)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
                
            print(f"Downloaded image {index + 1} for SKU {sku}")
            return local_path
            
        except Exception as e:
            print(f"Error downloading image {index + 1} for SKU {sku}: {str(e)}")
            return ""
        
    def get_product_info(self, sku: str) -> Dict:
        """
        Fetch product information using the SKU
        """
        try:
            url = f"{self.base_url}{sku}"
            print(f"Fetching from URL: {url}")
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract images first
            image_urls = self._get_images(soup)
            if not image_urls:
                print("No images found. Checking alternative image containers...")
                # Try alternative image containers
                image_urls = self._get_alternative_images(soup)
            
            local_image_paths = []
            
            if image_urls:
                # Download each image
                print(f"\nDownloading images for SKU {sku}...")
                for idx, img_url in enumerate(image_urls):
                    if not img_url.startswith('http'):
                        img_url = 'https:' + img_url if img_url.startswith('//') else 'https://' + img_url
                    local_path = self.download_image(img_url, sku, idx)
                    if local_path:
                        local_image_paths.append(local_path)
                    time.sleep(0.5)  # Small delay between downloads
            else:
                print("No images found for this product")
            
            # Extract product details
            title = self._get_title(soup)
            if not title:
                print("Warning: Could not find product title")
            
            description = self._get_description(soup)
            if not description:
                print("Warning: Could not find product description")
            
            product_data = {
                'sku': sku,
                'title': title,
                'description': description,
                'image_urls': '|'.join(image_urls),
                'local_image_paths': '|'.join(local_image_paths),
                'url': url
            }
            
            return product_data
            
        except requests.RequestException as e:
            print(f"Error fetching product {sku}: {str(e)}")
            return None
    
    def _get_title(self, soup: BeautifulSoup) -> str:
        """Extract product title"""
        # Try multiple possible title selectors
        selectors = [
            ('h1', {'class_': 'product-title'}),
            ('h1', {'class_': 'title'}),
            ('div', {'class_': 'product-name'}),
            ('div', {'class_': 'detail-title'})
        ]
        
        for tag, attrs in selectors:
            title_elem = soup.find(tag, attrs)
            if title_elem:
                return title_elem.text.strip()
        return ''
    
    def _get_description(self, soup: BeautifulSoup) -> str:
        """Extract product description"""
        # Try multiple possible description selectors
        selectors = [
            ('div', {'class_': 'product-description'}),
            ('div', {'class_': 'description'}),
            ('div', {'class_': 'detail-desc'}),
            ('div', {'id': 'description'})
        ]
        
        for tag, attrs in selectors:
            desc_elem = soup.find(tag, attrs)
            if desc_elem:
                return desc_elem.text.strip()
        return ''
    
    def _get_images(self, soup: BeautifulSoup) -> List[str]:
        """Extract product images"""
        images = []
        # Try multiple possible image containers
        containers = [
            ('div', {'class_': 'product-images'}),
            ('div', {'class_': 'detail-gallery'}),
            ('div', {'class_': 'product-gallery'})
        ]
        
        for tag, attrs in containers:
            img_container = soup.find(tag, attrs)
            if img_container:
                for img in img_container.find_all('img'):
                    if 'src' in img.attrs:
                        images.append(img['src'])
                    elif 'data-src' in img.attrs:
                        images.append(img['data-src'])
        return images
    
    def _get_alternative_images(self, soup: BeautifulSoup) -> List[str]:
        """Try alternative methods to find product images"""
        images = []
        # Look for any img tags with specific patterns in src or class
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if any(x in src.lower() for x in ['product', 'goods', 'item', 'detail']):
                images.append(src)
            # Check data-src attribute
            data_src = img.get('data-src', '')
            if data_src:
                images.append(data_src)
        return list(set(images))  # Remove duplicates

    def save_to_csv(self, product_data: Dict, filename: str = 'products.csv'):
        """
        Save product information to CSV file
        """
        if not product_data:
            return
        
        # Convert to DataFrame
        df = pd.DataFrame([product_data])
        
        # Check if file exists to determine if we need to write headers
        file_exists = os.path.isfile(filename)
        
        # Save to CSV
        df.to_csv(filename, mode='a' if file_exists else 'w',
                 header=not file_exists, index=False)
        
        print(f"Product information saved to {filename}")

def main():
    scraper = CJScraper()
    
    while True:
        sku = input("\nEnter product SKU (or 'quit' to exit): ").strip()
        
        if sku.lower() == 'quit':
            break
            
        if not sku:
            print("Please enter a valid SKU")
            continue
            
        print(f"\nFetching information for SKU: {sku}")
        product_data = scraper.get_product_info(sku)
        
        if product_data:
            scraper.save_to_csv(product_data)
            print(f"\nSuccessfully scraped product: {product_data['title']}")
            print(f"Images saved in: {os.path.join(scraper.images_dir, sku)}")
        else:
            print(f"\nFailed to fetch product information for SKU: {sku}")

if __name__ == "__main__":
    main()
