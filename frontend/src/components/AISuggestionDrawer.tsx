import React, { useState, useEffect } from 'react';
import {
  X,
  Sparkles,
  Check,
  XCircle,
  ShieldCheck,
  ArrowRight,
  TrendingUp,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import type { AIMetrics, AISuggestion } from '../types';
import { api } from '../services/api';

interface AISuggestionDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  suggestions: AISuggestion[];
  onAccept: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
  onRefreshSuggestions: () => Promise<void>;
}

export const AISuggestionDrawer: React.FC<AISuggestionDrawerProps> = ({
  isOpen,
  onClose,
  suggestions,
  onAccept,
  onReject,
  onRefreshSuggestions,
}) => {
  const [metrics, setMetrics] = useState<AIMetrics | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [processingId, setProcessingId] = useState<string | null>(null);

  const fetchMetrics = async () => {
    try {
      const data = await api.getAIMetrics();
      setMetrics(data);
    } catch {
      // fallback
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchMetrics();
    }
  }, [isOpen, suggestions]);

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      await onRefreshSuggestions();
      await fetchMetrics();
    } finally {
      setIsGenerating(false);
    }
  };

  const handleAccept = async (id: string) => {
    setProcessingId(id);
    try {
      await onAccept(id);
      await fetchMetrics();
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (id: string) => {
    setProcessingId(id);
    try {
      await onReject(id);
      await fetchMetrics();
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <aside className={`ai-drawer ${isOpen ? 'is-open' : ''}`}>
      <div className="ai-drawer-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={18} style={{ color: '#ec4899' }} />
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>AI Dependency Copilot</h3>
        </div>
        <button className="card-icon-btn" onClick={onClose}>
          <X size={18} />
        </button>
      </div>

      {/* Untrusted AI Security / Grounding Banner */}
      <div
        style={{
          padding: '10px 18px',
          background: 'rgba(99, 102, 241, 0.08)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '0.74rem',
          color: '#cbd5e1',
        }}
      >
        <ShieldCheck size={16} style={{ color: '#818cf8', flexShrink: 0 }} />
        <span>
          Untrusted AI Paradigm: Closed-set grounded, verified by DAG engine before acceptance.
        </span>
      </div>

      {/* Metrics Banner */}
      <div className="ai-metrics-banner">
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <TrendingUp size={14} style={{ color: '#a855f7' }} />
          <span>Acceptance Rate:</span>
          <span style={{ fontWeight: 700, color: 'var(--text-main)' }}>
            {metrics ? `${metrics.acceptance_rate}%` : '0%'}
          </span>
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)' }}>
          {metrics?.accepted || 0} accepted / {metrics?.rejected || 0} rejected
        </div>
      </div>

      {/* Action to trigger generation */}
      <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
        <button
          className="btn btn-ai"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={handleGenerate}
          disabled={isGenerating}
        >
          {isGenerating ? (
            <>
              <Loader2 size={15} className="spin-animation" />
              <span>Analyzing tasks & DAG rules...</span>
            </>
          ) : (
            <>
              <RefreshCw size={15} />
              <span>Analyze & Propose Dependencies</span>
            </>
          )}
        </button>
      </div>

      {/* Suggestions List */}
      <div className="ai-suggestions-list">
        {suggestions.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '60px 20px',
              textAlign: 'center',
              color: 'var(--text-subtle)',
              gap: '10px',
            }}
          >
            <Sparkles size={32} style={{ color: 'var(--text-subtle)', opacity: 0.5 }} />
            <p style={{ fontSize: '0.88rem' }}>No pending suggestions.</p>
            <p style={{ fontSize: '0.76rem', color: 'var(--text-muted)', maxWidth: '280px' }}>
              Click &quot;Analyze & Propose Dependencies&quot; to inspect active tasks with the LLM pipeline.
            </p>
          </div>
        ) : (
          suggestions.map((s) => {
            const isBusy = processingId === s.id;
            return (
              <div key={s.id} className="ai-suggestion-card">
                <div className="ai-card-conn">
                  <span style={{ color: '#38bdf8' }}>{s.prerequisite_title || s.prerequisite_id}</span>
                  <ArrowRight size={13} style={{ color: 'var(--text-subtle)', flexShrink: 0 }} />
                  <span style={{ color: '#a855f7' }}>{s.task_title || s.task_id}</span>
                </div>

                <div className="ai-card-rationale">
                  &ldquo;{s.rationale}&rdquo;
                </div>

                <div className="ai-card-footer">
                  <span className="ai-conf-meter">
                    Confidence: {(s.confidence * 100).toFixed(0)}%
                  </span>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="btn btn-danger"
                      style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                      onClick={() => handleReject(s.id)}
                      disabled={isBusy}
                    >
                      <XCircle size={13} />
                      <span>Reject</span>
                    </button>

                    <button
                      className="btn btn-primary"
                      style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                      onClick={() => handleAccept(s.id)}
                      disabled={isBusy}
                    >
                      <Check size={13} />
                      <span>Accept</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
