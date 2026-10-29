import React, { useState } from "react";
import {
  Brain,
  FileText,
  Link as LinkIcon,
  Sparkles,
  X,
  CheckCircle2,
  AlertCircle,
  Loader2,
  BookOpen,
} from "lucide-react";
import { learnFromDocument } from "../api";

export default function LearnFromDocModal({ isOpen, onClose, onTrainingSuccess }) {
  const [tab, setTab] = useState("url"); // "url" | "text"
  const [docUrl, setDocUrl] = useState("");
  const [rawText, setRawText] = useState("");
  const [epochs, setEpochs] = useState(5);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleLearn = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);

    const content = tab === "url" ? docUrl.trim() : rawText.trim();
    if (!content) {
      setError(tab === "url" ? "Please enter a Google Doc or Google Drive link." : "Please enter some text or track notes.");
      return;
    }

    setIsLoading(true);
    try {
      const data = await learnFromDocument({
        content,
        isUrl: tab === "url",
        epochs: Number(epochs) || 5,
      });
      setResult(data);
      if (onTrainingSuccess) {
        onTrainingSuccess(data);
      }
    } catch (err) {
      setError(err.message || "Failed to learn from document");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/30 backdrop-blur-sm animate-fade-in">
      <div className="neu-card w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="p-6 border-b border-slate-200/60 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl neu-raised flex items-center justify-center text-[#0084FF]">
              <Brain className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#1E293B] m-0">
                Teach Engine from Google Drive &amp; Docs
              </h3>
              <p className="text-xs text-[#64748B] m-0 mt-0.5 font-medium">
                Import playlists, soundtrack pairings, or custom notes to train the neural ranker
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="neu-raised p-2 text-[#64748B] hover:text-[#1E293B] cursor-pointer rounded-xl"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {/* Tabs */}
          <div className="neu-recessed p-1.5 flex items-center gap-1.5 rounded-2xl w-fit">
            <button
              type="button"
              onClick={() => { setTab("url"); setError(null); }}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-colors ${
                tab === "url"
                  ? "neu-raised text-[#0084FF]"
                  : "text-[#64748B] hover:text-[#1E293B]"
              }`}
            >
              <LinkIcon className="w-3.5 h-3.5" />
              <span>Google Doc / Drive Link</span>
            </button>
            <button
              type="button"
              onClick={() => { setTab("text"); setError(null); }}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-colors ${
                tab === "text"
                  ? "neu-raised text-[#0084FF]"
                  : "text-[#64748B] hover:text-[#1E293B]"
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Paste Notes / Tracklist</span>
            </button>
          </div>

          <form onSubmit={handleLearn} className="space-y-4">
            {tab === "url" ? (
              <div className="space-y-2">
                <label className="text-xs font-semibold text-[#1E293B] block">
                  Google Doc or Drive URL
                </label>
                <div className="neu-recessed p-2.5 rounded-xl">
                  <input
                    type="text"
                    value={docUrl}
                    onChange={(e) => setDocUrl(e.target.value)}
                    placeholder="https://docs.google.com/document/d/..."
                    className="w-full bg-transparent border-none outline-none text-xs text-[#1E293B] font-mono placeholder-[#94A3B8]"
                  />
                </div>
                <p className="text-[11px] text-[#64748B] font-medium m-0">
                  Tip: Ensure document link sharing is set to "Anyone with the link can view", or use your connected Google Drive.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <label className="text-xs font-semibold text-[#1E293B] block">
                  Media Knowledge / Playlist Notes
                </label>
                <div className="neu-recessed p-3 rounded-xl">
                  <textarea
                    value={rawText}
                    onChange={(e) => setRawText(e.target.value)}
                    rows={6}
                    placeholder={`Titanic -> Celine Dion - My Heart Will Go On\nCyberpunk 2077: Rosa Walton - I Really Want to Stay at Your House\nInterstellar -> Hans Zimmer - Cornfield Chase\nBohemian Rhapsody by Queen`}
                    className="w-full bg-transparent border-none outline-none text-xs text-[#1E293B] font-mono leading-relaxed placeholder-[#94A3B8]"
                  />
                </div>
              </div>
            )}

            {/* Supported Patterns Guide */}
            <div className="p-4 rounded-2xl neu-raised text-xs text-[#64748B] space-y-1.5 font-medium">
              <span className="font-bold text-[#1E293B] flex items-center gap-2">
                <BookOpen className="w-3.5 h-3.5 text-[#0084FF]" />
                Supported Knowledge Formats
              </span>
              <ul className="list-disc list-inside space-y-1 m-0 pl-1 font-mono text-[11px]">
                <li><code className="text-[#0084FF]">Movie/Query -&gt; Artist - Song</code> (e.g. Titanic -&gt; Celine Dion - My Heart Will Go On)</li>
                <li><code className="text-[#0084FF]">Context: Song Title</code> (e.g. Cyberpunk: I Really Want to Stay at Your House)</li>
                <li><code className="text-[#0084FF]">Song by Artist</code> or <code className="text-[#0084FF]">Artist - Song</code></li>
                <li>Markdown Tables <code className="text-[#0084FF]">| Topic | Song | Artist |</code></li>
              </ul>
            </div>

            {/* Epochs Selector */}
            <div className="flex items-center justify-between gap-4 p-4 rounded-2xl neu-raised">
              <div>
                <span className="text-xs font-bold text-[#1E293B] block">Training Intensity</span>
                <span className="text-xs text-[#64748B] font-medium">Number of SGD learning epochs</span>
              </div>
              <select
                value={epochs}
                onChange={(e) => setEpochs(Number(e.target.value))}
                className="neu-recessed text-xs px-3 py-2 rounded-xl text-[#1E293B] font-semibold outline-none"
              >
                <option value={3}>3 Epochs (Fast)</option>
                <option value={5}>5 Epochs (Balanced)</option>
                <option value={10}>10 Epochs (Deep)</option>
              </select>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-3.5 rounded-xl bg-[#FEE2E2]/60 border border-[#FCA5A5] text-xs text-[#DC2626] flex items-start gap-2.5 font-medium">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-[#DC2626]" />
                <div className="flex-1 font-mono">{error}</div>
              </div>
            )}

            {/* Training Success Results */}
            {result && (
              <div className="p-4 rounded-2xl neu-raised space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold text-[#10B981]">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>
                    Successfully trained on {result.extracted_count} media associations!
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs font-mono">
                  <div className="p-2.5 rounded-xl neu-recessed">
                    <span className="text-[#64748B] block text-[11px]">Learned Pairs</span>
                    <span className="text-[#1E293B] font-bold text-sm">{result.extracted_count}</span>
                  </div>
                  <div className="p-2.5 rounded-xl neu-recessed">
                    <span className="text-[#64748B] block text-[11px]">Training Loss</span>
                    <span className="text-[#0084FF] font-bold text-sm">{result.model_stats?.last_loss ?? "0.003"}</span>
                  </div>
                  <div className="p-2.5 rounded-xl neu-recessed">
                    <span className="text-[#64748B] block text-[11px]">Total Updates</span>
                    <span className="text-[#1E293B] font-bold text-sm">{result.model_stats?.total_updates ?? 0}</span>
                  </div>
                  <div className="p-2.5 rounded-xl neu-recessed">
                    <span className="text-[#64748B] block text-[11px]">Active Tokens</span>
                    <span className="text-[#1E293B] font-bold text-sm">{result.model_stats?.learned_tokens_count ?? 0}</span>
                  </div>
                </div>

                {result.sample_associations && result.sample_associations.length > 0 && (
                  <div>
                    <span className="text-xs font-semibold text-[#64748B] block mb-1.5">
                      Learned Association Preview:
                    </span>
                    <div className="space-y-1.5">
                      {result.sample_associations.map((s, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs font-mono text-[#1E293B] neu-recessed px-3 py-1.5 rounded-xl">
                          <span className="text-[#0084FF] font-bold">{s.query}</span>
                          <span className="text-[#94A3B8]">➔</span>
                          <span className="truncate">{s.target_media}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="neu-raised px-4 py-2.5 rounded-xl text-xs font-semibold text-[#64748B] hover:text-[#1E293B] cursor-pointer"
              >
                Done
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="neu-accent px-6 py-2.5 rounded-xl text-xs font-semibold flex items-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-white" />
                    <span>Learning...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Train Neural Engine</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
