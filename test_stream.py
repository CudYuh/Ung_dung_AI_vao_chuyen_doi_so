import requests
print("Requesting stream...")
try:
    with open("test.csv", "rb") as f:
        files = {"file": ("test.csv", f, "text/csv")}
        response = requests.post("http://localhost:8000/api/v1/valuate/batch", files=files, stream=True)
        print("Status code:", response.status_code)
        for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
            if chunk:
                print("Chunk received:", repr(chunk))
except Exception as e:
    print("Error:", e)
