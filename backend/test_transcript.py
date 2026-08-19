import os
import sys

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))
sys.path.append(os.path.dirname(__file__))

# Load env variables
from dotenv import load_dotenv
load_dotenv()

from app.services.transcript_service import extract_video_id, get_video_title, get_transcript

def main():
    # Test video URL (Rick Astley - Never Gonna Give You Up)
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"Testing URL parsing for: {url}")
    
    try:
        video_id = extract_video_id(url)
        print(f"Extracted Video ID: {video_id}")
        
        print("Fetching video title...")
        title = get_video_title(video_id)
        print(f"Video Title: {title}")
        
        print("Fetching transcript (youtube-transcript-api with Supadata fallback)...")
        transcript = get_transcript(video_id)
        print(f"Transcript fetched successfully! Total segments: {len(transcript)}")
        
        if transcript:
            print("First 3 segments:")
            for seg in transcript[:3]:
                print(f"  [{seg.start:.2f}s - {seg.start + seg.duration:.2f}s]: {seg.text}")
                
            last_seg = transcript[-1]
            total_dur = last_seg.start + last_seg.duration
            print(f"Computed Video Duration from transcript: {total_dur:.2f}s ({total_dur / 60.0:.2f} mins)")
            
    except Exception as e:
        print(f"Error during transcript testing: {str(e)}")

if __name__ == "__main__":
    main()
