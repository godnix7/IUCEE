import React, { useState, useEffect } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { CLASS_COLORS, CLASS_LABELS } from '../map/MapLegend';

export const AI_CLASS_CHOICES = ['building', 'road', 'water', 'barren_land', 'tree_cover', 'agriculture'];

interface RelabelModalProps {
  open: boolean;
  originalLabel: string;
  featureLabel: string; // human label of the feature being corrected
  onClose: () => void;
  onSubmit: (correctedLabel: string, comment: string) => Promise<void> | void;
}

export const RelabelModal: React.FC<RelabelModalProps> = ({ open, originalLabel, featureLabel, onClose, onSubmit }) => {
  const [corrected, setCorrected] = useState<string>('');
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (open) {
      setCorrected('');
      setComment('');
      setErr('');
    }
  }, [open]);

  if (!open) return null;

  const submit = async () => {
    if (!corrected) {
      setErr('Please choose the correct class.');
      return;
    }
    setSubmitting(true);
    setErr('');
    try {
      await onSubmit(corrected, comment);
    } catch (e: any) {
      setErr(e.message || 'Failed to submit correction');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-[#111827] border border-slate-700 rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <AlertTriangle size={16} className="text-amber-400" /> Relabel Detection
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X size={18} /></button>
        </div>

        <div className="p-5 space-y-4">
          <div className="text-xs text-slate-400">
            AI predicted <span className="font-semibold text-slate-200">{CLASS_LABELS[originalLabel] || featureLabel}</span>.
            Choose the correct class. The original AI prediction is preserved for auditability.
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-2">Corrected Class</label>
            <div className="grid grid-cols-2 gap-2">
              {AI_CLASS_CHOICES.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCorrected(c)}
                  className={`flex items-center gap-2 p-2 rounded-lg border text-xs transition-colors ${
                    corrected === c ? 'bg-blue-500/10 border-blue-500/60 text-white' : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-600'
                  }`}
                >
                  <span className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: CLASS_COLORS[c] }} />
                  {CLASS_LABELS[c] || c}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Reason / Comment (optional)</label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={2}
              placeholder="Why is the AI label wrong?"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-blue-500 resize-none"
            />
          </div>

          {err && <div className="text-xs text-red-400">{err}</div>}
        </div>

        <div className="flex justify-end gap-2 px-5 py-4 border-t border-slate-800">
          <button onClick={onClose} className="px-3 py-2 text-xs rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700">Cancel</button>
          <button
            onClick={submit}
            disabled={submitting}
            className="px-3 py-2 text-xs rounded-lg bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-50"
          >
            {submitting ? 'Saving…' : 'Submit Correction'}
          </button>
        </div>
      </div>
    </div>
  );
};
