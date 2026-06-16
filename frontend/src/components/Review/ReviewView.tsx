import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Eye,
  EyeOff,
  Play,
  RotateCcw,
  Save,
  Trash2,
  X,
} from 'lucide-react';
import { api } from '../../api';

interface ReviewViewProps {
  project: {
    id: number;
    name: string;
    classes: Array<{
      id: number;
      name: string;
      color: string;
      shortcut_key?: string;
    }>;
  };
}

type EditableAnnotation = {
  id?: number;
  class_name: string;
  confidence?: number;
  segmentation: number[][];
  bbox?: any;
  deleted?: boolean;
};

export default function ReviewView({ project }: ReviewViewProps) {
  const reviewClasses = useMemo(
    () => project.classes.filter((classDef) => classDef.name.toLowerCase() !== 'unknown'),
    [project.classes],
  );
  const [queue, setQueue] = useState<any[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [annotations, setAnnotations] = useState<EditableAnnotation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overlayVisible, setOverlayVisible] = useState(true);
  const [selectedRegion, setSelectedRegion] = useState<number | null>(null);
  const [hoveredRegion, setHoveredRegion] = useState<number | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [reviewNotes, setReviewNotes] = useState('');
  const [rejectionClass, setRejectionClass] = useState(reviewClasses[0]?.name || '');
  const [rejectionNotes, setRejectionNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const currentImage = queue[currentIndex];

  useEffect(() => {
    fetchQueue();
  }, [project?.id]);

  useEffect(() => {
    if (!reviewClasses.some((classDef) => classDef.name === rejectionClass)) {
      setRejectionClass(reviewClasses[0]?.name || '');
    }
  }, [reviewClasses, rejectionClass]);

  useEffect(() => {
    if (currentImage) {
      fetchAnnotations(currentImage.id);
      setReviewNotes('');
      setRejectionNotes('');
      setSelectedRegion(null);
    } else {
      setAnnotations([]);
    }
  }, [currentImage]);

  const visibleAnnotations = useMemo(
    () => annotations.filter((annotation) => !annotation.deleted),
    [annotations],
  );

  const fetchQueue = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.review.getQueue(project.id);
      setQueue(data);
      setCurrentIndex(0);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch review queue');
    } finally {
      setLoading(false);
    }
  };

  const parseAnnotation = (annotation: any): EditableAnnotation => {
    let segmentation: number[][] = [];
    let bbox: any = {};
    try {
      segmentation = JSON.parse(annotation.segmentation_json || '[]');
    } catch {
      segmentation = [];
    }
    try {
      bbox = JSON.parse(annotation.bbox_json || '{}');
    } catch {
      bbox = {};
    }
    return {
      id: annotation.id,
      class_name: annotation.class_name,
      confidence: annotation.confidence,
      segmentation,
      bbox,
    };
  };

  const fetchAnnotations = async (imageId: number) => {
    try {
      const data = await api.review.getAnnotations(project.id, imageId);
      setAnnotations(data.map(parseAnnotation));
    } catch (err) {
      console.error('Failed to fetch annotations', err);
    }
  };

  const removeCurrentImageFromQueue = () => {
    setQueue((prevQueue) => {
      const newQueue = prevQueue.filter((_, idx) => idx !== currentIndex);
      if (newQueue.length === 0) {
        setCurrentIndex(0);
        fetchQueue();
      } else if (currentIndex >= newQueue.length) {
        setCurrentIndex(newQueue.length - 1);
      }
      return newQueue;
    });
  };

  const handleApprove = async () => {
    if (!currentImage) return;
    setSaving(true);
    try {
      await api.review.markViewed(project.id, currentImage.id, reviewNotes);
      removeCurrentImageFromQueue();
    } catch (err) {
      alert('Failed to approve: ' + err);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveCorrections = async () => {
    if (!currentImage) return;
    setSaving(true);
    try {
      await api.review.correct(
        project.id,
        currentImage.id,
        visibleAnnotations.map((annotation) => ({
          id: annotation.id,
          class_name: annotation.class_name,
          segmentation: annotation.segmentation,
          bbox: annotation.bbox || {},
        })),
        reviewNotes,
      );
      removeCurrentImageFromQueue();
    } catch (err) {
      alert('Failed to save corrections: ' + err);
    } finally {
      setSaving(false);
    }
  };

  const handleReject = async () => {
    if (!currentImage) return;
    const reason = rejectionClass ? `needs_relabel_${rejectionClass}` : 'needs_relabel';
    const notes = rejectionNotes || `Rejected for relabeling. Human indicated ${rejectionClass || 'mask quality'} needs attention.`;
    setSaving(true);
    try {
      await api.review.reject(project.id, currentImage.id, reason, notes);
      removeCurrentImageFromQueue();
    } catch (err) {
      alert('Failed to reject: ' + err);
    } finally {
      setSaving(false);
    }
  };

  const updateAnnotationClass = (idx: number, className: string) => {
    setAnnotations((items) =>
      items.map((item, itemIdx) => (itemIdx === idx ? { ...item, class_name: className } : item)),
    );
  };

  const deleteAnnotation = (idx: number) => {
    setAnnotations((items) =>
      items.map((item, itemIdx) => (itemIdx === idx ? { ...item, deleted: true } : item)),
    );
  };

  const resetAnnotations = () => {
    if (currentImage) fetchAnnotations(currentImage.id);
  };

  const getClassColor = (className: string) => {
    const classDef = reviewClasses.find((item) => item.name === className);
    return classDef ? classDef.color : '#cbd5e1';
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background h-full text-white">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary"></div>
        <p className="mt-4 text-textMuted text-sm">Loading review queue...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background h-full text-white p-6">
        <AlertTriangle className="text-red-400 mb-4" size={40} />
        <h3 className="text-lg font-bold mb-2">Error Loading Review</h3>
        <p className="text-textMuted text-sm mb-6">{error}</p>
        <button onClick={fetchQueue} className="btn-primary">Retry</button>
      </div>
    );
  }

  if (queue.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background h-full text-white p-8">
        <Check className="text-emerald-400 mb-4" size={40} />
        <h2 className="text-xl font-bold mb-2">Review Queue Clear</h2>
        <p className="text-textMuted text-sm mb-8 text-center max-w-sm">
          All completed images have been reviewed or are waiting for AI processing.
        </p>
        <button onClick={fetchQueue} className="btn-primary text-sm flex items-center gap-2">
          <Play size={14} /> Refresh Queue
        </button>
      </div>
    );
  }

  const imageUrl = `http://localhost:8000/api/v1/projects/${project.id}/images/${currentImage.id}/file`;
  const maskUrl = `http://localhost:8000/api/v1/projects/${project.id}/images/${currentImage.id}/mask-overlay`;
  const viewBox = `0 0 ${currentImage.width || 1} ${currentImage.height || 1}`;

  return (
    <div className="flex flex-1 h-full overflow-hidden bg-background">
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <div className="h-16 border-b border-white/10 bg-[#111b2b] px-6 flex items-center justify-between shrink-0">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold text-primary bg-primary/10 border border-primary/20 rounded px-2 py-1">{currentIndex + 1} / {queue.length}</span>
              <span className="text-sm font-medium text-white truncate max-w-md">{currentImage.filename}</span>
            </div>
            <p className="text-[10px] text-textMuted mt-0.5">
              {visibleAnnotations.length} regions, {Math.round((currentImage.confidence || 0) * 100)}% average confidence
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={currentIndex === 0}
              onClick={() => setCurrentIndex(currentIndex - 1)}
              className="p-2 rounded-md hover:bg-white/5 disabled:opacity-30 text-textMuted hover:text-white"
              title="Previous"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              disabled={currentIndex >= queue.length - 1}
              onClick={() => setCurrentIndex(currentIndex + 1)}
              className="p-2 rounded-md hover:bg-white/5 disabled:opacity-30 text-textMuted hover:text-white"
              title="Next"
            >
              <ChevronRight size={16} />
            </button>
            <button
              onClick={() => setOverlayVisible(!overlayVisible)}
              className="p-2 rounded-md hover:bg-white/5 text-textMuted hover:text-white"
              title="Toggle mask overlay"
            >
              {overlayVisible ? <Eye size={16} /> : <EyeOff size={16} />}
            </button>
            <button
              onClick={resetAnnotations}
              className="p-2 rounded-md hover:bg-white/5 text-textMuted hover:text-white"
              title="Reset local edits"
            >
              <RotateCcw size={16} />
            </button>
          </div>
        </div>

        <div className="flex-1 relative bg-[#070b12] overflow-auto">
          <div className="min-h-full flex items-center justify-center p-6">
            <div className="relative max-w-full max-h-full border border-white/10 bg-black shadow-2xl shadow-black/40 rounded-md overflow-hidden">
              <img
                src={imageUrl}
                alt={currentImage.filename}
                className="block max-w-full max-h-[calc(100vh-14rem)] object-contain"
              />
              {overlayVisible && maskUrl && (
                <img
                  src={maskUrl}
                  alt="Mask Overlay"
                  className="absolute inset-0 w-full h-full object-fill pointer-events-none"
                />
              )}
              <svg
                className="absolute inset-0 w-full h-full pointer-events-auto"
                viewBox={viewBox}
                preserveAspectRatio="none"
                onMouseMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}
              >
                {visibleAnnotations.map((annotation, idx) => {
                  const points = annotation.segmentation.map((point) => point.join(',')).join(' ');
                  const color = getClassColor(annotation.class_name);
                  const isSelected = selectedRegion === idx;
                  const isHovered = hoveredRegion === idx;
                  return (
                    <polygon
                      key={`${annotation.id || idx}-${annotation.class_name}`}
                      points={points}
                      fill={isSelected ? `${color}66` : (isHovered ? `${color}44` : 'transparent')}
                      stroke={isSelected ? '#ffffff' : (isHovered ? '#ffffff' : 'transparent')}
                      strokeWidth={isSelected || isHovered ? (currentImage.width ? currentImage.width / 400 : 2) : 0}
                      className="cursor-pointer transition-all duration-150 outline-none"
                      onMouseEnter={() => setHoveredRegion(idx)}
                      onMouseLeave={() => setHoveredRegion(null)}
                      onClick={() => setSelectedRegion(idx)}
                    />
                  );
                })}
              </svg>
              
              {/* Floating Tooltip */}
              {hoveredRegion !== null && visibleAnnotations[hoveredRegion] && (
                <div
                  className="fixed z-50 pointer-events-none bg-black/90 text-white text-xs px-3 py-2 rounded shadow-lg border border-white/20 whitespace-nowrap backdrop-blur-sm"
                  style={{ left: mousePos.x + 15, top: mousePos.y + 15 }}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span 
                      className="w-2.5 h-2.5 rounded-full shadow-[0_0_4px_rgba(255,255,255,0.5)]" 
                      style={{ backgroundColor: getClassColor(visibleAnnotations[hoveredRegion].class_name) }} 
                    />
                    <span className="font-bold text-sm">{visibleAnnotations[hoveredRegion].class_name}</span>
                  </div>
                  <div className="text-textMuted text-[10px] flex justify-between gap-4">
                    <span>Confidence:</span>
                    <span className="font-mono">{visibleAnnotations[hoveredRegion].confidence ? Math.round((visibleAnnotations[hoveredRegion].confidence as number) * 100) + '%' : 'N/A'}</span>
                  </div>
                  <div className="text-textMuted text-[10px] flex justify-between gap-4">
                    <span>Points:</span>
                    <span className="font-mono">{visibleAnnotations[hoveredRegion].segmentation.length}</span>
                  </div>
                  <div className="text-emerald-400 text-[9px] mt-1.5 pt-1 border-t border-white/10 text-center">
                    Click to edit
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="border-t border-white/10 bg-[#111b2b] px-6 py-3 flex items-center gap-3 shrink-0">
          <input
            value={reviewNotes}
            onChange={(event) => setReviewNotes(event.target.value)}
            placeholder="Reviewer notes"
            className="flex-1 bg-[#0b1120] border border-white/10 rounded-md px-3 py-2 text-xs text-white outline-none focus:border-primary"
          />
          <button
            onClick={handleReject}
            disabled={saving}
            className="px-4 py-2 text-xs font-semibold text-red-300 bg-red-500/10 border border-red-500/20 rounded-md flex items-center gap-1.5 disabled:opacity-50 hover:bg-red-500/15"
          >
            <X size={14} /> Reject & Relabel
          </button>
          <button
            onClick={handleSaveCorrections}
            disabled={saving}
            className="px-4 py-2 text-xs font-semibold text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-md flex items-center gap-1.5 disabled:opacity-50 hover:bg-amber-500/15"
          >
            <Save size={14} /> Save Corrections
          </button>
          <button
            onClick={handleApprove}
            disabled={saving}
            className="px-5 py-2.5 rounded-md bg-emerald-500 hover:bg-emerald-600 text-white text-xs flex items-center gap-1.5 disabled:opacity-50"
          >
            <Check size={14} /> Approve
          </button>
        </div>
      </div>

      <div className="w-96 border-l border-white/10 bg-[#111b2b] flex flex-col h-full shrink-0 overflow-hidden">
        <div className="p-4 border-b border-white/10">
          <h3 className="font-semibold text-white text-sm">Manual Review</h3>
          <p className="text-[10px] text-textMuted mt-1">
            Pixel mask output is reviewed here before export or relabeling.
          </p>
        </div>

        <div className="p-3 border-b border-white/10">
          <h4 className="text-[10px] text-textMuted uppercase tracking-wider mb-2">Reject Feedback</h4>
          <div className="grid grid-cols-2 gap-2">
            <select
              value={rejectionClass}
              onChange={(event) => setRejectionClass(event.target.value)}
              className="bg-[#0b1120] border border-white/10 rounded-md px-2 py-2 text-xs text-white outline-none focus:border-primary"
            >
              {reviewClasses.map((classDef) => (
                <option key={classDef.id} value={classDef.name}>{classDef.name}</option>
              ))}
            </select>
            <input
              value={rejectionNotes}
              onChange={(event) => setRejectionNotes(event.target.value)}
              placeholder="What was missed?"
              className="bg-[#0b1120] border border-white/10 rounded-md px-2 py-2 text-xs text-white outline-none focus:border-primary"
            />
          </div>
        </div>

        <div className="p-3 border-b border-white/10">
          <h4 className="text-[10px] text-textMuted uppercase tracking-wider mb-2">Class Legend</h4>
          <div className="flex flex-wrap gap-1">
            {reviewClasses.map((classDef) => (
              <span
                key={classDef.id}
                className="text-[9px] px-1.5 py-0.5 rounded border border-white/10"
                style={{ borderLeftColor: classDef.color, borderLeftWidth: 3 }}
              >
                {classDef.name}
              </span>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
          {visibleAnnotations.length === 0 ? (
            <div className="text-xs text-textMuted text-center py-8">
              <AlertTriangle size={22} className="mx-auto mb-2 text-amber-400" />
              No regions detected
            </div>
          ) : (
            visibleAnnotations.map((annotation, idx) => {
              const color = getClassColor(annotation.class_name);
              return (
                <div
                  key={annotation.id || idx}
                  onClick={() => setSelectedRegion(idx)}
                  onMouseEnter={() => setHoveredRegion(idx)}
                  onMouseLeave={() => setHoveredRegion(null)}
                  className={`p-3 rounded-md border cursor-pointer transition-colors ${
                    selectedRegion === idx ? 'border-primary bg-primary/10' : (hoveredRegion === idx ? 'border-white/20 bg-white/[0.08]' : 'border-white/5 bg-white/[0.03] hover:bg-white/[0.06]')
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                    <select
                      value={annotation.class_name}
                      onChange={(event) => updateAnnotationClass(idx, event.target.value)}
                      onClick={(event) => event.stopPropagation()}
                      className="flex-1 bg-[#0b1120] border border-white/10 rounded-md px-2 py-1.5 text-xs text-white outline-none focus:border-primary"
                    >
                      {reviewClasses.map((classDef) => (
                        <option key={classDef.id} value={classDef.name}>{classDef.name}</option>
                      ))}
                    </select>
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        deleteAnnotation(idx);
                      }}
                      className="p-1.5 rounded-md text-red-300 hover:bg-red-500/10"
                      title="Remove region"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-textMuted">
                    <span>{annotation.segmentation.length} mask points</span>
                    <span>{annotation.confidence ? `${Math.round(annotation.confidence * 100)}%` : 'No score'}</span>
                  </div>
                  {annotation.bbox?.needs_attention && (
                    <p className="text-[10px] text-amber-300 mt-2">Low-confidence region needs careful review</p>
                  )}
                  {annotation.bbox?.alt_class && annotation.bbox.alt_class !== annotation.class_name && (
                    <p className="text-[10px] text-textMuted mt-1">Alternative: {annotation.bbox.alt_class}</p>
                  )}
                </div>
              );
            })
          )}
        </div>

        {currentImage?.reviewer_notes && (
          <div className="p-3 border-t border-white/10 bg-slate-950/40 max-h-40 overflow-y-auto">
            <pre className="text-[9px] text-textMuted whitespace-pre-wrap">{currentImage.reviewer_notes}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
