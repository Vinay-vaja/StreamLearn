import os
import requests
import sys

BASE_URL = "http://127.0.0.1:8000/api/notes"

def test_analyze():
    print("\n--- 1. Testing /analyze endpoint ---")
    url = "https://www.youtube.com/watch?v=W6NZfCO5SIk"  # JS Promises (technical tutorial)
    payload = {"url": url, "chunk_size_mins": 30}
    try:
      response = requests.post(f"{BASE_URL}/analyze", json=payload)
      print(f"Status Code: {response.status_code}")
      data = response.json()
      print(f"Title: {data.get('title')}")
      print(f"Duration: {data.get('duration')}s")
      print(f"Is Long: {data.get('is_long')}")
      print(f"Chunks: {data.get('chunks')}")
      return data
    except Exception as e:
      print(f"Failed: {str(e)}")
      return None

def test_generate(video_id):
    print("\n--- 2. Testing /generate (single-shot) endpoint ---")
    payload = {"video_id": video_id}
    try:
      response = requests.post(f"{BASE_URL}/generate", json=payload)
      print(f"Status Code: {response.status_code}")
      data = response.json()
      markdown = data.get("markdown", "")
      print(f"Markdown note length: {len(markdown)} chars")
      print(f"Sections Count: {len(data.get('sections', []))}")
      print("Markdown snippet:")
      print("\n".join(markdown.split("\n")[:10]))
      return data
    except Exception as e:
      print(f"Failed: {str(e)}")
      return None

def test_generate_chunk(video_id):
    print("\n--- 3. Testing /generate-chunk (chunked) endpoint ---")
    # Simulate first 10 minutes (600s)
    payload = {
      "video_id": video_id,
      "start_sec": 0.0,
      "end_sec": 120.0
    }
    try:
      response = requests.post(f"{BASE_URL}/generate-chunk", json=payload)
      print(f"Status Code: {response.status_code}")
      data = response.json()
      markdown = data.get("markdown", "")
      print(f"Chunk Markdown note length: {len(markdown)} chars")
      print(f"Sections Count: {len(data.get('sections', []))}")
      return data
    except Exception as e:
      print(f"Failed: {str(e)}")
      return None

def test_reduce(sections):
    print("\n--- 4. Testing /reduce (summary pass) endpoint ---")
    payload = {"sections": sections}
    try:
      response = requests.post(f"{BASE_URL}/reduce", json=payload)
      print(f"Status Code: {response.status_code}")
      data = response.json()
      print(f"Quick Revision length: {len(data.get('quick_revision', ''))}")
      print(f"Common Questions length: {len(data.get('common_questions', ''))}")
      return data
    except Exception as e:
      print(f"Failed: {str(e)}")
      return None

def test_export_pdf(markdown_text):
    print("\n--- 5. Testing /export-pdf endpoint ---")
    payload = {"markdown": markdown_text}
    try:
      response = requests.post(f"{BASE_URL}/export-pdf", json=payload)
      print(f"Status Code: {response.status_code}")
      print(f"Content Type: {response.headers.get('content-type')}")
      # Save small sample
      if response.status_code == 200:
        pdf_path = os.path.join(os.path.dirname(__file__), "test_output.pdf")
        with open(pdf_path, "wb") as f:
          f.write(response.content)
        print(f"Successfully saved PDF to: {pdf_path}")
      return response.status_code == 200
    except Exception as e:
      print(f"Failed: {str(e)}")
      return False

if __name__ == "__main__":
    print("Starting API Integration Tests...")
    analyze_data = test_analyze()
    if analyze_data:
      video_id = analyze_data.get("video_id")
      
      # Test Single Shot Generation
      gen_data = test_generate(video_id)
      
      # Test Chunked Generation
      chunk_data = test_generate_chunk(video_id)
      
      # Test Reduce Pass
      if gen_data and gen_data.get("sections"):
        test_reduce(gen_data.get("sections"))
        
      # Test PDF Export
      if gen_data and gen_data.get("markdown"):
        test_export_pdf(gen_data.get("markdown"))
