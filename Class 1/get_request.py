import requests

url = "https://books.toscrape.com/"

response = requests.get(url)

print(f"Status Code: {response.status_code}")
