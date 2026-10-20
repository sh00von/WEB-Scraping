import requests
from bs4 import BeautifulSoup
import csv
import os

BASE_URL = "https://books.toscrape.com/"

# Rating word to number map
RATING_MAP = {
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5
}

# Create folder to save images
images_folder = "Class 1/book_images"
os.makedirs(images_folder, exist_ok=True)

# Send GET request
response = requests.get(BASE_URL)
soup = BeautifulSoup(response.text, "html.parser")

# Find all book articles
books = soup.find_all("article", class_="product_pod")[:10]

data = []

for i, book in enumerate(books, start=1):
    # Title
    title = book.h3.a["title"]

    # Price
    price = book.find("p", class_="price_color").text.strip()

    # Rating
    rating_class = book.find("p", class_="star-rating")["class"][1]
    rating = RATING_MAP.get(rating_class, 0)

    # Availability
    availability = book.find("p", class_="instock availability").text.strip()

    # Image URL
    img_tag = book.find("img")
    img_src = img_tag["src"].replace("../../", "")
    img_url = BASE_URL + img_src

    # Download image
    img_filename = f"{images_folder}/book_{i}.jpg"
    img_data = requests.get(img_url).content
    with open(img_filename, "wb") as f:
        f.write(img_data)

    print(f"[{i}] {title} | {price} | Rating: {rating}/5 | Image saved: {img_filename}")

    data.append({
        "No": i,
        "Title": title,
        "Price": price,
        "Rating (out of 5)": rating,
        "Availability": availability,
        "Image URL": img_url,
        "Image File": img_filename
    })

# Save to CSV
csv_file = "Class 1/books.csv"
with open(csv_file, "w", newline="", encoding="utf-8") as f:
    fieldnames = ["No", "Title", "Price", "Rating (out of 5)", "Availability", "Image URL", "Image File"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)

print(f"\nDone! Data saved to '{csv_file}' | Images saved in '{images_folder}'")
