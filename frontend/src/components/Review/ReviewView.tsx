import { useState, useEffect } from 'react';
import { 
  Check, 
  X, 
  Undo, 
  Plus, 
  Trash2, 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  AlertTriangle,
  HelpCircle,
  Play,
  RotateCw
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

export default function ReviewView({ project }: ReviewViewProps) {
  const [queue, setQueue] = useState<any[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [annotations, setAnnotations] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Interaction States
  const [selectedAnnIdx, setSelectedAnnIdx] = useState<number | null>(null);
  const [hoveredAnnIdx, setHoveredAnnIdx] = useState<number | null>(null);
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [drawingPoints, setDrawingPoints] = useState<[number, number][]>([]);
  const [cursorPos, setCursorPos] = useState<[number, number] | null>(null);
  const [imgSize, setImgSize] = useState<{ width: number; height: number }>({ width: 1024, height: 1024 });
  const [isModified, setIsModified] = useState<boolean>(false);

  // Zoom & Pan States
  const [zoomScale, setZoomScale] = useState<number>(1);
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Rejection Modal States
  const [showRejectionModal, setShowRejectionModal] = useState<boolean>(false);
  const [rejectionReason, setRejectionReason] = useState<string>("poor_segmentation");
  const [rejectionNotes, setRejectionNotes] = useState<string>("");

  // Default drawing class
  const [newClassForDrawing, setNewClassForDrawing] = useState<string>("");

  const currentImage = queue[currentIndex];

  useEffect(() => {
    if (project?.classes && project.classes.length > 0) {
      setNewClassForDrawing(project.classes[0].name);
    }
  }, [project?.classes]);

  // Fetch queue on mount
  useEffect(() => {
    fetchQueue();
  }, [project?.id]);

  // Fetch annotations when current image changes
  useEffect(() => {
    if (currentImage) {
      fetchAnnotations(currentImage.id);
      // Reset interaction states
      setSelectedAnnIdx(null);
      setHoveredAnnIdx(null);
      setIsDrawing(false);
      setDrawingPoints([]);
      setIsModified(false);
      setZoomScale(1);
      setPanOffset({ x: 0, y: 0 });
    } else {
      setAnnotations([]);
    }
  }, [currentImage]);

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

  const fetchAnnotations = async (imageId: number) => {
    try {
      const data = await api.review.getAnnotations(project.id, imageId);
      const parsed = data.map((ann: any) => {
        let points: [number, number][] = [];
        if (ann.segmentation_json) {
          try {
            points = JSON.parse(ann.segmentation_json);
          } catch (e) {
            console.error('Failed to parse segmentation JSON', e);
          }
        }
        let bbox = {};
        if (ann.bbox_json) {
          try {
            bbox = JSON.parse(ann.bbox_json);
          } catch (e) {
            console.error('Failed to parse bbox JSON', e);
          }
        }
        return {
          ...ann,
          points,
          bbox
        };
      });
      setAnnotations(parsed);
    } catch (err) {
      console.error('Failed to fetch annotations', err);
    }
  };

  // Compute bounding box for a custom polygon
  const computeBbox = (points: [number, number][]) => {
    if (!points || points.length === 0) return [0, 0, 0, 0];
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const [x, y] of points) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
    return [
      Math.round(minX),
      Math.round(minY),
      Math.round(maxX - minX),
      Math.round(maxY - minY)
    ];
  };

  // Keyboard Shortcuts Handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore key events if focused in modal inputs or textareas
      if (
        document.activeElement?.tagName === 'INPUT' || 
        document.activeElement?.tagName === 'TEXTAREA' || 
        showRejectionModal
      ) {
        return;
      }

      // 1. Reclassify selected annotation using shortcut keys
      const matchedClass = project?.classes?.find(
        (c: any) => c.shortcut_key && c.shortcut_key.toLowerCase() === e.key.toLowerCase()
      );
      if (matchedClass) {
        if (selectedAnnIdx !== null) {
          updateAnnotationClass(selectedAnnIdx, matchedClass.name);
        } else if (isDrawing && drawingPoints.length >= 3) {
          finalizeDrawing(matchedClass.name);
        }
      }

      // 2. Delete selected annotation via Delete or Backspace
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedAnnIdx !== null) {
        deleteAnnotation(selectedAnnIdx);
      }

      // 3. Zoom Controls via + / - keys
      if (e.key === '=') {
        setZoomScale(prev => Math.min(prev + 0.25, 4));
      }
      if (e.key === '-') {
        setZoomScale(prev => Math.max(prev - 0.25, 1));
      }

      // 4. Ctrl + Enter to Quick Approve
      if (e.key === 'Enter' && e.ctrlKey) {
        handleApprove();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedAnnIdx, isDrawing, drawingPoints, project?.classes, annotations, showRejectionModal]);

  const updateAnnotationClass = (idx: number, newClass: string) => {
    const updated = [...annotations];
    updated[idx] = {
      ...updated[idx],
      class_name: newClass
    };
    setAnnotations(updated);
    setIsModified(true);
  };

  const deleteAnnotation = (idx: number) => {
    const updated = annotations.filter((_, i) => i !== idx);
    setAnnotations(updated);
    setSelectedAnnIdx(null);
    setIsModified(true);
  };

  // Canvas Drawing & Mapping Handlers
  const getSvgCoords = (e: React.MouseEvent<SVGSVGElement>): [number, number] => {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const svgX = (clickX / rect.width) * imgSize.width;
    const svgY = (clickY / rect.height) * imgSize.height;

    return [svgX, svgY];
  };

  const handleSvgClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDrawing) {
      setSelectedAnnIdx(null);
      return;
    }

    const [x, y] = getSvgCoords(e);

    // Click near starting point closes polygon
    if (drawingPoints.length >= 3) {
      const first = drawingPoints[0];
      const dist = Math.sqrt(Math.pow(x - first[0], 2) + Math.pow(y - first[1], 2));
      const threshold = imgSize.width * 0.015; // 1.5% of width threshold
      if (dist < threshold) {
        finalizeDrawing();
        return;
      }
    }

    setDrawingPoints([...drawingPoints, [x, y]]);
  };

  const handleSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDrawing) return;
    setCursorPos(getSvgCoords(e));
  };

  const finalizeDrawing = (customClass?: string) => {
    if (drawingPoints.length < 3) return;

    const finalClass = customClass || newClassForDrawing || project?.classes?.[0]?.name || 'unknown';
    const bbox = computeBbox(drawingPoints);

    const newAnn = {
      class_name: finalClass,
      model_source: 'Human Corrected',
      confidence: 1.0,
      points: drawingPoints,
      segmentation_json: JSON.stringify(drawingPoints),
      bbox_json: JSON.stringify({ bbox, area: 0 }),
      bbox: { bbox }
    };

    setAnnotations([...annotations, newAnn]);
    setIsModified(true);
    setIsDrawing(false);
    setDrawingPoints([]);
    setCursorPos(null);
  };

  const undoLastPoint = () => {
    if (drawingPoints.length > 0) {
      setDrawingPoints(drawingPoints.slice(0, -1));
    }
  };

  const cancelDrawing = () => {
    setIsDrawing(false);
    setDrawingPoints([]);
    setCursorPos(null);
  };

  // Zoom & Pan Mouse Events
  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoomScale > 1 && (e.button === 0 || e.button === 1)) {
      if (e.target === e.currentTarget || (e.target as SVGElement).tagName === 'svg') {
        setIsPanning(true);
        setPanStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
      }
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setPanOffset({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y
      });
    }
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  // Main Action Handlers
  const handleApprove = async () => {
    if (!currentImage) return;

    try {
      if (isModified) {
        // Send human corrections
        const formatted = annotations.map(ann => ({
          class_name: ann.class_name,
          segmentation: ann.points,
          bbox: ann.bbox
        }));
        await api.review.correct(project.id, currentImage.id, formatted);
      } else {
        // Approve directly
        await api.review.markViewed(project.id, currentImage.id);
      }
      advanceQueue();
    } catch (err) {
      alert('Failed to save decisions: ' + err);
    }
  };

  const handleReject = async () => {
    if (!currentImage) return;

    try {
      await api.review.reject(project.id, currentImage.id, rejectionReason, rejectionNotes);
      setShowRejectionModal(false);
      setRejectionNotes("");
      advanceQueue();
    } catch (err) {
      alert('Failed to reject image: ' + err);
    }
  };

  const advanceQueue = () => {
    if (currentIndex < queue.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      // Re-fetch queue to see if there are more
      fetchQueue();
    }
  };

  const handleForcePopulate = async () => {
    try {
      setLoading(true);
      await api.review.forcePopulate(project.id);
      await fetchQueue();
    } catch (err) {
      alert('Failed to populate queue: ' + err);
      setLoading(false);
    }
  };

  const getClassColor = (className: string) => {
    const cls = project?.classes?.find((c: any) => c.name === className);
    return cls ? cls.color : '#cbd5e1';
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background h-full text-white">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary"></div>
        <p className="mt-4 text-textMuted text-sm">Loading review assets...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background h-full text-white p-6">
        <AlertTriangle className="text-red-400 mb-4" size={40} />
        <h3 className="text-lg font-bold mb-2">Error Loading Review</h3>
        <p className="text-textMuted text-sm mb-6 text-center max-w-md">{error}</p>
        <button onClick={fetchQueue} className="btn-primary">Retry</button>
      </div>
    );
  }

  // Empty Queue View
  if (queue.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background h-full text-white p-8">
        <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center mb-6 text-emerald-400">
          <Check size={36} />
        </div>
        <h2 className="text-xl font-bold mb-2">Queue Completely Clear!</h2>
        <p className="text-textMuted text-sm mb-8 text-center max-w-sm">
          There are no images remaining in the review queue. All AI outputs have been successfully validated.
        </p>
        <div className="flex gap-4">
          <button onClick={fetchQueue} className="px-5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-white font-medium transition-all text-sm border border-white/10">
            Refresh Queue
          </button>
          <button onClick={handleForcePopulate} className="btn-primary text-sm flex items-center gap-2">
            <Play size={14} /> Repopulate Queue
          </button>
        </div>
      </div>
    );
  }

  const imageUrl = `http://localhost:8000/api/v1/projects/${project.id}/images/${currentImage.id}/file`;

  return (
    <div className="flex flex-1 h-full overflow-hidden bg-background relative select-none">
      
      {/* LEFT/CENTER AREA: Canvas & Toolbar */}
      <div className="flex-1 flex flex-col h-full bg-background relative overflow-hidden">
        
        {/* Sub-header controls */}
        <div className="h-14 border-b border-white/10 bg-surface/30 backdrop-blur-md px-6 flex items-center justify-between shrink-0 z-20">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-white">
              Image {currentIndex + 1} of {queue.length}
            </span>
            <span className="text-xs text-textMuted truncate max-w-xs" title={currentImage.filename}>
              {currentImage.filename}
            </span>
            {isModified && (
              <span className="text-[10px] bg-yellow-500/10 text-yellow-400 px-2 py-0.5 rounded border border-yellow-500/20 font-medium">
                Unsaved Changes
              </span>
            )}
          </div>

          {/* Interactive Action Toolbar */}
          <div className="flex items-center gap-4">
            
            {/* Draw Actions */}
            <div className="flex items-center gap-1 border-r border-white/10 pr-4">
              {!isDrawing ? (
                <button 
                  onClick={() => setIsDrawing(true)}
                  className="px-3 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-all text-xs font-medium flex items-center gap-1.5"
                >
                  <Plus size={14} /> Add Polygon
                </button>
              ) : (
                <div className="flex items-center gap-2">
                  <select
                    value={newClassForDrawing}
                    onChange={(e) => setNewClassForDrawing(e.target.value)}
                    className="bg-surface border border-white/10 rounded-lg text-xs py-1.5 px-2.5 text-white outline-none"
                  >
                    {project?.classes?.map((cls: any) => (
                      <option key={cls.id} value={cls.name}>{cls.name}</option>
                    ))}
                  </select>

                  <button 
                    onClick={undoLastPoint}
                    disabled={drawingPoints.length === 0}
                    className="p-1.5 rounded-lg bg-white/5 text-white hover:bg-white/10 transition-all disabled:opacity-40"
                    title="Undo Last Point"
                  >
                    <Undo size={14} />
                  </button>

                  <button 
                    onClick={finalizeDrawing}
                    disabled={drawingPoints.length < 3}
                    className="px-2.5 py-1.5 rounded-lg bg-emerald-500 text-white font-medium hover:bg-emerald-600 transition-all text-xs disabled:opacity-40"
                  >
                    Done
                  </button>

                  <button 
                    onClick={cancelDrawing}
                    className="px-2.5 py-1.5 rounded-lg bg-white/5 text-white hover:bg-white/10 transition-all text-xs"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>

            {/* Zoom / Reset controls */}
            <div className="flex items-center gap-1">
              <button 
                onClick={() => setZoomScale(prev => Math.min(prev + 0.25, 4))}
                className="p-1.5 rounded-lg hover:bg-white/5 text-textMuted hover:text-white transition-all"
                title="Zoom In"
              >
                <ZoomIn size={16} />
              </button>
              <button 
                onClick={() => setZoomScale(prev => Math.max(prev - 0.25, 1))}
                className="p-1.5 rounded-lg hover:bg-white/5 text-textMuted hover:text-white transition-all"
                title="Zoom Out"
              >
                <ZoomOut size={16} />
              </button>
              <button 
                onClick={() => { setZoomScale(1); setPanOffset({ x: 0, y: 0 }); }}
                className="p-1.5 rounded-lg hover:bg-white/5 text-textMuted hover:text-white transition-all"
                title="Reset Zoom & Pan"
              >
                <RotateCcw size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* Canvas Display Viewport */}
        <div className="flex-1 w-full relative overflow-hidden flex items-center justify-center p-6 bg-slate-950">
          <div 
            className="relative transition-transform duration-100 ease-out origin-center select-none"
            style={{
              transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomScale})`,
              transformOrigin: 'center center',
              cursor: isPanning ? 'grabbing' : zoomScale > 1 ? 'grab' : 'default'
            }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <img 
              src={imageUrl} 
              alt="Review annotation view" 
              className="max-w-full max-h-[70vh] object-contain pointer-events-none rounded shadow-2xl border border-white/5"
              onLoad={(e) => {
                const img = e.currentTarget;
                setImgSize({ width: img.naturalWidth, height: img.naturalHeight });
              }}
            />
            
            {/* SVG Interactive Overlay */}
            <svg 
              viewBox={`0 0 ${imgSize.width} ${imgSize.height}`} 
              className="absolute inset-0 w-full h-full"
              onClick={handleSvgClick}
              onMouseMove={handleSvgMouseMove}
            >
              {/* Render Polygons */}
              {annotations.map((ann, idx) => {
                if (!ann.points || ann.points.length === 0) return null;
                const color = getClassColor(ann.class_name);
                const isSelected = selectedAnnIdx === idx;
                const isHovered = hoveredAnnIdx === idx;
                
                return (
                  <polygon
                    key={ann.id || idx}
                    points={ann.points.map(([x, y]: [number, number]) => `${x},${y}`).join(' ')}
                    fill={color}
                    fillOpacity={isSelected ? 0.45 : isHovered ? 0.35 : 0.15}
                    stroke={color}
                    strokeWidth={isSelected ? 3 : isHovered ? 2 : 1.5}
                    className="cursor-pointer transition-all duration-150"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedAnnIdx(idx);
                    }}
                    onMouseEnter={() => setHoveredAnnIdx(idx)}
                    onMouseLeave={() => setHoveredAnnIdx(null)}
                  />
                );
              })}

              {/* Render Drawing Polygon */}
              {isDrawing && drawingPoints.length > 0 && (
                <>
                  <polyline
                    points={drawingPoints.map(([x, y]) => `${x},${y}`).join(' ')}
                    fill="none"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    strokeDasharray="4 4"
                  />
                  {cursorPos && (
                    <line
                      x1={drawingPoints[drawingPoints.length - 1][0]}
                      y1={drawingPoints[drawingPoints.length - 1][1]}
                      x2={cursorPos[0]}
                      y2={cursorPos[1]}
                      stroke="#3b82f6"
                      strokeWidth={1.5}
                      strokeDasharray="2 2"
                    />
                  )}
                  {drawingPoints.map(([x, y], idx) => (
                    <circle
                      key={idx}
                      cx={x}
                      cy={y}
                      r={idx === 0 ? 5 : 4}
                      fill={idx === 0 ? "#10b981" : "#3b82f6"}
                      stroke="white"
                      strokeWidth={1.5}
                      className="cursor-pointer hover:scale-125 transition-transform"
                      onClick={(e) => {
                        if (idx === 0 && drawingPoints.length >= 3) {
                          e.stopPropagation();
                          finalizeDrawing();
                        }
                      }}
                    />
                  ))}
                </>
              )}
            </svg>
          </div>
        </div>

        {/* Footer actions bar */}
        <div className="h-16 border-t border-white/10 bg-surface/30 backdrop-blur-md px-6 flex items-center justify-between shrink-0 z-20">
          <div className="text-xs text-textMuted">
            <span className="font-semibold text-white">Hotkeys:</span> Space/Click on polygon to select • Delete to remove • Shortcut key to reclassify • Ctrl+Enter to approve
          </div>

          <div className="flex gap-3">
            <button 
              onClick={() => setShowRejectionModal(true)}
              className="px-4 py-2 text-xs font-semibold text-red-400 hover:text-red-300 bg-red-500/10 hover:bg-red-500/25 border border-red-500/20 rounded-xl transition-all flex items-center gap-1.5"
            >
              <X size={14} /> Reject Image
            </button>
            <button 
              onClick={handleApprove}
              className="px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-medium transition-all text-xs flex items-center gap-1.5 shadow-lg shadow-emerald-500/20"
            >
              <Check size={14} /> {isModified ? 'Save & Approve' : 'Approve'}
            </button>
          </div>
        </div>
      </div>

      {/* RIGHT SIDEBAR: Annotation list */}
      <div className="w-80 border-l border-white/10 bg-surface/30 backdrop-blur-md flex flex-col h-full shrink-0 z-10 overflow-hidden">
        <div className="p-4 border-b border-white/10 shrink-0">
          <h3 className="font-semibold text-white text-sm">Detected Objects</h3>
          <p className="text-[10px] text-textMuted mt-1">
            Review model prediction polygons. Click list items or polygons to correct.
          </p>
        </div>

        {/* Polygons list */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
          {annotations.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center py-12">
              <HelpCircle className="text-white/10 mb-3" size={24} />
              <p className="text-xs text-textMuted font-medium">No objects detected</p>
              <p className="text-[10px] text-textMuted mt-1">Use 'Add Polygon' to segment objects manually.</p>
            </div>
          ) : (
            annotations.map((ann, idx) => {
              const isSelected = selectedAnnIdx === idx;
              const isHovered = hoveredAnnIdx === idx;
              const color = getClassColor(ann.class_name);
              
              return (
                <div
                  key={ann.id || idx}
                  onMouseEnter={() => setHoveredAnnIdx(idx)}
                  onMouseLeave={() => setHoveredAnnIdx(null)}
                  onClick={() => setSelectedAnnIdx(idx)}
                  className={`p-3 rounded-xl border transition-all cursor-pointer flex flex-col gap-2 ${
                    isSelected 
                      ? 'bg-primary/10 border-primary/45 shadow-lg shadow-primary/5' 
                      : isHovered 
                        ? 'bg-white/5 border-white/20' 
                        : 'bg-white/2 border-white/5'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span 
                        className="w-2.5 h-2.5 rounded-full" 
                        style={{ backgroundColor: color }}
                      />
                      <span className="text-xs font-semibold text-white capitalize">
                        {ann.class_name}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-textMuted">
                        {ann.confidence ? `${Math.round(ann.confidence * 100)}%` : 'Human'}
                      </span>
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteAnnotation(idx);
                        }}
                        className="p-1 hover:bg-red-500/20 rounded hover:text-red-400 text-textMuted transition-all"
                        title="Delete Annotation"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>

                  {/* Quick Class Selector details card */}
                  {isSelected && (
                    <div className="flex flex-col gap-2 mt-1 border-t border-white/5 pt-2">
                      <span className="text-[9px] text-textMuted font-medium">
                        Change Ontology Class
                      </span>
                      <div className="grid grid-cols-2 gap-1.5">
                        {project?.classes?.map((cls: any) => (
                          <button
                            key={cls.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              updateAnnotationClass(idx, cls.name);
                            }}
                            className={`px-2 py-1 rounded text-[10px] text-left truncate transition-colors border font-medium ${
                              ann.class_name === cls.name 
                                ? 'bg-white/10 text-white border-white/20' 
                                : 'bg-transparent text-textMuted border-white/5 hover:bg-white/5 hover:text-white'
                            }`}
                            style={{ borderLeftColor: cls.color, borderLeftWidth: 3 }}
                          >
                            {cls.name} {cls.shortcut_key && `(${cls.shortcut_key.toUpperCase()})`}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Global info card */}
        {currentImage && currentImage.reviewer_notes && (
          <div className="p-4 border-t border-white/10 bg-slate-950/40 shrink-0">
            <h4 className="text-[10px] text-textMuted font-semibold uppercase tracking-wider mb-2">
              Model Diagnostic Log
            </h4>
            <div className="bg-black/20 border border-white/5 rounded-lg p-2 max-h-32 overflow-y-auto">
              <pre className="text-[9px] text-textMuted whitespace-pre-wrap leading-relaxed">
                {currentImage.reviewer_notes}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* REJECTION DIALOG MODAL */}
      {showRejectionModal && (
        <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-white/10 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-in fade-in zoom-in duration-200">
            <div className="flex items-center gap-3 mb-4 text-red-400">
              <AlertTriangle size={24} />
              <h2 className="text-lg font-bold text-white">Reject Image</h2>
            </div>
            
            <p className="text-textMuted text-xs mb-6">
              Rejecting this image will discard current predictions and queue it for reprocessing/relabeling in the backend.
            </p>

            <div className="flex flex-col gap-4 mb-6">
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] text-textMuted font-semibold uppercase">
                  Rejection Reason
                </label>
                <select
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="bg-slate-950 border border-white/10 rounded-xl py-2.5 px-3.5 text-xs text-white outline-none"
                >
                  <option value="poor_segmentation">Poor AI Segmentation</option>
                  <option value="incorrect_classes">Incorrect Object Classes</option>
                  <option value="low_resolution">Low Resolution/Occluded</option>
                  <option value="duplicate_data">Duplicate/Corrupt File</option>
                  <option value="other">Other (Explain below)</option>
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] text-textMuted font-semibold uppercase">
                  Notes / Instructions for pipeline
                </label>
                <textarea
                  value={rejectionNotes}
                  onChange={(e) => setRejectionNotes(e.target.value)}
                  placeholder="Explain why this image is rejected..."
                  className="bg-slate-950 border border-white/10 rounded-xl py-2.5 px-3.5 text-xs text-white outline-none h-24 resize-none"
                />
              </div>
            </div>

            <div className="flex gap-3 justify-end">
              <button 
                onClick={() => setShowRejectionModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold hover:bg-white/5 text-white transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={handleReject}
                className="px-4 py-2.5 rounded-xl bg-red-500 hover:bg-red-600 text-white font-semibold transition-all text-xs shadow-lg shadow-red-500/20"
              >
                Reject & Re-Queue
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
