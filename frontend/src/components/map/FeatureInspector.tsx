import React from 'react';
import { Info, MapPin } from 'lucide-react';

interface FeatureInspectorProps {
  feature: any | null;
  onZoomFeature?: (feature: any) => void;
}

export const FeatureInspector: React.FC<FeatureInspectorProps> = ({ feature, onZoomFeature }) => {
  if (!feature) {
    return (
      <div className="w-72 bg-[#111827] border-l border-slate-800 flex flex-col h-full p-4 items-center justify-center text-slate-500 text-center">
        <Info size={32} className="mb-4 opacity-50" />
        <p className="text-sm">Select a map feature to inspect its details.</p>
      </div>
    );
  }

  const props = feature.properties || {};
  const isAI = props.source === 'ai_segformer' || props.source === 'ai_segformer_loveda';
  const isOSM = props.source === 'osm_layer' || props.source === 'openstreetmap' || props.osm_id;

  return (
    <div className="w-72 bg-[#111827] border-l border-slate-800 flex flex-col h-full overflow-y-auto">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <h3 className="font-semibold text-slate-100 flex items-center gap-2">
          <MapPin size={16} className="text-blue-400" /> Feature Details
        </h3>
      </div>
      
      <div className="p-4">
        {/* Badge */}
        <div className="mb-6 flex justify-between items-start">
          <span className={`inline-flex px-2.5 py-1 rounded text-xs font-bold tracking-wider ${
            isAI ? 'bg-blue-900/50 text-blue-400 border border-blue-800' :
            isOSM ? 'bg-purple-900/50 text-purple-400 border border-purple-800' :
            'bg-slate-800 text-slate-400 border border-slate-700'
          }`}>
            {isAI ? 'AI SEGMENTATION' : isOSM ? 'OPENSTREETMAP' : 'UNKNOWN SOURCE'}
          </span>
          {onZoomFeature && (
            <button 
              onClick={() => onZoomFeature(feature)}
              className="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded border border-slate-600 text-xs text-slate-300 transition-colors"
              title="Zoom to Feature"
            >
              Zoom
            </button>
          )}
        </div>

        <div className="space-y-4 text-sm">
          {/* Common attributes */}
          {props.class_name && (
            <div>
              <div className="text-slate-500 text-xs font-semibold mb-1 uppercase">Class</div>
              <div className="text-slate-200 capitalize">{props.class_name.replace('_', ' ')}</div>
            </div>
          )}
          
          {isOSM && props.category && (
            <div>
              <div className="text-slate-500 text-xs font-semibold mb-1 uppercase">Category</div>
              <div className="text-slate-200 capitalize">{props.category.replace('_', ' ')}</div>
            </div>
          )}

          {isOSM && props.name && (
            <div>
              <div className="text-slate-500 text-xs font-semibold mb-1 uppercase">Name</div>
              <div className="text-slate-200">{props.name}</div>
            </div>
          )}

          {/* AI specific */}
          {isAI && (
            <>
              <div>
                <div className="text-slate-500 text-xs font-semibold mb-1 uppercase">Source</div>
                <div className="text-slate-200">AI / LoveDA</div>
              </div>
              <div>
                <div className="text-slate-500 text-xs font-semibold mb-1 uppercase">Model</div>
                <div className="text-slate-200">{props.model_name || 'SegFormer B2'}</div>
              </div>
              <div>
                <div className="text-slate-500 text-xs font-semibold mb-1 uppercase">Confidence</div>
                <div className="text-slate-200">
                  {props.confidence ? `${(props.confidence * 100).toFixed(1)}%` : 'Confidence unavailable'}
                </div>
              </div>
              {props.area_sq_meters && (
                <div>
                  <div className="text-slate-500 text-xs font-semibold mb-1 uppercase">Area</div>
                  <div className="text-slate-200">
                    {props.area_sq_meters < 10000 
                      ? `${props.area_sq_meters.toFixed(1)} m²` 
                      : `${(props.area_sq_meters / 10000).toFixed(2)} ha`}
                  </div>
                </div>
              )}
            </>
          )}

          {/* OSM specific */}
          {isOSM && (
            <>
              <div>
                <div className="text-slate-500 text-xs font-semibold mb-1 uppercase">Source</div>
                <div className="text-slate-200">OpenStreetMap</div>
              </div>
              {props.osm_id && (
                <div>
                  <div className="text-slate-500 text-xs font-semibold mb-1 uppercase">OSM ID</div>
                  <div className="text-slate-200">{props.osm_id}</div>
                </div>
              )}
              {props.tags && Object.keys(props.tags).length > 0 && (
                <div>
                  <div className="text-slate-500 text-xs font-semibold mb-1 uppercase">Tags</div>
                  <div className="bg-slate-900 rounded p-2 text-xs overflow-x-auto">
                    <pre className="text-slate-300">{JSON.stringify(props.tags, null, 2)}</pre>
                  </div>
                </div>
              )}
              {props.retrieved_at && (
                <div>
                  <div className="text-slate-500 text-xs font-semibold mb-1 uppercase">Retrieved At</div>
                  <div className="text-slate-200">{new Date(props.retrieved_at).toLocaleString()}</div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
