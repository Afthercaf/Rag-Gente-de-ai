import requests

api_key = "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"

response = requests.get(
    "https://api.groq.com/openai/v1/models",
    headers={
        "Authorization": f"Bearer {api_key}"
    }
)

print(response.status_code)
print(response.json())