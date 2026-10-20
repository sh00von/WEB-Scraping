# 🕷️ Web Scraping Course & Projects

Welcome to the **Web Scraping** repository! This repository contains practical implementations, scripts, datasets, and resources covering foundational to advanced web scraping techniques.

---

## 📚 Course Syllabus

<p align="center">
  <img src="Web Scraping 9-Class Syllabus (1)_page-0001.jpg" alt="Web Scraping 9-Class Syllabus" width="850"/>
</p>

---

## 📁 Repository Structure

```plaintext
WEB-Scraping/
├── Class 1/
│   ├── get_request.py          # Basic HTTP GET requests & response handling
│   ├── scrape_books.py         # Scraping Books to Scrape using BeautifulSoup
│   ├── books.csv               # Extracted book catalog data
│   ├── scrape_itstore.py       # Detail scraper extracting metadata & specs
│   ├── parallal.py             # High-speed parallel scraper with ThreadPool & random User-Agents
│   └── itstore_products.csv    # Full dataset (2,031 products scraped)
├── Web Scraping 9-Class Syllabus (1)_page-0001.jpg
└── README.md
```

---

## 🚀 Class 1: Fundamentals to Parallel Scraping

### Key Topics Covered:
1. **HTTP Requests & Inspecting APIs**:
   - Working with `requests` library.
   - Status codes, custom headers, and session management.
   - Bypassing browser overhead by inspecting and querying backend REST APIs (WordPress/WooCommerce endpoints).

2. **Parsing HTML & JSON**:
   - Extracting product details, prices, availability, and OpenGraph/JSON-LD metadata with `BeautifulSoup`.
   - Handling structured API responses.

3. **High-Speed Parallel Scraping**:
   - Multi-threading with `concurrent.futures.ThreadPoolExecutor`.
   - Dynamic user-agent rotation using `fake-useragent`.
   - Connection pooling and auto-retries via `HTTPAdapter`.
   - Scraped all **2,031 products** and downloaded their images in record time.

---

## 🛠️ Setup & Requirements

Install required dependencies:

```bash
pip install requests beautifulsoup4 fake-useragent urllib3
```

### Running the Scrapers:
```bash
# Basic request test
python "Class 1/get_request.py"

# Scrape Books to Scrape catalog
python "Class 1/scrape_books.py"

# Fast parallel scraper for IT Store
python "Class 1/parallal.py"
```
