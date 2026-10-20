import requests
from bs4 import BeautifulSoup
import json
import csv
import os
import html as html_lib

# ── Setup ──────────────────────────────────────────────────────────────────
BASE_URL      = "https://itstore.com.bd"
API_URL       = f"{BASE_URL}/wp-json/wp/v2/product?per_page=10&_embed=true"
images_folder = "Class 1/itstore_images"
os.makedirs(images_folder, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ── Helper: scrape details from a product page ─────────────────────────────
def scrape_product_details(url):
    details = {
        "price"        : "N/A",
        "currency"     : "N/A",
        "availability" : "N/A",
        "category"     : "N/A",
        "brand"        : "N/A",
        "description"  : "N/A",
        "regular_price": "N/A",
        "sale_price"   : "N/A",
    }
    try:
        r    = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        # ── 1. Price from Open Graph meta tags ─────────────────────────────
        price_meta = soup.find("meta", {"property": "product:price:amount"})
        if price_meta:
            details["price"] = price_meta.get("content", "N/A")

        currency_meta = soup.find("meta", {"property": "product:price:currency"})
        if currency_meta:
            details["currency"] = currency_meta.get("content", "N/A")

        avail_meta = soup.find("meta", {"property": "product:availability"})
        if avail_meta:
            details["availability"] = avail_meta.get("content", "N/A")

        # ── 2. Rich data from JSON-LD schema ──────────────────────────────
        schema_tag = soup.find("script", {"type": "application/ld+json", "class": "rank-math-schema-pro"})
        if schema_tag:
            schema = json.loads(schema_tag.string)
            for node in schema.get("@graph", []):
                if node.get("@type") == "Product":
                    details["category"]    = node.get("category", "N/A")
                    details["description"] = node.get("description", "N/A")
                    offers = node.get("offers", {})
                    details["price"]       = offers.get("price", details["price"])
                    details["currency"]    = offers.get("priceCurrency", details["currency"])
                    details["availability"]= "In Stock" if "InStock" in offers.get("availability","") else offers.get("availability","N/A")
                    break

        # ── 3. Sale vs Regular price from twitter meta ─────────────────────
        twitter_price = soup.find("meta", {"name": "twitter:data1"})
        if twitter_price:
            price_text = twitter_price.get("content", "")
            details["sale_price"] = price_text.strip()

        # ── 4. Brand from product specs table ─────────────────────────────
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True).lower()
                    val = cells[1].get_text(strip=True)
                    if key == "brand":
                        details["brand"] = val
                        break

    except Exception as e:
        print(f"  Detail fetch error for {url}: {e}")
    return details


# ── Fetch product list from API ────────────────────────────────────────────
print("Fetching product list from WordPress API...")
response = requests.get(API_URL, headers=HEADERS, timeout=15)
products = response.json()
print(f"Found {len(products)} products. Fetching details...\n")

data = []

for i, product in enumerate(products, start=1):
    # Basic info from API
    title       = html_lib.unescape(product.get("title", {}).get("rendered", "N/A"))
    product_url = product.get("link", "N/A")
    date        = product.get("date", "N/A")[:10]

    # Image URL
    img_url      = "N/A"
    img_filename = "N/A"
    try:
        media   = product["_embedded"]["wp:featuredmedia"][0]
        img_url = media.get("source_url", "N/A")
        sizes   = media.get("media_details", {}).get("sizes", {})
        if "medium" in sizes:
            img_url = sizes["medium"]["source_url"]
    except (KeyError, IndexError, TypeError):
        pass

    # Download image
    if img_url != "N/A":
        try:
            img_filename = f"{images_folder}/product_{i}.jpg"
            img_data     = requests.get(img_url, headers=HEADERS, timeout=10).content
            with open(img_filename, "wb") as f:
                f.write(img_data)
        except Exception as e:
            print(f"  Image error: {e}")
            img_filename = "N/A"

    # Scrape product details page
    print(f"[{i}] Fetching details: {title[:60]}...")
    details = scrape_product_details(product_url)

    price        = f"{details['price']} {details['currency']}" if details['price'] != "N/A" else "N/A"
    availability = details["availability"]
    category     = details["category"]
    brand        = details["brand"]
    description  = details["description"]
    sale_price   = details["sale_price"]

    print(f"     Price       : {price}")
    print(f"     Availability: {availability}")
    print(f"     Brand       : {brand}")
    print(f"     Category    : {category}")
    print()

    data.append({
        "No"          : i,
        "Title"       : title,
        "Brand"       : brand,
        "Price (BDT)" : details["price"],
        "Sale Price"  : sale_price,
        "Availability": availability,
        "Category"    : category,
        "Date Added"  : date,
        "Description" : description,
        "Product URL" : product_url,
        "Image URL"   : img_url,
        "Image File"  : img_filename,
    })

# ── Save CSV ───────────────────────────────────────────────────────────────
csv_file = "Class 1/itstore_products.csv"
fieldnames = ["No","Title","Brand","Price (BDT)","Sale Price","Availability",
              "Category","Date Added","Description","Product URL","Image URL","Image File"]

with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)

print(f"Done! {len(data)} products saved to '{csv_file}'")
print(f"Images saved in '{images_folder}/'")
