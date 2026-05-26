import requests

with open("test.csv", "w", encoding="utf-8") as f:
    f.write("product_name\nLaptop Dell XPS 13\n")

with open("test.csv", "rb") as f:
    files = {"file": ("test.csv", f, "text/csv")}
    try:
        response = requests.post("http://localhost:8000/api/v1/valuate/batch", files=files)
        print("Status code:", response.status_code)
        print("Content:", response.text[:500])
    except Exception as e:
        print("Error:", e)
