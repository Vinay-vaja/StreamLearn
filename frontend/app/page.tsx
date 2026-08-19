"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  Youtube, 
  Sparkles, 
  BookOpen, 
  Download, 
  FileText, 
  CheckCircle, 
  Clock, 
  AlertCircle, 
  Loader2, 
  ArrowRight, 
  Copy, 
  Check, 
  HelpCircle
} from "./icons";

// --- Types ---
interface ChunkInfo {
  part: number;
  start_sec: number;
  end_sec: number;
}

interface VideoAnalyzeResponse {
  video_id: string;
  duration: number;
  title: string;
  chunks: ChunkInfo[];
  is_long: boolean;
}

interface SectionSummary {
  heading: string;
  key_points: string[];
}

interface ChunkStatus {
  status: "Pending" | "Extracting transcript" | "Segmenting" | "Generating notes" | "Done" | "Failed";
  error?: string;
  markdown?: string;
  sections?: SectionSummary[];
}

// --- Mermaid Diagram Renderer ---
const MermaidDiagram: React.FC<{ code: string; id: string }> = ({ code, id }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          themeVariables: {
            background: "#0a0a0f",
            primaryColor: "#14b8a6",
            primaryTextColor: "#e2e8f0",
            primaryBorderColor: "#2d3748",
            lineColor: "#4a5568",
            secondaryColor: "#1e293b",
            tertiaryColor: "#0f172a",
            nodeBorder: "#38b2ac",
            clusterBkg: "#0f172a",
            titleColor: "#f8fafc",
            edgeLabelBackground: "#1a202c",
            fontFamily: "Inter, system-ui, sans-serif",
          },
        });
        const uniqueId = `mermaid-${id}-${Date.now()}`;
        const { svg: rendered } = await mermaid.render(uniqueId, code);
        if (!cancelled) setSvg(rendered);
      } catch (err: unknown) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => { cancelled = true; };
  }, [code, id]);

  if (error) {
    return (
      <div className="bg-red-950/30 border border-red-800/40 rounded-xl p-4 my-4">
        <p className="text-xs text-red-400 font-mono mb-2">⚠ Diagram render error</p>
        <pre className="text-xs text-zinc-500 overflow-x-auto">{code}</pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="flex items-center gap-2 py-6 text-zinc-600 text-xs">
        <span className="inline-block w-3 h-3 rounded-full bg-teal-500/60 animate-pulse" />
        Rendering diagram...
      </div>
    );
  }

  return (
    <div
      ref={ref}
      className="my-5 bg-zinc-950/60 border border-zinc-800/60 rounded-xl p-4 overflow-x-auto flex justify-center"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
};

// --- React Markdown Renderer Component ---
interface MarkdownViewerProps {
  content: string;
}

const MarkdownViewer: React.FC<MarkdownViewerProps> = ({ content }) => {
  if (!content) return null;

  // Split on double-newlines BUT keep mermaid blocks intact
  // We first split by the mermaid fence, then process each segment
  const segments: Array<{ type: "mermaid"; code: string; key: string } | { type: "text"; content: string; key: string }> = [];
  const mermaidRegex = /```mermaid\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;
  let segIdx = 0;

  while ((match = mermaidRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "text", content: content.slice(lastIndex, match.index), key: `text-${segIdx++}` });
    }
    segments.push({ type: "mermaid", code: match[1].trim(), key: `mermaid-${segIdx++}` });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) {
    segments.push({ type: "text", content: content.slice(lastIndex), key: `text-${segIdx++}` });
  }

  return (
    <div className="space-y-2 text-zinc-300 leading-relaxed font-sans max-w-none">
      {segments.map((seg) => {
        if (seg.type === "mermaid") {
          return <MermaidDiagram key={seg.key} id={seg.key} code={seg.code} />;
        }
        // Render text segment block by block
        const blocks = seg.content.split("\n\n");
        return blocks.map((block, i) => {
          const trimmed = block.trim();
          if (!trimmed) return null;
          const blockKey = `${seg.key}-b${i}`;

          // H1 Title
          if (trimmed.startsWith("# ")) {
            return (
              <h1 key={blockKey} className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-indigo-400 mt-8 mb-4 border-b border-zinc-800 pb-3 tracking-tight">
                {trimmed.slice(2)}
              </h1>
            );
          }
          // H2 Subtitle
          if (trimmed.startsWith("## ")) {
            return (
              <h2 key={blockKey} className="text-2xl font-bold text-zinc-100 mt-8 mb-4 border-b border-zinc-800/60 pb-2 tracking-wide flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-teal-400" />
                {trimmed.slice(3)}
              </h2>
            );
          }
          // H3 Section Heading
          if (trimmed.startsWith("### ")) {
            return (
              <h3 key={blockKey} className="text-xl font-semibold text-zinc-200 mt-6 mb-3">
                {trimmed.slice(4)}
              </h3>
            );
          }

          // Horizontal Rule
          if (trimmed === "---") {
            return <hr key={blockKey} className="border-zinc-800/80 my-8" />;
          }

          // Code Block (non-mermaid)
          if (trimmed.startsWith("```")) {
            const code = trimmed.replace(/```[a-zA-Z]*\n?([\s\S]*?)```/, "$1");
            return (
              <pre key={blockKey} className="bg-zinc-950/80 border border-zinc-800/60 rounded-xl p-5 font-mono text-sm text-zinc-300 my-5 overflow-x-auto shadow-inner">
                <code>{code}</code>
              </pre>
            );
          }

          // List Items
          if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
            const items = trimmed.split("\n").map(item => item.replace(/^[\-\*]\s+/, ""));
            return (
              <ul key={blockKey} className="list-none pl-1 space-y-2.5 my-4">
                {items.map((item, j) => (
                  <li key={j} className="text-zinc-300 flex items-start gap-2.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-teal-400 mt-2.5 shrink-0" />
                    <span>{renderInlineMarkdown(item)}</span>
                  </li>
                ))}
              </ul>
            );
          }

          // Default Paragraph
          return (
            <p key={blockKey} className="text-zinc-300 text-justify">
              {renderInlineMarkdown(trimmed)}
            </p>
          );
        });
      })}
    </div>
  );
};

// Inline bold and code formatter
function renderInlineMarkdown(text: string) {
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={index} className="font-bold text-teal-300/90">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={index} className="bg-zinc-900 border border-zinc-800/60 text-teal-400 font-mono text-xs px-1.5 py-0.5 rounded shadow-sm">
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

// --- Helper Functions ---
function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

export default function Home() {
  const [url, setUrl] = useState("");
  const [chunkSizeMins, setChunkSizeMins] = useState(30);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [videoData, setVideoData] = useState<VideoAnalyzeResponse | null>(null);
  
  // Single-shot States
  const [singleStatus, setSingleStatus] = useState<string>("");
  const [singleMarkdown, setSingleMarkdown] = useState<string>("");
  const [singleSections, setSingleSections] = useState<SectionSummary[]>([]);
  
  // Chunk States
  const [chunksStatus, setChunksStatus] = useState<Record<string, ChunkStatus>>({});
  const [completedSections, setCompletedSections] = useState<SectionSummary[]>([]);
  const [reducedSummary, setReducedSummary] = useState<{ quick_revision: string; common_questions: string; markdown: string } | null>(null);
  const [isReducing, setIsReducing] = useState(false);

  // General States
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [exportingPDF, setExportingPDF] = useState(false);
  const [includeDiagrams, setIncludeDiagrams] = useState(true);

  // Poll progress state
  const pollProgress = (taskKey: string, onUpdate: (status: string) => void): Promise<string> => {
    return new Promise((resolve) => {
      const interval = setInterval(async () => {
        try {
          const res = await fetch(`http://localhost:8000/api/notes/progress/${taskKey}`);
          if (res.ok) {
            const data = await res.json();
            onUpdate(data.status);
            if (data.status === "Done" || data.status === "Failed") {
              clearInterval(interval);
              resolve(data.status);
            }
          }
        } catch {
          // Ignore network errors during polling
        }
      }, 800);
    });
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setIsAnalyzing(true);
    setError(null);
    setVideoData(null);
    setSingleMarkdown("");
    setSingleStatus("");
    setChunksStatus({});
    setCompletedSections([]);
    setReducedSummary(null);

    try {
      const response = await fetch("http://localhost:8000/api/notes/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          url: url.trim(), 
          chunk_size_mins: chunkSizeMins 
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to analyze YouTube video URL.");
      }

      const data: VideoAnalyzeResponse = await response.json();
      setVideoData(data);

      // Initialize status for each chunk if long
      if (data.is_long) {
        const initialStatus: Record<string, ChunkStatus> = {};
        data.chunks.forEach((chunk) => {
          const key = `${chunk.start_sec}-${chunk.end_sec}`;
          initialStatus[key] = { status: "Pending" };
        });
        setChunksStatus(initialStatus);
      } else {
        // Trigger single-shot automatically
        triggerSingleShot(data.video_id);
      }
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  // --- Single Shot Execution ---
  const triggerSingleShot = async (videoId: string) => {
    setSingleStatus("Extracting transcript");
    
    // Start polling in background
    pollProgress(videoId, (status) => {
      setSingleStatus(status);
    });

    try {
      const response = await fetch("http://localhost:8000/api/notes/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          video_id: videoId,
          include_diagrams: includeDiagrams
        })
      });

      if (!response.ok) {
        throw new Error("Failed to generate lecture notes.");
      }

      const resData = await response.json();
      setSingleMarkdown(resData.markdown);
      setSingleSections(resData.sections);
      setSingleStatus("Done");
    } catch (err: any) {
      setSingleStatus("Failed");
      setError(err.message || "Failed to generate notes for short video.");
    }
  };

  // --- Chunk Note Execution ---
  const triggerChunkNotes = async (chunk: ChunkInfo) => {
    const key = `${chunk.start_sec}-${chunk.end_sec}`;
    const taskKey = `${videoData?.video_id}_${parseInt(chunk.start_sec.toString())}_${parseInt(chunk.end_sec.toString())}`;

    // Update status to starting
    setChunksStatus(prev => ({
      ...prev,
      [key]: { status: "Extracting transcript" }
    }));

    // Poll progress
    pollProgress(taskKey, (status) => {
      setChunksStatus(prev => ({
        ...prev,
        [key]: { status: status as any }
      }));
    });

    try {
      const response = await fetch("http://localhost:8000/api/notes/generate-chunk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_id: videoData?.video_id,
          start_sec: chunk.start_sec,
          end_sec: chunk.end_sec,
          include_diagrams: includeDiagrams
        })
      });

      if (!response.ok) {
        throw new Error("Failed to generate notes for this section.");
      }

      const resData = await response.json();
      
      setChunksStatus(prev => ({
        ...prev,
        [key]: { 
          status: "Done",
          markdown: resData.markdown,
          sections: resData.sections
        }
      }));

      // Accumulate completed sections for reduction
      if (resData.sections) {
        setCompletedSections(prev => [...prev, ...resData.sections]);
      }

    } catch (err: any) {
      setChunksStatus(prev => ({
        ...prev,
        [key]: { status: "Failed", error: err.message }
      }));
    }
  };

  // --- Final Summary Reduction Pass ---
  const handleGenerateSummary = async () => {
    if (completedSections.length === 0) return;
    setIsReducing(true);
    setError(null);

    try {
      const response = await fetch("http://localhost:8000/api/notes/reduce", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sections: completedSections })
      });

      if (!response.ok) {
        throw new Error("Failed to produce final revision summary.");
      }

      const data = await response.json();
      setReducedSummary(data);
    } catch (err: any) {
      setError(err.message || "Summary reduction pass failed.");
    } finally {
      setIsReducing(false);
    }
  };

  // --- Get Combined Markdown ---
  const getCombinedMarkdown = () => {
    if (!videoData) return "";
    
    if (!videoData.is_long) {
      return singleMarkdown;
    }

    // Combine all completed chunks' markdown in chronological order
    const chunksMarkdown = videoData.chunks
      .map(chunk => {
        const key = `${chunk.start_sec}-${chunk.end_sec}`;
        return chunksStatus[key]?.markdown || "";
      })
      .filter(md => md.trim() !== "")
      .join("\n\n");

    const finalMD = [
      `# ${videoData.title}`,
      `\n## Table of Contents`,
      completedSections.map(s => {
        const anchor = s.heading.toLowerCase().replace(" ", "-").replace("?", "").replace("!", "").replace(":", "");
        return `- [${s.heading}](#${anchor})`;
      }).join("\n"),
      reducedSummary ? `- [Quick Revision Summary](#quick-revision-summary)` : "",
      reducedSummary ? `- [Common Interview/Exam Questions](#common-interview-questions)` : "",
      `\n---`,
      `\n${chunksMarkdown}`,
      reducedSummary ? `\n### <a name="quick-revision-summary"></a>Quick Revision Summary\n\n${reducedSummary.quick_revision}\n\n---` : "",
      reducedSummary ? `\n### <a name="common-interview-questions"></a>Common Interview/Exam Questions\n\n${reducedSummary.common_questions}` : "",
    ].filter(p => p !== "").join("\n");

    return finalMD;
  };

  // --- Copy Clipboard ---
  const copyToClipboard = () => {
    const md = getCombinedMarkdown();
    if (!md) return;
    navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // --- Download Markdown ---
  const downloadMarkdown = () => {
    const md = getCombinedMarkdown();
    if (!md) return;
    const blob = new Blob([md], { type: "text/markdown" });
    const urlBlob = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = urlBlob;
    a.download = `${videoData?.title.replace(/[^a-z0-9]/gi, "_").toLowerCase() || "study_notes"}.md`;
    a.click();
    URL.revokeObjectURL(urlBlob);
  };

  // --- Export PDF ---
  const downloadPDF = async () => {
    const md = getCombinedMarkdown();
    if (!md) return;
    setExportingPDF(true);
    
    try {
      const response = await fetch("http://localhost:8000/api/notes/export-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markdown: md })
      });

      if (!response.ok) {
        throw new Error("Failed to compile Markdown into PDF.");
      }

      const blob = await response.blob();
      const urlBlob = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = urlBlob;
      a.download = `${videoData?.title.replace(/[^a-z0-9]/gi, "_").toLowerCase() || "study_notes"}.pdf`;
      a.click();
      URL.revokeObjectURL(urlBlob);
    } catch (err: any) {
      setError(err.message || "PDF compilation failed.");
    } finally {
      setExportingPDF(false);
    }
  };

  return (
    <div className="flex-1 w-full max-w-6xl mx-auto px-4 py-12 flex flex-col justify-start">
      {/* Header */}
      <header className="mb-10 text-center relative">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 -z-10 w-72 h-72 bg-gradient-to-r from-indigo-500/20 to-teal-500/20 blur-3xl rounded-full" />
        <h1 className="text-4xl md:text-5xl font-black tracking-tight text-white mb-3 flex items-center justify-center gap-3">
          <Sparkles className="w-10 h-10 text-teal-400 animate-pulse" />
          <span className="bg-gradient-to-r from-white via-zinc-200 to-zinc-500 bg-clip-text text-transparent">
            LecToNotes AI
          </span>
        </h1>
        <p className="text-zinc-400 text-lg max-w-xl mx-auto">
          Convert any YouTube lecture into beautifully structured, timestamped study notes instantly.
        </p>
      </header>

      {/* Input Form */}
      <section className="mb-10">
        <form onSubmit={handleAnalyze} className="backdrop-blur-md bg-zinc-900/60 border border-zinc-800/80 p-6 rounded-2xl shadow-2xl relative overflow-hidden">
          <div className="absolute -top-32 -left-32 w-64 h-64 bg-indigo-500/10 rounded-full blur-2xl pointer-events-none" />
          
          <div className="flex flex-col md:flex-row gap-4 items-center">
            <div className="relative w-full flex-1">
              <Youtube className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-red-500" />
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Paste YouTube Video URL (e.g. https://www.youtube.com/watch?v=...)"
                className="w-full bg-zinc-950 border border-zinc-800/80 rounded-xl py-3.5 pl-12 pr-4 text-white placeholder-zinc-500 focus:outline-none focus:border-teal-500/50 transition-all font-medium text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={isAnalyzing || !url}
              className="w-full md:w-auto bg-gradient-to-r from-teal-500 to-indigo-600 hover:from-teal-400 hover:to-indigo-500 text-black font-semibold rounded-xl px-7 py-3.5 shadow-lg shadow-teal-500/10 transition-all active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none flex items-center justify-center gap-2"
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-black" />
                  Analyzing Video...
                </>
              ) : (
                <>
                  Generate Notes
                  <ArrowRight className="w-4 h-4 text-black" />
                </>
              )}
            </button>
          </div>

          {/* Conditional Duration Options (Shown if user wants to preset or video > 2 hours) */}
          <div className="mt-4 pt-4 border-t border-zinc-800/40 flex flex-wrap gap-6 items-center text-xs text-zinc-500">
            <span className="font-semibold text-zinc-400 uppercase tracking-wider">Partition Size for Long Videos:</span>
            <label className="flex items-center gap-2 cursor-pointer hover:text-zinc-300 transition-colors">
              <input
                type="radio"
                name="chunkSize"
                checked={chunkSizeMins === 15}
                onChange={() => setChunkSizeMins(15)}
                className="accent-teal-400"
              />
              15 Mins
            </label>
            <label className="flex items-center gap-2 cursor-pointer hover:text-zinc-300 transition-colors">
              <input
                type="radio"
                name="chunkSize"
                checked={chunkSizeMins === 30}
                onChange={() => setChunkSizeMins(30)}
                className="accent-teal-400"
              />
              30 Mins (Default)
            </label>
            <label className="flex items-center gap-2 cursor-pointer hover:text-zinc-300 transition-colors">
              <input
                type="radio"
                name="chunkSize"
                checked={chunkSizeMins === 45}
                onChange={() => setChunkSizeMins(45)}
                className="accent-teal-400"
              />
              45 Mins
            </label>
            <div className="h-4 w-px bg-zinc-800/80" />
            <label className="flex items-center gap-2 cursor-pointer text-zinc-400 hover:text-zinc-300 transition-colors">
              <input
                type="checkbox"
                checked={includeDiagrams}
                onChange={(e) => setIncludeDiagrams(e.target.checked)}
                className="accent-teal-400 rounded bg-zinc-950 border-zinc-800"
              />
              Include Mermaid Diagrams
            </label>
            <div className="flex items-center gap-1.5 ml-auto text-zinc-600" title="Videos under 30 minutes are processed in one automatic pass. Chunks only apply to long videos.">
              <HelpCircle className="w-3.5 h-3.5" />
              <span>Info</span>
            </div>
          </div>
        </form>
      </section>

      {/* Error Message */}
      {error && (
        <section className="mb-8">
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl flex items-center gap-3 text-sm font-medium">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span>{error}</span>
          </div>
        </section>
      )}

      {/* Video Details Card */}
      {videoData && (
        <section className="mb-10 animate-fade-in">
          <div className="backdrop-blur-md bg-zinc-900/40 border border-zinc-800/60 p-5 rounded-2xl flex flex-col md:flex-row gap-5 items-start">
            <div className="relative w-full md:w-56 shrink-0 aspect-video rounded-xl overflow-hidden bg-zinc-950 border border-zinc-800 flex items-center justify-center group shadow-md">
              {/* YouTube Thumbnail */}
              <img
                src={`https://img.youtube.com/vi/${videoData.video_id}/mqdefault.jpg`}
                alt={videoData.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-all duration-300"
              />
              <div className="absolute bottom-2 right-2 bg-black/85 backdrop-blur-sm text-[10px] text-zinc-300 px-2 py-0.5 rounded font-mono font-bold flex items-center gap-1 border border-zinc-800">
                <Clock className="w-3 h-3 text-zinc-400" />
                {formatTime(videoData.duration)}
              </div>
            </div>

            <div className="flex-1 space-y-2">
              <div className="flex flex-wrap gap-2 items-center">
                <span className="text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700/50">
                  {videoData.is_long ? "Long Video (> 30m)" : "Short Video (≤ 30m)"}
                </span>
                <span className="text-[10px] font-mono text-zinc-500">ID: {videoData.video_id}</span>
              </div>
              <h2 className="text-xl font-bold text-white tracking-tight">{videoData.title}</h2>
              <p className="text-xs text-zinc-400 font-medium">
                Detected Duration: <span className="text-zinc-200">{formatTime(videoData.duration)}</span>
              </p>

              {/* Pipeline Progress for Short Video */}
              {!videoData.is_long && (
                <div className="pt-4 space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-zinc-400">Processing Progress</span>
                    <span className="text-teal-400 font-bold">{singleStatus}</span>
                  </div>
                  <div className="w-full bg-zinc-950 rounded-full h-2 border border-zinc-800 overflow-hidden">
                    <div 
                      className="bg-gradient-to-r from-teal-500 to-indigo-500 h-full transition-all duration-500" 
                      style={{
                        width: 
                          singleStatus === "Extracting transcript" ? "25%" :
                          singleStatus === "Segmenting" ? "50%" :
                          singleStatus === "Generating notes" ? "75%" :
                          singleStatus === "Done" ? "100%" : "0%"
                      }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-zinc-600 font-semibold uppercase">
                    <span>Extracting</span>
                    <span>Segmenting</span>
                    <span>Generating</span>
                    <span>Done</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Long Video Chunking Interface */}
      {videoData && videoData.is_long && (
        <section className="mb-10 animate-fade-in">
          <div className="backdrop-blur-md bg-zinc-900/30 border border-zinc-800/40 p-6 rounded-2xl space-y-5">
            <div>
              <h3 className="text-lg font-bold text-white mb-1">Lecture Partitioning</h3>
              <p className="text-xs text-zinc-400">
                This video is over 30 minutes long. We have deterministically snapped boundaries to natural pauses near every {chunkSizeMins} minutes. Select chunks to process them on-demand.
              </p>
            </div>

            {/* Chunk Buttons Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {videoData.chunks.map((chunk) => {
                const key = `${chunk.start_sec}-${chunk.end_sec}`;
                const chunkState = chunksStatus[key] || { status: "Pending" };
                const isCompleted = chunkState.status === "Done";
                const isProcessing = ["Extracting transcript", "Segmenting", "Generating notes"].includes(chunkState.status);
                
                return (
                  <div 
                    key={chunk.part} 
                    className={`border p-4 rounded-xl flex flex-col justify-between gap-3 transition-all relative ${
                      isCompleted 
                        ? "bg-teal-500/5 border-teal-500/20" 
                        : isProcessing 
                        ? "bg-indigo-500/5 border-indigo-500/20"
                        : "bg-zinc-950/40 border-zinc-800/60 hover:border-zinc-700/50"
                    }`}
                  >
                    <div>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs font-extrabold uppercase tracking-wide text-zinc-400">Part {chunk.part}</span>
                        <span className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded-md border ${
                          isCompleted
                            ? "bg-teal-500/10 border-teal-500/20 text-teal-400"
                            : isProcessing
                            ? "bg-indigo-500/10 border-indigo-500/20 text-indigo-400"
                            : "bg-zinc-800 border-zinc-700 text-zinc-500"
                        }`}>
                          {chunkState.status}
                        </span>
                      </div>
                      <div className="text-xs font-mono text-zinc-400 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-zinc-500" />
                        <span>{formatTime(chunk.start_sec)} – {formatTime(chunk.end_sec)}</span>
                      </div>
                    </div>

                    {isProcessing && (
                      <div className="space-y-1">
                        <div className="flex justify-between text-[9px] text-zinc-500 font-semibold uppercase">
                          <span className={chunkState.status === "Extracting transcript" ? "text-teal-400" : ""}>Extract</span>
                          <span className={chunkState.status === "Segmenting" ? "text-teal-400" : ""}>Segment</span>
                          <span className={chunkState.status === "Generating notes" ? "text-teal-400" : ""}>Generate</span>
                        </div>
                        <div className="w-full bg-zinc-900 rounded-full h-1 border border-zinc-800 overflow-hidden">
                          <div 
                            className="bg-gradient-to-r from-teal-500 to-indigo-500 h-full transition-all duration-300"
                            style={{
                              width: 
                                chunkState.status === "Extracting transcript" ? "33%" :
                                chunkState.status === "Segmenting" ? "66%" :
                                chunkState.status === "Generating notes" ? "90%" : "0%"
                            }}
                          />
                        </div>
                      </div>
                    )}

                    {!isCompleted && !isProcessing && (
                      <button
                        onClick={() => triggerChunkNotes(chunk)}
                        className="w-full bg-zinc-900 hover:bg-zinc-800/80 text-zinc-300 font-semibold py-2 px-3 rounded-lg border border-zinc-800 hover:border-zinc-700 transition-all text-xs active:scale-[0.98]"
                      >
                        {chunkState.status === "Failed" ? "Retry Generate" : "Generate Notes"}
                      </button>
                    )}

                    {isCompleted && (
                      <div className="text-teal-400 text-xs font-bold flex items-center gap-1.5 py-2 justify-center bg-teal-500/10 rounded-lg border border-teal-500/20">
                        <CheckCircle className="w-4 h-4 text-teal-400" />
                        Completed
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Reduce summary action panel */}
            {completedSections.length > 0 && (
              <div className="pt-4 border-t border-zinc-800/40 flex flex-col md:flex-row justify-between items-center gap-4">
                <div className="text-xs text-zinc-400">
                  Generated notes for <span className="text-white font-bold">{completedSections.length}</span> sections. Compile them into a final summary revision.
                </div>
                <button
                  onClick={handleGenerateSummary}
                  disabled={isReducing || completedSections.length === 0}
                  className="bg-gradient-to-r from-teal-500 to-indigo-500 text-black font-semibold rounded-xl px-5 py-3 transition-all text-xs active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none flex items-center gap-2 hover:from-teal-400 hover:to-indigo-400 shadow-md shadow-teal-500/5"
                >
                  {isReducing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-black" />
                      Creating Final Summary...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 text-black" />
                      {reducedSummary ? "Re-generate Final Summary" : "Generate Final Summary"}
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Render Note Results (Viewer) */}
      {(singleMarkdown || (videoData?.is_long && Object.values(chunksStatus).some(c => c.status === "Done"))) && (
        <section className="mb-12 animate-fade-in">
          <div className="backdrop-blur-md bg-zinc-900/50 border border-zinc-800/60 rounded-2xl overflow-hidden shadow-2xl">
            {/* Toolbar */}
            <div className="bg-zinc-950/80 border-b border-zinc-800/80 px-6 py-4 flex flex-wrap gap-4 items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-teal-400" />
                <span className="font-bold text-sm tracking-wide text-zinc-100 uppercase">Compiled Lecture Notes</span>
              </div>
              <div className="flex gap-2.5">
                <button
                  onClick={copyToClipboard}
                  className="bg-zinc-900 border border-zinc-800 hover:border-zinc-700/80 hover:bg-zinc-800/60 text-zinc-300 rounded-lg p-2 flex items-center justify-center gap-1.5 transition-all text-xs font-semibold"
                  title="Copy markdown to clipboard"
                >
                  {copied ? (
                    <>
                      <Check className="w-4 h-4 text-teal-400" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      Copy Markdown
                    </>
                  )}
                </button>
                <button
                  onClick={downloadMarkdown}
                  className="bg-zinc-900 border border-zinc-800 hover:border-zinc-700/80 hover:bg-zinc-800/60 text-zinc-300 rounded-lg p-2 flex items-center justify-center gap-1.5 transition-all text-xs font-semibold"
                  title="Download raw markdown file"
                >
                  <Download className="w-4 h-4 text-zinc-400" />
                  .MD
                </button>
                <button
                  onClick={downloadPDF}
                  disabled={exportingPDF}
                  className="bg-zinc-900 border border-zinc-800 hover:border-zinc-700/80 hover:bg-zinc-800/60 text-zinc-300 rounded-lg p-2 flex items-center justify-center gap-1.5 transition-all text-xs font-semibold disabled:opacity-50"
                  title="Compile and download PDF format"
                >
                  {exportingPDF ? (
                    <Loader2 className="w-4 h-4 animate-spin text-zinc-400" />
                  ) : (
                    <FileText className="w-4 h-4 text-zinc-400" />
                  )}
                  .PDF
                </button>
              </div>
            </div>

            {/* Document Viewer Body */}
            <div className="p-8 max-h-[70vh] overflow-y-auto bg-zinc-950/20">
              {/* Short video renderer */}
              {!videoData?.is_long && (
                <MarkdownViewer content={singleMarkdown} />
              )}

              {/* Long video renderer */}
              {videoData?.is_long && (
                <div className="space-y-8">
                  {/* Document Header Title */}
                  <h1 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white to-zinc-400 mb-8 border-b border-zinc-800 pb-3 tracking-tight">
                    {videoData.title}
                  </h1>
                  
                  {/* Combined Chunks rendering */}
                  {videoData.chunks.map((chunk) => {
                    const key = `${chunk.start_sec}-${chunk.end_sec}`;
                    const chunkState = chunksStatus[key];
                    if (!chunkState || chunkState.status !== "Done" || !chunkState.markdown) return null;
                    return (
                      <div key={chunk.part} className="border-l-2 border-teal-500/20 pl-6 my-8 py-2 relative">
                        <span className="absolute top-2 -left-2.5 bg-zinc-900 text-teal-400 text-[10px] font-extrabold border border-teal-500/30 px-2 py-0.5 rounded">
                          Part {chunk.part} ({formatTime(chunk.start_sec)} - {formatTime(chunk.end_sec)})
                        </span>
                        <MarkdownViewer content={chunkState.markdown} />
                      </div>
                    );
                  })}

                  {/* Reduced Final Summary */}
                  {reducedSummary && (
                    <div className="border-t border-zinc-800 pt-8 mt-12 space-y-8">
                      <h2 className="text-2xl font-bold text-zinc-100 flex items-center gap-2 border-b border-zinc-800 pb-2">
                        <Sparkles className="w-6 h-6 text-teal-400" />
                        Quick Revision Summary
                      </h2>
                      <p className="text-zinc-300 text-justify leading-relaxed">
                        {reducedSummary.quick_revision}
                      </p>

                      <h2 className="text-2xl font-bold text-zinc-100 flex items-center gap-2 border-b border-zinc-800 pb-2 pt-6">
                        <HelpCircle className="w-6 h-6 text-indigo-400" />
                        Common Interview/Exam Questions
                      </h2>
                      <div className="text-zinc-300 font-sans space-y-6">
                        {/* Questions rendering */}
                        {reducedSummary.common_questions.split("\n\n").map((block, qIdx) => {
                          if (!block.trim()) return null;
                          return (
                            <div key={qIdx} className="bg-zinc-950/40 border border-zinc-800/40 p-5 rounded-xl space-y-2">
                              {renderInlineMarkdown(block)}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
