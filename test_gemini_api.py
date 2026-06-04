"""Test gemini-2.5-flash with Google Search Grounding."""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(dotenv_path=Path("FastAPIApplication/.env"), override=True)

from google import genai
from google.genai import types

key = os.environ.get("GOOGLE_API_KEY", "")
client = genai.Client(api_key=key)

print("=== Test: gemini-2.5-flash + Google Search Grounding ===")
try:
    search_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[search_tool])
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Gia iPhone 16 tai Viet Nam hien nay? Tra loi ngan gon.",
        config=config,
    )
    text = response.text or "No text"
    print(f"Response: {text[:500]}")

    # Check grounding
    candidate = response.candidates[0]
    metadata = getattr(candidate, "grounding_metadata", None)
    if metadata:
        chunks = getattr(metadata, "grounding_chunks", None) or []
        print(f"\nGrounding chunks: {len(chunks)}")
        for c in chunks[:5]:
            web = getattr(c, "web", None)
            if web:
                title = getattr(web, "title", "")
                uri = getattr(web, "uri", "")
                print(f"  - {title} | {uri}")
    else:
        print("No grounding metadata")

    print("\nSUCCESS!")
except Exception as e:
    print(f"ERROR: {str(e)[:500]}")
