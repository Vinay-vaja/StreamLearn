import asyncio
import base64
import logging
from typing import Optional

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

IMAGEN_MODEL = "imagen-4.0-generate-001"


def _sync_generate_image(prompt: str) -> Optional[str]:
    """
    Synchronous Imagen 3 call — wrapped in run_in_executor for async use.
    Returns base64-encoded JPEG string, or None on failure.
    """
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY not set — skipping image generation.")
        return None

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="16:9",
            ),
        )
        if response.generated_images:
            raw = response.generated_images[0].image.image_bytes
            return base64.b64encode(raw).decode("utf-8")
    except Exception as e:
        logger.error(f"Imagen generation failed: {type(e).__name__}: {e}")
    return None


async def generate_section_image(heading: str, explanation: str) -> Optional[str]:
    """
    Generates a clean educational diagram / illustration for a note section.
    Runs Imagen 3 in a thread-pool so it doesn't block the async event loop.
    Returns base64-encoded JPEG string, or None on failure.
    """
    # Build a focused prompt for academic diagrams
    short_context = explanation[:250].replace("\n", " ")
    prompt = (
        f"Clean educational diagram illustrating the concept: '{heading}'. "
        f"Context: {short_context}. "
        "Style: minimalist academic illustration, white background, labeled arrows, "
        "geometric shapes, no photographs, no dense text. "
        "Suitable for a machine learning or data science textbook."
    )

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_generate_image, prompt)
