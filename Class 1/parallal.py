
import csv
import html
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import local
from urllib.parse import urlparse

import requests
from fake_useragent import UserAgent
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://itstore.com.bd"
API_URL = f"{BASE_URL}/wp-json/wc/store/v1/products"

OUTPUT_DIR = "Class 1"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "itstore_images")
CSV_FILE = os.path.join(OUTPUT_DIR, "itstore_products.csv")

PER_PAGE = 100

# Adjust these according to server capacity.
API_WORKERS = 6
IMAGE_WORKERS = 12

TIMEOUT = (5, 15)
MAX_RETRIES = 2

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)


# ============================================================
# RANDOM USER-AGENT MODULE
# ============================================================

ua = UserAgent(
    browsers=["Chrome", "Firefox", "Edge", "Safari"],
    os=["Windows", "Linux", "Mac OS X"],
)

thread_local = local()


# ============================================================
# HTTP SESSION WITH CONNECTION POOLING AND RETRIES
# ============================================================

def make_session():
    session = requests.Session()

    session.headers.update({
        "User-Agent": ua.random,
        "Accept": "application/json, text/html, */*",
    })

    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=4,
        pool_maxsize=4,
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def get_session():
    if not hasattr(thread_local, "session"):
        thread_local.session = make_session()

    return thread_local.session


def get_json(url, params=None):
    response = get_session().get(
        url,
        params=params,
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    return response.json(), response.headers


# ============================================================
# TEXT AND PRODUCT HELPERS
# ============================================================

def clean_text(value):
    if value is None or value == "":
        return "N/A"

    if isinstance(value, dict):
        value = value.get("rendered", "")

    if isinstance(value, list):
        return ", ".join(clean_text(item) for item in value)

    value = html.unescape(str(value))
    value = re.sub(r"<[^>]*>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value or "N/A"


def get_categories(product):
    categories = product.get("categories") or []

    names = [
        clean_text(category.get("name"))
        for category in categories
        if isinstance(category, dict)
    ]

    return ", ".join(names) if names else "N/A"


def get_brand(product):
    # Brand data is not exposed by every Store API installation.
    brands = product.get("brands") or []

    if isinstance(brands, list):
        names = [
            clean_text(brand.get("name"))
            for brand in brands
            if isinstance(brand, dict)
        ]

        if names:
            return ", ".join(names)

    # Try product attributes if brand is represented there.
    for attribute in product.get("attributes") or []:
        if not isinstance(attribute, dict):
            continue

        name = str(attribute.get("name", "")).strip().lower()

        if name not in ("brand", "brands", "manufacturer"):
            continue

        terms = attribute.get("terms") or []

        if terms:
            return ", ".join(
                clean_text(term.get("name"))
                for term in terms
                if isinstance(term, dict)
            )

        if attribute.get("value"):
            return clean_text(attribute["value"])

    return "N/A"


def get_image_url(product):
    images = product.get("images") or []

    if not images:
        return "N/A"

    image = images[0]

    if not isinstance(image, dict):
        return "N/A"

    return image.get("thumbnail") or image.get("src") or "N/A"


def get_price(prices, key):
    raw = prices.get(key)

    if raw in (None, ""):
        return "N/A"

    try:
        decimals = int(prices.get("currency_minor_unit", 2))
        amount = int(raw) / (10 ** decimals)

        return f"{amount:.{decimals}f}"

    except (ValueError, TypeError):
        return str(raw)


# ============================================================
# PAGINATED PRODUCT API
# ============================================================

def fetch_page(page):
    products, headers = get_json(
        API_URL,
        params={
            "page": page,
            "per_page": PER_PAGE,
        },
    )

    if not isinstance(products, list):
        raise ValueError(f"Unexpected response on page {page}")

    return page, products, headers


def fetch_all_products():
    print("=" * 60)
    print("FETCHING PRODUCTS")
    print("=" * 60)

    _, first_page, headers = fetch_page(1)

    total_products = int(headers.get("X-WP-Total", 0) or 0)
    total_pages = int(headers.get("X-WP-TotalPages", 0) or 0)

    if not total_pages and total_products:
        total_pages = (
            total_products + PER_PAGE - 1
        ) // PER_PAGE

    products = list(first_page)
    failed_pages = []

    if total_pages:
        pages = range(2, total_pages + 1)

        print(f"Products reported by API: {total_products}")
        print(f"Pages to fetch: {total_pages}")

        with ThreadPoolExecutor(max_workers=API_WORKERS) as pool:
            futures = {
                pool.submit(fetch_page, page): page
                for page in pages
            }

            for future in as_completed(futures):
                page = futures[future]

                try:
                    _, batch, _ = future.result()
                    products.extend(batch)

                except Exception as exc:
                    failed_pages.append(page)
                    print(f"Page {page} failed: {exc}")

        # Retry failed pages once more.
        for page in failed_pages[:]:
            try:
                _, batch, _ = fetch_page(page)
                products.extend(batch)
                failed_pages.remove(page)

            except Exception as exc:
                print(f"Page {page} retry failed: {exc}")

    else:
        # Fallback if pagination headers are unavailable.
        print("Pagination headers missing; fetching sequentially.")

        page = 2

        while True:
            try:
                _, batch, _ = fetch_page(page)

                if not batch:
                    break

                products.extend(batch)

                if len(batch) < PER_PAGE:
                    break

                page += 1

            except Exception as exc:
                print(f"Stopped at page {page}: {exc}")
                break

    # Deduplicate products by their WordPress product ID.
    unique_products = {}

    for product in products:
        product_id = product.get("id")

        if product_id is not None:
            unique_products[product_id] = product

    result = list(unique_products.values())

    print(f"Unique products retrieved: {len(result)}")

    if failed_pages:
        print(f"WARNING: Failed pages remain: {failed_pages}")

    if total_products and len(result) != total_products:
        print(
            f"WARNING: Expected {total_products}, "
            f"retrieved {len(result)}."
        )

    return result


# ============================================================
# PARALLEL IMAGE DOWNLOADS
# ============================================================

def download_image(task):
    index, product_id, image_url = task

    if not image_url or image_url == "N/A":
        return product_id, "N/A"

    filepath = None

    try:
        parsed = urlparse(image_url)

        if parsed.scheme not in ("http", "https"):
            return product_id, "N/A"

        extension = os.path.splitext(parsed.path)[1].lower()

        if extension not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            extension = ".jpg"

        filename = f"product_{index}_{product_id}{extension}"
        filepath = os.path.join(IMAGES_DIR, filename)

        response = get_session().get(
            image_url,
            timeout=TIMEOUT,
            stream=True,
        )

        try:
            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if not content_type.startswith("image/"):
                return product_id, "N/A"

            # Write to a temporary file to avoid incomplete images.
            temp_path = filepath + ".part"

            try:
                with open(temp_path, "wb") as file:
                    for chunk in response.iter_content(
                        chunk_size=64 * 1024
                    ):
                        if chunk:
                            file.write(chunk)

                os.replace(temp_path, filepath)

            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        finally:
            response.close()

        return product_id, filepath

    except Exception as exc:
        print(f"Image failed for product {product_id}: {exc}")
        return product_id, "N/A"


def download_all_images(products):
    print("\n" + "=" * 60)
    print("DOWNLOADING IMAGES")
    print("=" * 60)

    tasks = []

    for index, product in enumerate(products, start=1):
        tasks.append((
            index,
            product.get("id", index),
            get_image_url(product),
        ))

    image_paths = {}
    completed = 0

    with ThreadPoolExecutor(max_workers=IMAGE_WORKERS) as pool:
        futures = [
            pool.submit(download_image, task)
            for task in tasks
        ]

        for future in as_completed(futures):
            try:
                product_id, filepath = future.result()
                image_paths[product_id] = filepath

            except Exception as exc:
                print(f"Image worker error: {exc}")

            completed += 1

            if completed % 100 == 0 or completed == len(futures):
                print(f"Images processed: {completed}/{len(futures)}")

    return image_paths


# ============================================================
# CSV EXPORT
# ============================================================

FIELDNAMES = [
    "No",
    "Product ID",
    "Title",
    "Brand",
    "Price (BDT)",
    "Regular Price",
    "Sale Price",
    "Currency",
    "Availability",
    "Category",
    "Date Added",
    "Description",
    "Product URL",
    "Image URL",
    "Image File",
]


def build_row(index, product, image_paths):
    product_id = product.get("id", index)
    prices = product.get("prices") or {}

    current_price = get_price(prices, "price")
    regular_price = get_price(prices, "regular_price")
    on_sale = product.get("on_sale", False)

    if product.get("is_in_stock") is True:
        availability = "In Stock"
    elif product.get("is_in_stock") is False:
        availability = "Out of Stock"
    else:
        availability = "N/A"

    currency = prices.get("currency_code", "BDT")

    return {
        "No": index,
        "Product ID": product_id,
        "Title": clean_text(product.get("name")),
        "Brand": get_brand(product),
        "Price (BDT)": current_price,
        "Regular Price": regular_price,
        "Sale Price": current_price if on_sale else "N/A",
        "Currency": currency,
        "Availability": availability,
        "Category": get_categories(product),
        "Date Added": str(
            product.get("date_created", "N/A")
        )[:10],
        "Description": clean_text(
            product.get("description")
            or product.get("short_description")
        ),
        "Product URL": product.get("permalink", "N/A"),
        "Image URL": get_image_url(product),
        "Image File": image_paths.get(product_id, "N/A"),
    }


def save_csv(products, image_paths):
    print("\n" + "=" * 60)
    print("SAVING CSV")
    print("=" * 60)

    with open(
        CSV_FILE,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES,
        )

        writer.writeheader()

        for index, product in enumerate(products, start=1):
            writer.writerow(
                build_row(index, product, image_paths)
            )

    print(f"CSV saved: {CSV_FILE}")


# ============================================================
# MAIN
# ============================================================

def main():
    start_time = time.perf_counter()

    try:
        products = fetch_all_products()

        if not products:
            print("No products retrieved. CSV was not created.")
            return

        image_paths = download_all_images(products)

        save_csv(products, image_paths)

        elapsed = time.perf_counter() - start_time

        print("\n" + "=" * 60)
        print("SCRAPING COMPLETE")
        print("=" * 60)
        print(f"Products: {len(products)}")
        print(f"CSV file: {CSV_FILE}")
        print(f"Images folder: {IMAGES_DIR}")
        print(f"Elapsed time: {elapsed:.2f} seconds")

    except KeyboardInterrupt:
        print("\nStopped by user.")

    except Exception as exc:
        print(f"\nScraper failed: {exc}")
        raise

    finally:
        # Close sessions created by the main thread.
        session = getattr(thread_local, "session", None)

        if session:
            session.close()


if __name__ == "__main__":
    main()
