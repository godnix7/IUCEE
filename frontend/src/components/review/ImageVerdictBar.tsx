import React, { useState, useEffect } from 'react';
import { CheckCircle2, RefreshCw, XCircle, Send } from 'lucide-react';
import type { AnalysisReview } from '../../types';

interface Props {
  review: AnalysisReview | null;
  canEdit: boolean;
  saving: boolean;
  onVerdict: (status: 'accepted' | 'needs_relabel' | 'rejected', comment: string) => void;
}

const STATUS_META: Record<string, { label: string; cls: string }> = {
  accepted: { label: 'Accepted', cls: 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10' },
  needs_relabel: { label: 'Flagged — image re-sent', cls: 'text-amber-400 border-amber-500/40 bg-amber-500/10' },
  rejected: { label: 'Rejected', cls: 'text-red-400 border-red-500/40 bg-red-500/10' },
  pending: { label: 'Pending review', cls: 'text-slate-400 border-slate-600/40 bg-slate-700/30' },
};

export const ImageVerdictBar: React.FC<Props> = ({ review, canEdit, saving, onVerdict }) => {
  const [comment, setComment] = useState('');
  useEffect(() => { setComment(review?.comment || ''); }, [review?.id, review?.comment]);

  const status = review?.status || 'pending';
  const meta = STATUS_META[status] || STATUS_META.pending;

  return (
    <div className="bg-[#0e1420] border-b border-slate-800 px-5 py-3 shrink-0">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-xs font-semibold text-slate-300">Whole-image verdict:</span>
        <span className={`px-2 py-0.5 rounded-full text-[11px] border ${meta.cls}`}>{meta.label}</span>
        {review?.resent && review?.resent_job_id && (
          <span className="text-[11px] text-amber-300/80 flex items-center gap-1">
            <Send size={11} /> re-sent as job #{review.resent_job_id}
          </span>
        )}
        {review?.reviewer_email && (
          <span className="text-[10px] text-slate-500">by {review.reviewer_email}</span>
        )}

        {canEdit && (
          <div className="flex items-center gap-2 ml-auto flex-wrap">
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Reason (optional)"
              className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-[11px] text-white focus:outline-none focus:border-blue-500 w-48"
            />
            <button
              onClick={() => onVerdict('accepted', comment)}
              disabled={saving}
              className="px-2.5 py-1.5 rounded-lg text-[11px] bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1 disabled:opacity-40"
            >
              <CheckCircle2 size={13} /> Accept
            </button>
            <button
              onClick={() => onVerdict('needs_relabel', comment)}
              disabled={saving}
              title="Classes not detected properly — re-send the whole image for reprocessing"
              className="px-2.5 py-1.5 rounded-lg text-[11px] bg-amber-600 hover:bg-amber-500 text-white flex items-center gap-1 disabled:opacity-40"
            >
              <RefreshCw size={13} /> Needs Relabel · Re-send
            </button>
            <button
              onClick={() => onVerdict('rejected', comment)}
              disabled={saving}
              className="px-2.5 py-1.5 rounded-lg text-[11px] bg-red-600/80 hover:bg-red-600 text-white flex items-center gap-1 disabled:opacity-40"
            >
              <XCircle size={13} /> Reject
            </button>
          </div>
        )}
      </div>
      {!canEdit && <div className="text-[10px] text-slate-500 mt-1">Read-only — your role cannot submit a verdict.</div>}
    </div>
  );
};
