import os
import sys
import asyncio

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))
sys.path.append(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.models.schemas import TranscriptSegment
from app.services.llm_service import segment_transcript, generate_section_notes, generate_summary_reduce

def get_dummy_transcript() -> list[TranscriptSegment]:
    return [
        TranscriptSegment(text="Welcome everyone. Today we are going to learn about JavaScript promises.", start=0.0, duration=5.0),
        TranscriptSegment(text="A promise is an object representing the eventual completion or failure of an asynchronous operation.", start=5.0, duration=7.0),
        TranscriptSegment(text="Think of it like ordering food. You get a receipt, which is a promise that you will get food eventually.", start=12.0, duration=8.0),
        TranscriptSegment(text="Next, let's look at how to create a promise. You use the new Promise constructor.", start=20.0, duration=6.0),
        TranscriptSegment(text="It takes an executor function with resolve and reject parameters.", start=26.0, duration=5.0),
        TranscriptSegment(text="For example: new Promise((resolve, reject) => { resolve('Success!'); });", start=31.0, duration=8.0),
        TranscriptSegment(text="Finally, let's learn how to consume promises using .then() and .catch().", start=40.0, duration=6.0),
        TranscriptSegment(text="The .then method handles success, while the .catch method handles errors.", start=46.0, duration=7.0),
        TranscriptSegment(text="For instance, myPromise.then(result => console.log(result)).catch(err => console.error(err));", start=53.0, duration=9.0),
        TranscriptSegment(text="That concludes our quick session on JavaScript promises. Thank you!", start=62.0, duration=5.0),
    ]

async def main():
    print("Testing LLM Service...")
    transcript = get_dummy_transcript()
    duration = 67.0
    
    print("\n1. Running segmentation logic...")
    sections = await segment_transcript(transcript, duration)
    print(f"Sections identified: {len(sections)}")
    for idx, sec in enumerate(sections):
        print(f"  Section {idx+1}: {sec.get('title')} ({sec.get('start_sec')}s - {sec.get('end_sec')}s)")
        
    print("\n2. Generating section notes in parallel (concurrency=3)...")
    # For each section, filter the transcript text belonging to it
    semaphore = asyncio.Semaphore(3)
    
    async def process_section(sec):
        async with semaphore:
            # Filter transcript segments in range
            start_sec = float(sec.get('start_sec', 0.0))
            end_sec = float(sec.get('end_sec', duration))
            
            sec_texts = [
                seg.text for seg in transcript 
                if start_sec <= seg.start <= end_sec
            ]
            section_text = " ".join(sec_texts)
            
            print(f"  Generating notes for: {sec.get('title')} ({len(section_text)} chars)...")
            notes = await generate_section_notes(section_text, start_sec)
            return notes

    # Run tasks concurrently
    tasks = [process_section(sec) for sec in sections]
    sections_notes = await asyncio.gather(*tasks)
    
    print(f"\nSuccessfully generated {len(sections_notes)} section notes!")
    for sec_notes in sections_notes:
        print(f"  Notes Title: {sec_notes.heading}")
        print(f"    Explanation: {sec_notes.explanation[:60]}...")
        print(f"    Key points count: {len(sec_notes.key_points)}")
        print(f"    Examples count: {len(sec_notes.examples)}")
        
    print("\n3. Running reduce summary pass...")
    summary_data = await generate_summary_reduce(sections_notes)
    print("Reduce summary complete!")
    print(f"  Quick Revision summary length: {len(summary_data['quick_revision'])} characters")
    print(f"  Interview questions count: {summary_data['common_questions'].count('**') // 2} (approx)")

if __name__ == "__main__":
    asyncio.run(main())
