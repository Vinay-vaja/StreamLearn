import asyncio
import io
import logging
import markdown
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from xhtml2pdf import pisa
from typing import List

from app.models.schemas import (
    VideoAnalyzeRequest,
    VideoAnalyzeResponse,
    GenerateNotesRequest,
    GenerateNotesChunkRequest,
    GenerateNotesResponse,
    ReduceNotesRequest,
    ReduceNotesResponse,
    ExportPDFRequest,
    SectionNotes,
    SectionSummary,
)
from app.services.transcript_service import (
    extract_video_id,
    get_video_title,
    get_transcript,
    partition_transcript,
)
from app.services.llm_service import (
    segment_transcript,
    generate_section_notes,
    generate_section_mermaid,
    generate_summary_reduce,
)

logger = logging.getLogger(__name__)

# In-memory progress tracking
progress_store = {}

router = APIRouter(prefix="/api/notes", tags=["notes"])

@router.get("/progress/{task_key}")
async def get_progress(task_key: str):
    """
    Returns the current real progress status of note generation.
    """
    return {
        "task_key": task_key,
        "status": progress_store.get(task_key, "Pending")
    }


# --- Markdown Assembly Helpers ---

def _embed_mermaid(sec: SectionNotes) -> str:
    """Returns a mermaid fenced code block if diagram code is present."""
    if sec.mermaid_diagram:
        return f"\n```mermaid\n{sec.mermaid_diagram}\n```\n"
    return ""


def assemble_markdown_chunk(sections: List[SectionNotes]) -> str:
    """
    Assembles a list of SectionNotes into a markdown chunk snippet.
    """
    lines = []
    for sec in sections:
        lines.append(f"### {sec.heading} `[{sec.timestamp}]`")
        lines.append("")
        diagram = _embed_mermaid(sec)
        if diagram:
            lines.append(diagram)
        lines.append(sec.explanation)
        lines.append("")

        if sec.key_points:
            lines.append("**Key Takeaways:**")
            for kp in sec.key_points:
                lines.append(f"- {kp}")
            lines.append("")

        if sec.examples:
            lines.append("**Examples / Snippets:**")
            for ex in sec.examples:
                lines.append(f"- {ex}")
            lines.append("")

        lines.append("---")
        lines.append("")
    return "\n".join(lines)

def assemble_full_markdown(
    title: str,
    sections: List[SectionNotes],
    quick_revision: str = "",
    common_questions: str = ""
) -> str:
    """
    Assembles the final, complete study notes Markdown document.
    """
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    
    # Table of Contents
    lines.append("## Table of Contents")
    for sec in sections:
        # Generate simple link anchor
        anchor = sec.heading.lower().replace(" ", "-").replace("?", "").replace("!", "").replace(":", "")
        lines.append(f"- [{sec.heading} (`{sec.timestamp}`)](#{anchor})")
    
    if quick_revision:
        lines.append("- [Quick Revision Summary](#quick-revision-summary)")
    if common_questions:
        lines.append("- [Common Interview/Exam Questions](#common-interview-questions)")
        
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Render sections
    for sec in sections:
        anchor = sec.heading.lower().replace(" ", "-").replace("?", "").replace("!", "").replace(":", "")
        lines.append(f"### <a name=\"{anchor}\"></a>{sec.heading} `[{sec.timestamp}]`")
        lines.append("")
        diagram = _embed_mermaid(sec)
        if diagram:
            lines.append(diagram)
        lines.append(sec.explanation)
        lines.append("")

        if sec.key_points:
            lines.append("**Key Takeaways:**")
            for kp in sec.key_points:
                lines.append(f"- {kp}")
            lines.append("")

        if sec.examples:
            lines.append("**Examples / Practice:**")
            for ex in sec.examples:
                lines.append(f"- {ex}")
            lines.append("")

        lines.append("---")
        lines.append("")
        
    # Quick Revision
    if quick_revision:
        lines.append("### <a name=\"quick-revision-summary\"></a>Quick Revision Summary")
        lines.append("")
        lines.append(quick_revision)
        lines.append("")
        lines.append("---")
        lines.append("")
        
    # Common Questions
    if common_questions:
        lines.append("### <a name=\"common-interview-questions\"></a>Common Interview/Exam Questions")
        lines.append("")
        lines.append(common_questions)
        lines.append("")
        
    return "\n".join(lines)

# --- Endpoint Handlers ---

@router.post("/analyze", response_model=VideoAnalyzeResponse)
async def analyze_video(request: VideoAnalyzeRequest):
    """
    Submits a YouTube URL to extract video details (ID, title, duration) and chunk partitioning metadata.
    """
    try:
        video_id = extract_video_id(request.url)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        
    try:
        title = get_video_title(video_id)
        transcript = get_transcript(video_id)
        
        if not transcript:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No transcript found for this video.")
            
        last_seg = transcript[-1]
        duration = last_seg.start + last_seg.duration
        
        is_long = duration > 1800.0  # > 30 minutes
        
        # Calculate chunks (15 / 30 / 45 min choices)
        chunk_size_mins = request.chunk_size_mins or 30
        chunks = partition_transcript(transcript, duration, chunk_size_mins)
        
        return VideoAnalyzeResponse(
            video_id=video_id,
            duration=duration,
            title=title,
            chunks=chunks,
            is_long=is_long
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during video analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch video details or transcript: {str(e)}"
        )

@router.post("/generate", response_model=GenerateNotesResponse)
async def generate_notes(request: GenerateNotesRequest):
    """
    Generates notes for an entire short video (<= 30 mins) in one pass.
    Optionally generates an Imagen 3 educational diagram per section.
    """
    task_key = request.video_id
    try:
        progress_store[task_key] = "Extracting transcript"
        title = get_video_title(request.video_id)
        transcript = get_transcript(request.video_id)

        if not transcript:
            progress_store[task_key] = "Failed"
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No transcript found.")

        last_seg = transcript[-1]
        duration = last_seg.start + last_seg.duration

        # Segment using LLM
        progress_store[task_key] = "Segmenting"
        sections = await segment_transcript(transcript, duration)

        # Generate notes in parallel (concurrency capped to 2)
        progress_store[task_key] = "Generating notes"
        semaphore = asyncio.Semaphore(2)

        async def process_section(sec):
            async with semaphore:
                start_sec = float(sec.get('start_sec', 0.0))
                end_sec = float(sec.get('end_sec', duration))
                sec_texts = [
                    seg.text for seg in transcript
                    if start_sec <= seg.start <= end_sec
                ]
                section_text = " ".join(sec_texts)
                notes = await generate_section_notes(section_text, start_sec)
                if request.include_diagrams:
                    progress_store[task_key] = f"Generating diagram: {notes.heading[:30]}"
                    mermaid_code = await generate_section_mermaid(
                        notes.heading, notes.explanation, notes.key_points
                    )
                    notes = notes.model_copy(update={"mermaid_diagram": mermaid_code})
                return notes
                
        tasks = [process_section(sec) for sec in sections]
        sections_notes = await asyncio.gather(*tasks)
        
        # Run reduce pass for revision/interview questions
        reduce_data = await generate_summary_reduce(sections_notes)
        
        # Assemble final Markdown
        full_markdown = assemble_full_markdown(
            title=title,
            sections=sections_notes,
            quick_revision=reduce_data["quick_revision"],
            common_questions=reduce_data["common_questions"]
        )
        
        # Populate SectionSummary list
        section_summaries = [
            SectionSummary(heading=s.heading, key_points=s.key_points)
            for s in sections_notes
        ]
        
        progress_store[task_key] = "Done"
        return GenerateNotesResponse(markdown=full_markdown, sections=section_summaries)
    except HTTPException:
        progress_store[task_key] = "Failed"
        raise
    except Exception as e:
        progress_store[task_key] = "Failed"
        logger.error(f"Error generating notes: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/generate-chunk", response_model=GenerateNotesResponse)
async def generate_notes_chunk(request: GenerateNotesChunkRequest):
    """
    Generates notes for a specific chunk of a long video.
    Optionally generates an Imagen 3 educational diagram per section.
    """
    task_key = f"{request.video_id}_{int(request.start_sec)}_{int(request.end_sec)}"
    try:
        progress_store[task_key] = "Extracting transcript"
        transcript = get_transcript(request.video_id)
        if not transcript:
            progress_store[task_key] = "Failed"
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No transcript found.")

        chunk_transcript = [
            seg for seg in transcript
            if request.start_sec <= seg.start <= request.end_sec
        ]

        if not chunk_transcript:
            progress_store[task_key] = "Failed"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No transcript segments in range {request.start_sec}-{request.end_sec}s."
            )

        chunk_duration = request.end_sec - request.start_sec

        progress_store[task_key] = "Segmenting"
        sections = await segment_transcript(chunk_transcript, chunk_duration)

        # Make timestamps absolute relative to the video timeline
        for sec in sections:
            sec_start = float(sec.get('start_sec', 0.0))
            if sec_start < request.start_sec:
                sec['start_sec'] = sec_start + request.start_sec
                sec['end_sec'] = float(sec.get('end_sec', 0.0)) + request.start_sec

        progress_store[task_key] = "Generating notes"
        semaphore = asyncio.Semaphore(2)

        async def process_section(sec):
            async with semaphore:
                start_sec = float(sec.get('start_sec', request.start_sec))
                end_sec = float(sec.get('end_sec', request.end_sec))
                sec_texts = [
                    seg.text for seg in chunk_transcript
                    if start_sec <= seg.start <= end_sec
                ]
                section_text = " ".join(sec_texts)
                notes = await generate_section_notes(section_text, start_sec)
                if request.include_diagrams:
                    progress_store[task_key] = f"Generating diagram: {notes.heading[:30]}"
                    mermaid_code = await generate_section_mermaid(
                        notes.heading, notes.explanation, notes.key_points
                    )
                    notes = notes.model_copy(update={"mermaid_diagram": mermaid_code})
                return notes
                
        tasks = [process_section(sec) for sec in sections]
        sections_notes = await asyncio.gather(*tasks)
        
        # Assemble chunk markdown
        chunk_markdown = assemble_markdown_chunk(sections_notes)
        
        # Populate SectionSummary list
        section_summaries = [
            SectionSummary(heading=s.heading, key_points=s.key_points)
            for s in sections_notes
        ]
        
        progress_store[task_key] = "Done"
        return GenerateNotesResponse(markdown=chunk_markdown, sections=section_summaries)
    except HTTPException:
        progress_store[task_key] = "Failed"
        raise
    except Exception as e:
        progress_store[task_key] = "Failed"
        logger.error(f"Error generating chunk notes: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/reduce", response_model=ReduceNotesResponse)
async def reduce_notes(request: ReduceNotesRequest):
    """
    Produces final 'Quick Revision' and 'Common Questions' sections from compiled notes.
    """
    try:
        # Adapt SectionSummary list to generate_summary_reduce (which acts on head + key points)
        # We can construct temporary SectionNotes/mimic structures
        class MockSection:
            def __init__(self, heading, key_points):
                self.heading = heading
                self.key_points = key_points
                
        mock_sections = [MockSection(s.heading, s.key_points) for s in request.sections]
        
        reduce_data = await generate_summary_reduce(mock_sections)
        
        quick_revision = reduce_data["quick_revision"]
        common_questions = reduce_data["common_questions"]
        
        markdown_output = f"## Quick Revision Summary\n\n{quick_revision}\n\n---\n\n## Common Interview/Exam Questions\n\n{common_questions}"
        
        return ReduceNotesResponse(
            quick_revision=quick_revision,
            common_questions=common_questions,
            markdown=markdown_output
        )
    except Exception as e:
        logger.error(f"Error during note reduction: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/export-pdf")
async def export_pdf(request: ExportPDFRequest):
    """
    Exports markdown content into a PDF file stream.
    """
    try:
        # Convert Markdown to HTML
        html_content = markdown.markdown(request.markdown)
        
        # Styling layout for a premium-feeling PDF
        styled_html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: a4 portrait;
                    margin: 2cm;
                }}
                body {{
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    color: #2D3748;
                    line-height: 1.6;
                    font-size: 10pt;
                }}
                h1 {{
                    font-size: 22pt;
                    color: #1A365D;
                    border-bottom: 2px solid #3182CE;
                    padding-bottom: 8px;
                    margin-top: 0;
                    margin-bottom: 20px;
                }}
                h2 {{
                    font-size: 15pt;
                    color: #2B6CB0;
                    margin-top: 25px;
                    margin-bottom: 12px;
                    border-bottom: 1px solid #E2E8F0;
                    padding-bottom: 4px;
                }}
                h3 {{
                    font-size: 12pt;
                    color: #2D3748;
                    margin-top: 18px;
                    margin-bottom: 8px;
                }}
                p {{
                    margin-bottom: 12px;
                    text-align: justify;
                }}
                ul, ol {{
                    margin-bottom: 12px;
                    padding-left: 20px;
                }}
                li {{
                    margin-bottom: 4px;
                }}
                hr {{
                    border: 0;
                    border-top: 1px solid #E2E8F0;
                    margin: 20px 0;
                }}
                code {{
                    font-family: Courier, monospace;
                    background-color: #F7FAFC;
                    padding: 2px 4px;
                    font-size: 8.5pt;
                    border: 1px solid #EDF2F7;
                }}
                pre {{
                    font-family: Courier, monospace;
                    background-color: #F7FAFC;
                    padding: 8px;
                    font-size: 8.5pt;
                    border: 1px solid #EDF2F7;
                    margin-bottom: 12px;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(styled_html, dest=pdf_buffer)
        
        if pisa_status.err:
            raise Exception("xhtml2pdf rendering error.")
            
        pdf_buffer.seek(0)
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=study_notes.pdf"}
        )
    except Exception as e:
        logger.error(f"Error during PDF export: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {str(e)}"
        )
