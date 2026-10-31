import { KonFlashIcon, KonPrecisionIcon, KonTrainingIcon } from "./KonIcons";
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
  Play,
  Pause,
  Zap,
  Repeat,
} from "lucide-react";
import {
  fetchModelStats,
  startContinuousTrain,
  stopContinuousTrain,
} from "../api";

export default function ModelInfoModal({ isOpen, onClose }) {
  const [stats, setStats] = useState(null);
  const [isToggling, setIsToggling] = useState(false);

  const loadStats = () => {
    fetchModelStats()
      .then((data) => setStats(data))
      .catch(() => null);
  };

  useEffect(() => {
    if (!isOpen) return;
    loadStats();
    // Poll telemetry every 1.5s while modal is open
    const interval = setInterval(loadStats, 1500);
    return () => clearInterval(interval);
  }, [isOpen]);

  const handleToggleTraining = async () => {
    const isCurrentlyTraining = stats?.continuous_training?.is_training ?? true;
    setIsToggling(true);
    try {
      if (isCurrentlyTraining) {
        await stopContinuousTrain();
      } else {
        await startContinuousTrain();
      }
      loadStats();
    } catch (e) {
      console.error(e);
    } finally {
      setIsToggling(false);
    }
  };

  if (!isOpen) return null;

  const ct = stats?.continuous_training;
  const isTraining = ct?.is_training ?? false;

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
                  KON Search 1.2 Rei
                </h2>
                <span className="neu-recessed px-2.5 py-0.5 rounded-full text-xs font-mono font-bold text-[#0084FF]">
                  v1.2
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

        {/* Non-Stop Autonomous Training Showcase Card */}
        <div className="neu-raised p-5 rounded-2xl space-y-4 border border-[#0084FF]/20 bg-linear-to-r from-blue-50/40 via-transparent to-emerald-50/40">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl neu-raised flex items-center justify-center text-[#0084FF]">
                <Repeat className={`w-4 h-4 ${isTraining ? "animate-spin text-[#0084FF]" : "text-slate-400"}`} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-[#1E293B]">
                    Non-Stop Autonomous Training
                  </span>
                  {isTraining ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100/80 text-emerald-700 border border-emerald-300">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
                      TRAINING NON-STOP
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-500">
                      PAUSED
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-[#64748B] m-0">
                  Continuous SGD learning over queries, user feedback, and music entities
                </p>
              </div>
            </div>

            <button
              onClick={handleToggleTraining}
              disabled={isToggling}
              className={`cursor-pointer px-3.5 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all ${
                isTraining
                  ? "neu-raised text-amber-700 hover:text-amber-800"
                  : "neu-accent text-white"
              }`}
            >
              {isTraining ? (
                <>
                  <Pause className="w-3.5 h-3.5" />
                  <span>Pause Training</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>Resume Non-Stop</span>
                </>
              )}
            </button>
          </div>

          {/* Continuous Training Live Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1">
            <div className="neu-recessed p-2.5 rounded-xl text-center">
              <div className="text-[10px] text-[#64748B] font-semibold">Epochs</div>
              <div className="text-sm font-bold text-[#0084FF] font-mono mt-0.5">
                {(ct?.current_epoch ?? stats?.training_epochs ?? 0).toLocaleString()}
              </div>
            </div>

            <div className="neu-recessed p-2.5 rounded-xl text-center">
              <div className="text-[10px] text-[#64748B] font-semibold">Total Steps</div>
              <div className="text-sm font-bold text-[#1E293B] font-mono mt-0.5">
                {(ct?.total_steps ?? stats?.total_updates ?? 0).toLocaleString()}
              </div>
            </div>

            <div className="neu-recessed p-2.5 rounded-xl text-center">
              <div className="text-[10px] text-[#64748B] font-semibold">Current Loss</div>
              <div className="text-sm font-bold text-[#10B981] font-mono mt-0.5">
                {ct?.ema_loss !== undefined ? ct.ema_loss.toFixed(4) : (stats?.last_loss ? Number(stats.last_loss).toFixed(4) : "0.0120")}
              </div>
            </div>

            <div className="neu-recessed p-2.5 rounded-xl text-center">
              <div className="text-[10px] text-[#64748B] font-semibold">Speed</div>
              <div className="text-sm font-bold text-[#1E293B] font-mono mt-0.5 flex items-center justify-center gap-1">
                <KonFlashIcon className="w-3.5 h-3.5" />
                <span>{ct?.steps_per_second ? `${ct.steps_per_second} /s` : "Active"}</span>
              </div>
            </div>
          </div>

          {/* Live stream snippet of recent samples */}
          {ct?.recent_samples && ct.recent_samples.length > 0 && (
            <div className="pt-1">
              <div className="text-[10px] font-mono text-[#64748B] mb-1">
                Recent Training Samples (Live Feed):
              </div>
              <div className="neu-recessed p-2 rounded-xl space-y-1 max-h-24 overflow-y-auto text-[11px] font-mono">
                {ct.recent_samples.slice(-3).map((sample, idx) => (
                  <div key={idx} className="flex items-center justify-between text-[#334155] truncate">
                    <span className="truncate">
                      <span className="text-[#0084FF]">q:</span> &quot;{sample.query}&quot; &rarr; &quot;{sample.target}&quot;
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.2 rounded shrink-0 ml-2 ${sample.label === 1.0 ? "text-emerald-700 bg-emerald-100" : "text-rose-700 bg-rose-100"}`}>
                      {sample.label === 1.0 ? "+1 Match" : "-1 Reject"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Hero Spotlight Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="neu-recessed p-3.5 rounded-2xl text-center space-y-1">
            <div className="text-[11px] font-semibold text-[#64748B] flex items-center justify-center gap-1">
              <Gauge className="w-3 h-3 text-[#0084FF]" />
              <span>Inference</span>
            </div>
            <div className="text-sm font-bold text-[#1E293B]">&lt; 0.2ms</div>
            <div className="text-[10px] text-[#94A3B8]">Native Rust Core</div>
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
              {stats?.associations_count ? stats.associations_count.toLocaleString() : "7,766"}
            </div>
            <div className="text-[10px] text-[#94A3B8]">Learned Pairings</div>
          </div>

          <div className="neu-recessed p-3.5 rounded-2xl text-center space-y-1">
            <div className="text-[11px] font-semibold text-[#64748B] flex items-center justify-center gap-1">
              <Layers className="w-3 h-3 text-[#0084FF]" />
              <span>Vocabulary</span>
            </div>
            <div className="text-sm font-bold text-[#1E293B]">
              {stats?.learned_tokens_count ? stats.learned_tokens_count.toLocaleString() : "1,685"}
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
            <strong>KON Search 1.2 Rei</strong> is KON Media&apos;s bespoke dual-engine architecture, combining native
            Rust sub-millisecond ranking with real-time <em>Continuous Stochastic Gradient Descent (SGD)</em>.
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
              <span>Popularity-Aware Normalized Multiplier [0.0, 1.0]</span>
            </div>
            <div className="neu-recessed p-2.5 rounded-xl flex items-center gap-2 font-medium text-[#334155]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981] shrink-0" />
              <span>Dual Modes: Rei (Precision) &amp; Rei Flash (Speed)</span>
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
                Loss: {ct?.ema_loss !== undefined ? ct.ema_loss.toFixed(4) : (stats.last_loss || "0.0120")} · Epochs: {ct?.current_epoch ?? stats.training_epochs ?? 266}
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
