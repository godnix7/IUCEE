import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
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
  Keyboard
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
  model_source?: string;
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
  const [showKeyboardHints, setShowKeyboardHints] = useState(false);

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

  // Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Avoid if typing in input
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA' || document.activeElement?.tagName === 'SELECT') return;

      const key = parseInt(e.key);
      if (!isNaN(key) && key >= 1 && key <= 9) {
        const classIndex = key - 1;
        if (classIndex < reviewClasses.length && selectedRegion !== null) {
          updateAnnotationClass(selectedRegion, reviewClasses[classIndex].name);
        }
      }
      
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedRegion !== null) {
          deleteAnnotation(selectedRegion);
          setSelectedRegion(null);
        }
      }

      if (e.key === 'ArrowLeft') {
        if (currentIndex > 0) setCurrentIndex(currentIndex - 1);
      }
      if (e.key === 'ArrowRight') {
        if (currentIndex < queue.length - 1) setCurrentIndex(currentIndex + 1);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedRegion, reviewClasses, currentIndex, queue.length]);

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
      model_source: annotation.model_source,
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
        <p className="mt-4 text-textMuted text-sm font-medium">Loading review queue...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background h-full text-white p-6">
        <AlertTriangle className="text-red-400 mb-4" size={48} />
        <h3 className="text-xl font-bold mb-2 text-textMain">Error Loading Review</h3>
        <p className="text-textMuted text-sm mb-6">{error}</p>
        <button onClick={fetchQueue} className="btn-primary">Retry</button>
      </div>
    );
  }

  if (queue.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background h-full text-white p-8">
        <Check className="text-emerald-400 mb-6 drop-shadow-[0_0_15px_rgba(52,211,153,0.5)]" size={64} />
        <h2 className="text-2xl font-bold mb-3 text-textMain">Review Queue Clear</h2>
        <p className="text-textMuted text-base mb-8 text-center max-w-sm">
          All completed images have been reviewed or are waiting for AI processing.
        </p>
        <button onClick={fetchQueue} className="btn-primary text-sm flex items-center gap-2 px-6 py-3">
          <Play size={18} /> Refresh Queue
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
        {/* Top Header */}
        <div className="h-16 border-b border-white/5 bg-surface/90 backdrop-blur-md px-6 flex items-center justify-between shrink-0 shadow-sm z-20">
          <div className="min-w-0">
            <div className="flex items-center gap-3 mb-1">
              <span className="text-xs font-bold text-primary bg-primary/10 border border-primary/20 rounded px-2.5 py-1 shadow-inner">{currentIndex + 1} / {queue.length}</span>
              <span className="text-sm font-semibold text-textMain truncate max-w-md">{currentImage.filename}</span>
            </div>
            <p className="text-[11px] text-textMuted">
              <span className="text-white font-medium">{visibleAnnotations.length}</span> regions • <span className="text-white font-medium">{Math.round((currentImage.confidence || 0) * 100)}%</span> avg confidence
            </p>
          </div>
          <div className="flex items-center gap-1 bg-black/20 p-1 rounded-lg border border-white/5">
            <button
              disabled={currentIndex === 0}
              onClick={() => setCurrentIndex(currentIndex - 1)}
              className="p-2 rounded-md hover:bg-white/10 disabled:opacity-30 text-textMuted hover:text-white transition-colors"
              title="Previous (Left Arrow)"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              disabled={currentIndex >= queue.length - 1}
              onClick={() => setCurrentIndex(currentIndex + 1)}
              className="p-2 rounded-md hover:bg-white/10 disabled:opacity-30 text-textMuted hover:text-white transition-colors"
              title="Next (Right Arrow)"
            >
              <ChevronRight size={18} />
            </button>
            <div className="w-px h-5 bg-white/10 mx-1"></div>
            <button
              onClick={() => setOverlayVisible(!overlayVisible)}
              className={`p-2 rounded-md transition-colors ${overlayVisible ? 'bg-primary/20 text-primary' : 'hover:bg-white/10 text-textMuted hover:text-white'}`}
              title="Toggle mask overlay"
            >
              {overlayVisible ? <Eye size={18} /> : <EyeOff size={18} />}
            </button>
            <button
              onClick={resetAnnotations}
              className="p-2 rounded-md hover:bg-white/10 text-textMuted hover:text-white transition-colors"
              title="Reset local edits"
            >
              <RotateCcw size={18} />
            </button>
            <button
              onClick={() => setShowKeyboardHints(!showKeyboardHints)}
              className={`p-2 rounded-md transition-colors ${showKeyboardHints ? 'bg-secondary/20 text-secondary' : 'hover:bg-white/10 text-textMuted hover:text-white'}`}
              title="Keyboard Shortcuts"
            >
              <Keyboard size={18} />
            </button>
          </div>
        </div>

        {/* Canvas Area */}
        <div className="flex-1 relative bg-[#040405] overflow-auto radial-gradient-background">
          <div className="min-h-full flex items-center justify-center p-8">
            <div className="relative max-w-full max-h-full border border-white/10 bg-black shadow-[0_0_50px_rgba(0,0,0,0.8)] rounded-lg overflow-hidden transition-all">
              <img
                src={imageUrl}
                alt={currentImage.filename}
                className="block max-w-full max-h-[calc(100vh-16rem)] object-contain"
              />
              {overlayVisible && maskUrl && (
                <img
                  src={maskUrl}
                  alt="Mask Overlay"
                  className={`absolute inset-0 w-full h-full object-fill pointer-events-none transition-opacity duration-300 ${selectedRegion !== null ? 'opacity-30' : 'opacity-100'}`}
                />
              )}
              <svg
                className="absolute inset-0 w-full h-full pointer-events-auto"
                viewBox={viewBox}
                preserveAspectRatio="none"
                onMouseMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}
                onClick={() => setSelectedRegion(null)}
              >
                {visibleAnnotations.map((annotation, idx) => {
                  const points = annotation.segmentation.map((point) => point.join(',')).join(' ');
                  const color = getClassColor(annotation.class_name);
                  const isSelected = selectedRegion === idx;
                  const isHovered = hoveredRegion === idx;
                  
                  // Focus mode: if something is selected, fade out the others heavily
                  const isFaded = selectedRegion !== null && !isSelected;

                  return (
                    <polygon
                      key={`${annotation.id || idx}-${annotation.class_name}`}
                      points={points}
                      fill={isSelected ? `${color}77` : (isHovered ? `${color}55` : (isFaded ? `${color}11` : 'transparent'))}
                      stroke={isSelected ? '#ffffff' : (isHovered ? '#ffffff' : (isFaded ? 'transparent' : 'transparent'))}
                      strokeWidth={isSelected ? (currentImage.width ? currentImage.width / 200 : 3) : (isHovered ? (currentImage.width ? currentImage.width / 400 : 2) : 0)}
                      strokeDasharray={isSelected ? `${currentImage.width ? currentImage.width / 100 : 5}, ${currentImage.width ? currentImage.width / 100 : 5}` : 'none'}
                      className={`cursor-pointer transition-all duration-200 outline-none ${isSelected ? 'animate-[dash_1s_linear_infinite]' : ''}`}
                      onMouseEnter={() => setHoveredRegion(idx)}
                      onMouseLeave={() => setHoveredRegion(null)}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedRegion(idx);
                      }}
                    />
                  );
                })}
              </svg>
              
              {/* Floating Tooltip / Context Menu */}
              {hoveredRegion !== null && visibleAnnotations[hoveredRegion] && (
                <div
                  className="fixed z-50 pointer-events-none bg-surface/95 text-textMain text-xs px-4 py-3 rounded-xl shadow-2xl border border-white/10 whitespace-nowrap backdrop-blur-md"
                  style={{ left: mousePos.x + 15, top: mousePos.y + 15 }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span 
                      className="w-3 h-3 rounded-full shadow-[0_0_8px_rgba(255,255,255,0.4)]" 
                      style={{ backgroundColor: getClassColor(visibleAnnotations[hoveredRegion].class_name) }} 
                    />
                    <span className="font-bold text-sm">{visibleAnnotations[hoveredRegion].class_name}</span>
                  </div>
                  <div className="text-textMuted text-[11px] flex justify-between gap-6 mb-1">
                    <span>Confidence:</span>
                    <span className="font-mono text-white">{visibleAnnotations[hoveredRegion].confidence ? Math.round((visibleAnnotations[hoveredRegion].confidence as number) * 100) + '%' : 'N/A'}</span>
                  </div>
                  <div className="text-textMuted text-[11px] flex justify-between gap-6 mb-1">
                    <span>Model:</span>
                    <span className="font-mono text-white">{visibleAnnotations[hoveredRegion].model_source || 'Unknown'}</span>
                  </div>
                  <div className="text-textMuted text-[11px] flex justify-between gap-6">
                    <span>Points:</span>
                    <span className="font-mono text-white">{visibleAnnotations[hoveredRegion].segmentation.length}</span>
                  </div>
                  
                  {selectedRegion === hoveredRegion ? (
                    <div className="text-accent font-semibold text-[10px] mt-2 pt-2 border-t border-white/5 text-center">
                      Selected - Press 1-9 to reclassify
                    </div>
                  ) : (
                    <div className="text-primary font-medium text-[10px] mt-2 pt-2 border-t border-white/5 text-center">
                      Click to select & edit
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Bottom Action Bar */}
        <div className="border-t border-white/5 bg-surface px-6 py-4 flex items-center gap-4 shrink-0 shadow-xl z-20">
          <input
            value={reviewNotes}
            onChange={(event) => setReviewNotes(event.target.value)}
            placeholder="Add reviewer notes..."
            className="flex-1 bg-black/30 border border-white/10 rounded-lg px-4 py-2.5 text-sm text-textMain outline-none focus:border-primary transition-colors"
          />
          <button
            onClick={handleReject}
            disabled={saving}
            className="px-5 py-2.5 text-sm font-semibold text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 disabled:opacity-50 hover:bg-red-500/20 hover:border-red-500/40 transition-all"
          >
            <X size={16} /> Reject & Relabel
          </button>
          <button
            onClick={handleSaveCorrections}
            disabled={saving}
            className="px-5 py-2.5 text-sm font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-center gap-2 disabled:opacity-50 hover:bg-amber-500/20 hover:border-amber-500/40 transition-all"
          >
            <Save size={16} /> Save Corrections
          </button>
          <button
            onClick={handleApprove}
            disabled={saving}
            className="px-8 py-2.5 rounded-lg bg-primary hover:bg-indigo-500 text-white text-sm font-bold flex items-center gap-2 disabled:opacity-50 shadow-[0_0_15px_rgba(99,102,241,0.4)] transition-all"
          >
            <Check size={16} /> Approve
          </button>
        </div>
      </div>

      {/* Right Sidebar */}
      <div className="w-80 border-l border-white/5 bg-surface flex flex-col h-full shrink-0 overflow-hidden z-20">
        <div className="p-5 border-b border-white/5 bg-black/20">
          <h3 className="font-bold text-textMain text-sm mb-1 flex items-center gap-2">
            <Activity size={16} className="text-primary"/> Manual Review
          </h3>
          <p className="text-xs text-textMuted">
            Review and correct AI polygon predictions before saving.
          </p>
        </div>

        {showKeyboardHints && (
          <div className="p-4 border-b border-white/5 bg-primary/5 animate-in slide-in-from-top-2">
            <h4 className="text-[10px] text-primary uppercase tracking-wider mb-3 font-bold">Keyboard Shortcuts</h4>
            <div className="grid grid-cols-2 gap-2">
              {reviewClasses.slice(0, 9).map((classDef, idx) => (
                <div key={classDef.id} className="flex items-center gap-2 text-xs">
                  <span className="bg-black/50 border border-white/10 rounded w-5 h-5 flex items-center justify-center font-mono text-[10px] text-textMuted shadow-inner">{idx + 1}</span>
                  <span className="truncate text-textMain" style={{ color: classDef.color }}>{classDef.name}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-white/5 flex gap-4 text-xs text-textMuted">
              <span className="flex items-center gap-1"><span className="bg-black/50 px-1 border border-white/10 rounded font-mono">Del</span> Delete</span>
              <span className="flex items-center gap-1"><span className="bg-black/50 px-1 border border-white/10 rounded font-mono">←</span><span className="bg-black/50 px-1 border border-white/10 rounded font-mono">→</span> Nav</span>
            </div>
          </div>
        )}

        <div className="p-4 border-b border-white/5">
          <h4 className="text-[10px] text-textMuted uppercase tracking-wider mb-3 font-semibold">Reject Context</h4>
          <div className="space-y-3">
            <select
              value={rejectionClass}
              onChange={(event) => setRejectionClass(event.target.value)}
              className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-xs text-textMain outline-none focus:border-red-500/50 transition-colors"
            >
              {reviewClasses.map((classDef) => (
                <option key={classDef.id} value={classDef.name}>{classDef.name}</option>
              ))}
            </select>
            <input
              value={rejectionNotes}
              onChange={(event) => setRejectionNotes(event.target.value)}
              placeholder="What was missed or wrong?"
              className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-xs text-textMain outline-none focus:border-red-500/50 transition-colors"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 custom-scrollbar">
          <div className="flex items-center justify-between mb-1">
            <h4 className="text-[10px] text-textMuted uppercase tracking-wider font-semibold">Detected Regions</h4>
            <span className="text-[10px] font-mono bg-white/10 px-2 py-0.5 rounded-full text-textMain">{visibleAnnotations.length}</span>
          </div>
          
          {visibleAnnotations.length === 0 ? (
            <div className="text-xs text-textMuted text-center py-10 bg-black/20 rounded-xl border border-white/5 border-dashed">
              <AlertTriangle size={24} className="mx-auto mb-3 text-amber-500/50" />
              No regions detected
            </div>
          ) : (
            visibleAnnotations.map((annotation, idx) => {
              const color = getClassColor(annotation.class_name);
              const isSelected = selectedRegion === idx;
              
              return (
                <div
                  key={annotation.id || idx}
                  onClick={() => setSelectedRegion(idx)}
                  onMouseEnter={() => setHoveredRegion(idx)}
                  onMouseLeave={() => setHoveredRegion(null)}
                  className={`p-3 rounded-xl border cursor-pointer transition-all duration-200 group ${
                    isSelected ? 'border-primary bg-primary/10 shadow-[0_0_15px_rgba(99,102,241,0.15)] scale-[1.02]' : (hoveredRegion === idx ? 'border-white/20 bg-white/[0.04]' : 'border-white/5 bg-black/20 hover:bg-white/[0.02]')
                  }`}
                >
                  <div className="flex items-center gap-3 mb-2.5">
                    <span className={`w-3 h-3 rounded-full shrink-0 shadow-[0_0_5px_rgba(255,255,255,0.3)] ${isSelected ? 'animate-pulse' : ''}`} style={{ backgroundColor: color }} />
                    <select
                      value={annotation.class_name}
                      onChange={(event) => updateAnnotationClass(idx, event.target.value)}
                      onClick={(event) => event.stopPropagation()}
                      className="flex-1 bg-black/50 border border-white/5 rounded-md px-2 py-1.5 text-xs text-textMain font-medium outline-none focus:border-primary transition-colors"
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
                      className={`p-1.5 rounded-md transition-colors ${isSelected ? 'text-red-400 hover:bg-red-500/20' : 'text-textMuted hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100'}`}
                      title="Remove region"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-textMuted px-1 mt-1 border-t border-white/5 pt-1.5">
                    <span className="flex items-center gap-1"><Activity size={12}/> Model:</span>
                    <span className="font-mono text-xs">{annotation.model_source || 'Unknown'}</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-textMuted px-1 mt-1">
                    <span className="flex items-center gap-1"><Activity size={12}/> {annotation.segmentation.length} pts</span>
                    <span className="font-mono bg-black/40 px-1.5 rounded">{annotation.confidence ? `${Math.round(annotation.confidence * 100)}%` : 'N/A'}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {currentImage?.reviewer_notes && (
          <div className="p-4 border-t border-white/5 bg-amber-500/5">
            <h4 className="text-[10px] text-amber-500/80 uppercase tracking-wider mb-2 font-semibold">Previous Notes</h4>
            <pre className="text-[11px] text-amber-200/70 whitespace-pre-wrap font-sans">{currentImage.reviewer_notes}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
