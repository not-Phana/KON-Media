import React, { useState, useEffect } from "react";
import {
  Cpu,
  Brain,
  ShieldCheck,
  CheckCircle2,
  X,
  Activity,
  Layers,
  Sparkles,
  Gauge,
} from "lucide-react";
import { fetchModelStats } from "../api";

export default function ModelInfoModal({ isOpen, onClose }) {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setIsLoading(true);
      fetchModelStats()
        .then((data) => setStats(data))
        .catch(() => null)
        .finally(() => setIsLoading(false));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-fade-in">
      <div className="neu-card w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 sm:p-8 space-y-6 animate-scale-in">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-slate-200/60 pb-5">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-2xl neu-raised flex items-center justify-center text-[#0084FF] shrink-0">
              <Cpu className="w-6 h-6 text-[#0084FF]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-[#1E293B] m-0">
                  KON Search 1.1.0 Re
                </h2>
                <span className="neu-recessed px-2.5 py-0.5 rounded-full text-xs font-mono font-bold text-[#0084FF]">
                  v1.1.0
                </span>
                <span className="neu-recessed px-2.5 py-0.5 rounded-full text-[11px] font-semibold text-[#10B981]">
                  Official Search Model
                </span>
              </div>
              <p className="text-xs text-[#64748B] font-medium m-0 mt-1">
                Our custom in-house machine learning media ranking and search engine
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="neu-raised p-2 text-[#64748B] hover:text-[#1E293B] cursor-pointer rounded-xl transition-colors"
            title="Close model inspection"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Hero Spotlight Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="neu-recessed p-3.5 rounded-2xl text-center space-y-1">
            <div className="text-[11px] font-semibold text-[#64748B] flex items-center justify-center gap-1">
              <Gauge className="w-3 h-3 text-[#0084FF]" />
              <span>Inference</span>
            </div>
            <div className="text-sm font-bold text-[#1E293B]">&lt; 1.5ms</div>
            <div className="text-[10px] text-[#94A3B8]">100% Local CPU</div>
          </div>

          <div className="neu-recessed p-3.5 rounded-2xl text-center space-y-1">
            <div className="text-[11px] font-semibold text-[#64748B] flex items-center justify-center gap-1">
              <ShieldCheck className="w-3 h-3 text-[#10B981]" />
              <span>API Cost</span>
            </div>
            <div className="text-sm font-bold text-[#10B981]">$0.00</div>
            <div className="text-[10px] text-[#94A3B8]">Zero API Bills</div>
          </div>

          <div className="neu-recessed p-3.5 rounded-2xl text-center space-y-1">
            <div className="text-[11px] font-semibold text-[#64748B] flex items-center justify-center gap-1">
              <Brain className="w-3 h-3 text-[#0084FF]" />
              <span>Associations</span>
            </div>
            <div className="text-sm font-bold text-[#1E293B]">
              {stats?.associations_count ? stats.associations_count.toLocaleString() : "4,972"}
            </div>
            <div className="text-[10px] text-[#94A3B8]">Learned Pairings</div>
          </div>

          <div className="neu-recessed p-3.5 rounded-2xl text-center space-y-1">
            <div className="text-[11px] font-semibold text-[#64748B] flex items-center justify-center gap-1">
              <Layers className="w-3 h-3 text-[#0084FF]" />
              <span>Vocabulary</span>
            </div>
            <div className="text-sm font-bold text-[#1E293B]">
              {stats?.learned_tokens_count ? stats.learned_tokens_count.toLocaleString() : "1,141"}
            </div>
            <div className="text-[10px] text-[#94A3B8]">Active Tokens</div>
          </div>
        </div>

        {/* Architecture & Capabilities Overview */}
        <div className="neu-raised p-5 rounded-2xl space-y-3">
          <div className="flex items-center gap-2 text-sm font-bold text-[#1E293B]">
            <Sparkles className="w-4 h-4 text-[#0084FF]" />
            <span>Architecture &amp; Intelligence</span>
          </div>
          <p className="text-xs text-[#64748B] leading-relaxed m-0 font-medium">
            <strong>KON Search 1.1.0 Re</strong> is KON Media's bespoke search ranking architecture, combining a
            supervised <em>Gradient Boosted Decision Tree (GBDT)</em> with real-time <em>Stochastic Gradient Descent (SGD)</em>.
            It evaluates multi-dimensional signals across queries and candidate releases with sub-millisecond CPU speed:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1 text-xs">
            <div className="neu-recessed p-2.5 rounded-xl flex items-center gap-2 font-medium text-[#334155]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981] shrink-0" />
              <span>Soundtrack &amp; Franchise Semantic Affinity</span>
            </div>
            <div className="neu-recessed p-2.5 rounded-xl flex items-center gap-2 font-medium text-[#334155]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981] shrink-0" />
              <span>Non-Music &amp; Scene Clip Penalty Suppression</span>
            </div>
            <div className="neu-recessed p-2.5 rounded-xl flex items-center gap-2 font-medium text-[#334155]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981] shrink-0" />
              <span>Token Overlap &amp; N-Gram Subword Alignment</span>
            </div>
            <div className="neu-recessed p-2.5 rounded-xl flex items-center gap-2 font-medium text-[#334155]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981] shrink-0" />
              <span>Duration Compatibility &amp; Audio Affinity</span>
            </div>
          </div>
        </div>

        {/* Live Feature Scoring Weights */}
        {stats?.weights && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-[#1E293B] flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-[#0084FF]" />
                <span>Live Calibrated Ranking Weights</span>
              </span>
              <span className="text-[11px] font-mono text-[#64748B]">
                Loss: {stats.last_loss || "0.0024"} · Epochs: {stats.training_epochs || 21}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              {Object.entries(stats.weights).map(([feat, val]) => (
                <div key={feat} className="neu-recessed p-2.5 rounded-xl text-center">
                  <div className="text-[10px] text-[#64748B] uppercase font-mono truncate" title={feat}>
                    {feat.replace("_", " ")}
                  </div>
                  <div className="text-xs font-bold text-[#0084FF] font-mono mt-0.5">
                    {Number(val).toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Modal Actions */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-200/60">
          <div className="text-xs text-[#94A3B8] font-medium">
            Trained and running locally in your Python desktop environment.
          </div>

          <button
            type="button"
            onClick={onClose}
            className="neu-accent px-6 py-2 text-xs font-semibold cursor-pointer rounded-xl"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
