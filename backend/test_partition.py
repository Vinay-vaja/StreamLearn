import os
import sys

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))
sys.path.append(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.services.transcript_service import get_transcript, get_video_title, partition_transcript

def main():
    # A known long video ID: "W6NZfCO5SIk" (approx 1 hour JavaScript tutorial)
    video_id = "W6NZfCO5SIk"
    print(f"Testing partitioning for video ID: {video_id}")
    
    try:
        title = get_video_title(video_id)
        print(f"Video Title: {title}")
        
        print("Fetching transcript (this may take a few seconds)...")
        transcript = get_transcript(video_id)
        print(f"Transcript fetched! Total segments: {len(transcript)}")
        
        if not transcript:
            print("No transcript segments returned.")
            return
            
        last_seg = transcript[-1]
        duration = last_seg.start + last_seg.duration
        print(f"Total computed duration: {duration:.2f} seconds ({duration / 60.0:.2f} mins)")
        
        print("\nPartitioning with 15-minute chunks:")
        chunks_15 = partition_transcript(transcript, duration, chunk_size_mins=15)
        for chunk in chunks_15:
            start_min = chunk.start_sec / 60.0
            end_min = chunk.end_sec / 60.0
            print(f"  Part {chunk.part}: {chunk.start_sec:.2f}s -> {chunk.end_sec:.2f}s ({start_min:.2f}m -> {end_min:.2f}m)")
            
        print("\nPartitioning with 30-minute chunks:")
        chunks_30 = partition_transcript(transcript, duration, chunk_size_mins=30)
        for chunk in chunks_30:
            start_min = chunk.start_sec / 60.0
            end_min = chunk.end_sec / 60.0
            print(f"  Part {chunk.part}: {chunk.start_sec:.2f}s -> {chunk.end_sec:.2f}s ({start_min:.2f}m -> {end_min:.2f}m)")
            
    except Exception as e:
        print(f"Error during partition testing: {str(e)}")

if __name__ == "__main__":
    main()
