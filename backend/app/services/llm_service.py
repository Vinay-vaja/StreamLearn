import json
import asyncio
import logging
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from app.core.config import settings
from app.models.schemas import TranscriptSegment, SectionNotes

logger = logging.getLogger(__name__)

GEMINI_TEXT_MODEL = "gemini-3.1-flash-lite"

# Token budget guards — keeps each API call well within Gemini's limits
MAX_SEGMENT_CHARS = 8000   # transcript sample sent for topic segmentation
MAX_SECTION_CHARS = 5000   # transcript text per section for note generation
MAX_SUMMARY_CHARS = 10000  # compiled outline sent for the reduce/revision pass


# ---------------------------------------------------------------------------
# Client helper
# ---------------------------------------------------------------------------

def _get_text_client() -> genai.Client:
    if not settings.gemini_api_key_fortext:
        raise ValueError(
            "GEMINI_API_KEY_FORTEXT is not set in .env. "
            "Please add it to use note generation."
        )
    return genai.Client(api_key=settings.gemini_api_key_fortext)


def format_time(seconds: float) -> str:
    mins, secs = divmod(int(seconds), 60)
    return f"{mins:02d}:{secs:02d}"


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

def _is_retryable(exc: Exception) -> bool:
    """Retry only on transient 429 / 503 / connection errors."""
    msg = str(exc).lower()
    return any(k in msg for k in ("429", "503", "rate", "quota", "unavailable", "resource_exhausted"))


def _log_retry(retry_state):
    exc = retry_state.outcome.exception()
    logger.warning(
        f"Gemini API failed (attempt {retry_state.attempt_number}): "
        f"{type(exc).__name__}: {exc}"
    )


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    retry=retry_if_exception(_is_retryable),
    before_sleep=_log_retry,
)
async def _call_gemini(prompt: str, temperature: float = 0.2) -> str:
    """
    Core Gemini Flash call with JSON-mode output and exponential backoff.
    Only retries on rate-limit / server errors — not on bad-request errors.
    """
    client = _get_text_client()
    response = await client.aio.models.generate_content(
        model=GEMINI_TEXT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=temperature,
            max_output_tokens=2048,
        ),
    )
    return response.text


# ---------------------------------------------------------------------------
# Service 1: Segment transcript into logical topic sections
# ---------------------------------------------------------------------------

async def segment_transcript(
    transcript: List[TranscriptSegment],
    duration: float,
) -> List[Dict[str, Any]]:
    """
    Analyzes a transcript and returns logical topic sections with timestamps.
    Samples the transcript evenly to stay within token limits.
    """
    if not transcript:
        return [{"title": "Introduction", "start_sec": 0.0, "end_sec": duration}]

    # Build timestamped lines then sample evenly to stay within budget
    lines = [
        f"[{format_time(s.start)}] ({s.start:.1f}s): {s.text}"
        for s in transcript
    ]
    full_text = "\n".join(lines)

    if len(full_text) > MAX_SEGMENT_CHARS:
        step = max(1, len(lines) // (MAX_SEGMENT_CHARS // 80))
        sampled = lines[::step]
        transcript_text = "\n".join(sampled)[:MAX_SEGMENT_CHARS]
        logger.info(f"Transcript sampled: {len(lines)} → {len(sampled)} lines for segmentation.")
    else:
        transcript_text = full_text

    prompt = f"""You are an expert video content analyzer. Analyze this lecture transcript and split it into 3-8 logical topic sections based on clear subject-matter shifts.

Rules:
- Sections must be chronological and non-overlapping.
- first section start_sec = {transcript[0].start:.1f}
- last section end_sec = {transcript[-1].start + transcript[-1].duration:.1f}
- Title must be concise (5-8 words max) and describe the actual topic.

Return ONLY this JSON:
{{
  "sections": [
    {{"title": "Topic Title", "start_sec": 0.0, "end_sec": 120.0}},
    ...
  ]
}}

Transcript:
{transcript_text}
"""

    try:
        raw = await _call_gemini(prompt, temperature=0.1)
        result = json.loads(raw)
        sections = result.get("sections", [])
        if not sections:
            raise ValueError("Empty sections in response.")
        return sections
    except Exception as e:
        logger.error(f"segment_transcript failed: {e}. Using single-section fallback.")
        return [{
            "title": "Full Lecture",
            "start_sec": transcript[0].start,
            "end_sec": transcript[-1].start + transcript[-1].duration,
        }]


# ---------------------------------------------------------------------------
# Service 2: Generate detailed study notes for one section
# ---------------------------------------------------------------------------

async def generate_section_notes(section_text: str, start_sec: float) -> SectionNotes:
    """
    Generates comprehensive, exam-ready study notes for one transcript section
    using Gemini Flash with structured JSON output.
    """
    formatted_start = format_time(start_sec)

    if len(section_text) > MAX_SECTION_CHARS:
        section_text = section_text[:MAX_SECTION_CHARS] + " ..."
        logger.info(f"Section text truncated to {MAX_SECTION_CHARS} chars at {formatted_start}.")

    prompt = f"""You are a senior educator and technical writer creating premium, exam-ready study notes from a lecture transcript.

Section start time: {formatted_start} ({start_sec:.0f}s)

Generate notes that are comprehensive, precise, and suitable for a student preparing for an exam or job interview.

Requirements:
1. heading   — A sharp, descriptive title (5-10 words) capturing the exact concept taught.
2. explanation — A well-structured 3-5 paragraph explanation covering:
   • The core concept and its motivation / real-world importance
   • How it works (mechanism, formula, algorithm, or theory)
   • Intuition-building analogies or comparisons where helpful
   • Edge cases, limitations, or common pitfalls
3. key_points — 5-8 crisp, exam-ready bullet points a student must memorise.
4. examples — 2-4 concrete items: formulas, worked examples, code snippets, or real datasets mentioned.
5. timestamp — Exactly "{formatted_start}" — do not change this value.

Return ONLY this JSON (no markdown fences):
{{
  "heading": "...",
  "explanation": "...",
  "key_points": ["...", "..."],
  "examples": ["...", "..."],
  "timestamp": "{formatted_start}"
}}

Transcript section:
{section_text}
"""

    try:
        raw = await _call_gemini(prompt, temperature=0.3)
        data = json.loads(raw)

        examples = data.get("examples", [])
        if not isinstance(examples, list):
            examples = [examples] if examples else []

        return SectionNotes(
            heading=data.get("heading", "Section Notes"),
            explanation=data.get("explanation", ""),
            key_points=data.get("key_points", []),
            examples=examples,
            timestamp=data.get("timestamp", formatted_start),
        )
    except Exception as e:
        logger.error(f"generate_section_notes failed at {formatted_start}: {e}")
        return SectionNotes(
            heading=f"Notes — {formatted_start}",
            explanation="Notes could not be generated for this section due to an API error.",
            key_points=["API error — please retry."],
            examples=[],
            timestamp=formatted_start,
        )


# ---------------------------------------------------------------------------
# Service 2b: Generate a Mermaid diagram for one section
# ---------------------------------------------------------------------------

async def generate_section_mermaid(heading: str, explanation: str, key_points: List[str]) -> Optional[str]:
    """
    Generates a concise Mermaid diagram code block for a lecture section.
    Chooses between flowchart, sequence, or mindmap depending on content type.
    Returns raw Mermaid syntax (without the ```mermaid fence), or None on failure.
    """
    bullet_points = "\n".join(f"- {kp}" for kp in key_points[:6])
    short_explanation = explanation[:400].replace("\n", " ")

    prompt = f"""You are an expert technical educator who creates concise, accurate Mermaid diagrams to visualise lecture concepts.

Section heading: {heading}
Explanation summary: {short_explanation}
Key points:
{bullet_points}

Task: Produce a SINGLE, valid Mermaid diagram that best visualises the concept above.
Rules:
- Pick the most appropriate diagram type: flowchart TD (for processes / algorithms), mindmap (for concept maps), or sequenceDiagram (for interactions).
- Keep it concise — 6-14 nodes/steps maximum.
- All node labels must be short (2-5 words), wrapped in quotes if they contain spaces or special characters.
- ONLY return raw Mermaid syntax — do NOT include ```mermaid fences, no extra commentary, no JSON wrapper.
- The output MUST start with one of: `flowchart TD`, `mindmap`, or `sequenceDiagram`.

Return ONLY this JSON:
{{"mermaid": "<raw mermaid code here>"}}
"""

    try:
        raw = await _call_gemini(prompt, temperature=0.2)
        data = json.loads(raw)
        mermaid_code = data.get("mermaid", "").strip()
        if not mermaid_code:
            return None
        # Basic sanity check — must start with a known diagram type
        valid_starts = ("flowchart", "mindmap", "sequenceDiagram", "graph ")
        if not any(mermaid_code.startswith(s) for s in valid_starts):
            logger.warning(f"Unexpected Mermaid output for section '{heading}': {mermaid_code[:80]}")
            return None
        return mermaid_code
    except Exception as e:
        logger.error(f"generate_section_mermaid failed for '{heading}': {e}")
        return None


# ---------------------------------------------------------------------------
# Service 3: Reduce all sections into Quick Revision + Exam Questions
# ---------------------------------------------------------------------------

async def generate_summary_reduce(sections_notes: list) -> Dict[str, str]:
    """
    Final reduce pass: synthesises all section headings + key points into a
    cohesive Quick Revision summary and high-value exam/interview questions.
    """
    outline_parts = []
    for i, sec in enumerate(sections_notes, 1):
        bullets = "\n".join(f"  - {kp}" for kp in sec.key_points)
        outline_parts.append(f"Section {i}: {sec.heading}\nKey Points:\n{bullets}")

    outline = "\n\n".join(outline_parts)

    if len(outline) > MAX_SUMMARY_CHARS:
        outline = outline[:MAX_SUMMARY_CHARS] + "\n..."
        logger.info("Summary reduce outline truncated.")

    prompt = f"""You are a senior educator preparing students for exams and technical interviews.

Below is the complete structured outline of a lecture (headings + key points). Produce two high-value outputs:

1. quick_revision — A fluent, cohesive 200-300 word summary of the entire lecture that ties all concepts together. Written in clear prose. Good enough to revise from the night before an exam.

2. common_questions — 6-8 conceptual or applied exam / interview questions drawn directly from this lecture. Format each as:
   **Q1. Question text?**
   → Answer guideline (2-3 sentences, covering the key idea and a nuance).

Return ONLY this JSON:
{{
  "quick_revision": "...",
  "common_questions": "**Q1. ...?**\\n→ ...\\n\\n**Q2. ...?**\\n→ ..."
}}

Lecture outline:
{outline}
"""

    try:
        raw = await _call_gemini(prompt, temperature=0.4)
        data = json.loads(raw)
        return {
            "quick_revision": data.get("quick_revision", ""),
            "common_questions": data.get("common_questions", ""),
        }
    except Exception as e:
        logger.error(f"generate_summary_reduce failed: {e}")
        return {
            "quick_revision": "Summary unavailable.",
            "common_questions": "Questions unavailable.",
        }
