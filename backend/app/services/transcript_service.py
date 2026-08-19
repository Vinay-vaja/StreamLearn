import re
import time
import logging
import requests
from typing import List
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

from app.models.schemas import TranscriptSegment, ChunkInfo
from app.core.config import settings

logger = logging.getLogger(__name__)

def extract_video_id(url: str) -> str:
    """
    Extracts the 11-character YouTube video ID from various YouTube URL formats.
    """
    pattern = r"(?:v=|\/embed\/|\/1\/|\/v\/|https:\/\/youtu\.be\/|\/shorts\/|\/live\/|^)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, url)
    if not match:
        raise ValueError("Invalid YouTube URL. Could not extract video ID.")
    return match.group(1)

def get_video_title(video_id: str) -> str:
    """
    Retrieves the video title using YouTube's public oEmbed API.
    """
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json().get("title", f"YouTube Video {video_id}")
    except Exception as e:
        logger.warning(f"Failed to fetch video title from oEmbed: {str(e)}")
    return f"YouTube Video {video_id}"

def fetch_youtube_transcript_api(video_id: str) -> List[TranscriptSegment]:
    """
    Fetches transcript using youtube-transcript-api with exponential backoff.
    """
    max_retries = 3
    delay = 1.0  # initial delay in seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting youtube-transcript-api for video {video_id} (Attempt {attempt+1}/{max_retries})")
            raw_transcript = YouTubeTranscriptApi.get_transcript(video_id)
            return [
                TranscriptSegment(
                    text=item["text"],
                    start=float(item["start"]),
                    duration=float(item["duration"])
                )
                for item in raw_transcript
            ]
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            # Permanent errors - raise immediately to avoid useless retries
            logger.info(f"Permanent transcript exception for video {video_id}: {type(e).__name__}")
            raise e
        except Exception as e:
            logger.warning(f"youtube-transcript-api attempt {attempt+1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise e
            time.sleep(delay)
            delay *= 2.0  # exponential backoff
            
    raise Exception("Exhausted retries for youtube-transcript-api")

def fetch_supadata_transcript(video_id: str) -> List[TranscriptSegment]:
    """
    Fetches transcript using Supadata API as a fallback.
    """
    if not settings.supadata_api_key:
        raise ValueError("Supadata API key is not configured, and youtube-transcript-api failed.")
        
    url = "https://api.supadata.ai/v1/youtube/transcript"
    headers = {
        "x-api-key": settings.supadata_api_key
    }
    params = {
        "videoId": video_id
    }
    
    logger.info(f"Calling Supadata transcript API fallback for video {video_id}")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        content = data.get("content", [])
        if not content:
            raise ValueError("Supadata transcript content is empty.")
            
        segments = []
        for item in content:
            # Convert milliseconds to seconds
            start_sec = float(item.get("offset", 0)) / 1000.0
            duration_sec = float(item.get("duration", 0)) / 1000.0
            segments.append(TranscriptSegment(
                text=item.get("text", ""),
                start=start_sec,
                duration=duration_sec
            ))
        return segments
    except Exception as e:
        logger.error(f"Supadata fallback failed: {str(e)}")
        raise e

def get_transcript(video_id: str) -> List[TranscriptSegment]:
    """
    Fetches transcript for a YouTube video.
    First tries youtube-transcript-api (with backoff), falls back to Supadata on failure.
    """
    try:
        return fetch_youtube_transcript_api(video_id)
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        logger.info(f"youtube-transcript-api reports transcripts disabled/not found. Falling back to Supadata...")
        return fetch_supadata_transcript(video_id)
    except Exception as e:
        logger.warning(f"youtube-transcript-api failed with generic exception. Falling back to Supadata...")
        return fetch_supadata_transcript(video_id)

def partition_transcript(
    transcript: List[TranscriptSegment],
    duration: float,
    chunk_size_mins: int = 30
) -> List[ChunkInfo]:
    """
    Partitions the video transcript into chunks of chunk_size_mins (default 30),
    snapping boundaries to the largest gap between segments within a ±3 min window.
    """
    if duration <= chunk_size_mins * 60:
        return [ChunkInfo(part=1, start_sec=0.0, end_sec=duration)]
        
    chunk_size_secs = chunk_size_mins * 60
    window_secs = 180.0  # ±3 minutes window
    
    # Calculate how many chunks we aim for
    num_chunks = int(duration // chunk_size_secs)
    if duration % chunk_size_secs > 0:
        num_chunks += 1
        
    boundaries = [0.0]
    
    for i in range(1, num_chunks):
        target = float(i * chunk_size_secs)
        window_start = target - window_secs
        window_end = target + window_secs
        
        # Find segments that start within the window
        candidates = []
        for idx in range(len(transcript) - 1):
            seg = transcript[idx]
            if window_start <= seg.start <= window_end:
                next_seg = transcript[idx + 1]
                gap = next_seg.start - (seg.start + seg.duration)
                candidates.append((seg.start + seg.duration, gap))
                
        if candidates:
            # Pick the candidate with the maximum gap
            best_boundary, max_gap = max(candidates, key=lambda x: x[1])
            
            # Meaningfully larger gap threshold: let's say 0.3 seconds
            if max_gap > 0.3:
                boundaries.append(best_boundary)
            else:
                boundaries.append(target)
        else:
            boundaries.append(target)
            
    boundaries.append(duration)
    
    # Remove duplicates, sort, and clean boundaries
    boundaries = sorted(list(set(boundaries)))
    
    # Build ChunkInfo list
    chunks = []
    for i in range(len(boundaries) - 1):
        chunks.append(ChunkInfo(
            part=i + 1,
            start_sec=boundaries[i],
            end_sec=boundaries[i + 1]
        ))
        
    return chunks


