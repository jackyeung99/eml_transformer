import re
import requests


url = "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py"

params = {
    "pil": "AFDIND",
    "sdate": "2025-01-01",
    "edate": "2025-01-05",
    "limit": 2,
    "fmt": "text",
}

response = requests.get(
    url,
    params=params,
    timeout=30,
)

text = response.text

print("URL:", response.url)
print("Status:", response.status_code)


print(text)
