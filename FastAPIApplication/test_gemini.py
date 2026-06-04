import os, sys, json
from dotenv import load_dotenv
load_dotenv()

from routers.google_search_grounding import _get_client, GEMINI_MODEL
from google.genai import types

try:
    with open('test_sources.json', 'r', encoding='utf-8') as f:
        sources = json.load(f)
        
    client = _get_client()
    source_context = ''
    for idx, src in enumerate(sources[:5], start=1):
        source_context += f"[{idx}] {src.get('title')}\nURL: {src.get('url')}\n{src.get('content')}\n\n"
        
    prompt = f"Trích xuất GIÁ BÁN CHÍNH XÁC của sản phẩm 'iPhone 16' từ các nguồn dưới đây.\n\n{source_context}\n\nTrả về JSON:\n{{\"results\":[{{\"description\":\"...\",\"price\":\"...\",\"url\":\"...\"}}]}}"
    
    search_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[search_tool])
    
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=config)
    with open('test_raw_reply.txt', 'w', encoding='utf-8') as f:
        f.write(response.text)
    print("DONE")
except Exception as e:
    print("ERROR:", e)
