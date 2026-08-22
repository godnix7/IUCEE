import React from 'react';
import { Info } from 'lucide-react';
import { CLASS_LABELS } from '../map/MapLegend';
import type { DetectionReview, ImageryAnalysis } from '../../types';
import type { ReviewFeature } from './DetectionReviewPanel';

interface Props {
  feature: ReviewFeature | null;
  review: DetectionReview | null;
  analysis: ImageryAnalysis;
}

const Row: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="flex justify-between gap-3 py-0.5">
    <span className="text-slate-500">{label}</span>
    <span className="text-slate-200 text-right truncate">{value}</span>
  </div>
);

export const DetectionInspector: React.FC<Props> = ({ feature, review, analysis }) => {
  if (!feature) {
    return (
      <div className="px-4 py-2 text-[11px] text-slate-500 flex items-center gap-2">
        <Info size={12} /> Select a detection to inspect its metadata.
      </div>
    );
  }
  const crs = analysis.original_crs || (analysis.normalized_crs ?? null);
  const area = feature.area_sq_meters && feature.area_sq_meters > 0
    ? `${feature.area_sq_meters.toLocaleString()} m²`
    : 'n/a (pixel space)';

  return (
    <div className="px-4 py-2.5 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-0.5 text-[11px]">
      <Row label="Detection class" value={CLASS_LABELS[feature.class_name] || feature.class_name} />
      <Row label="Source" value={feature.source || '—'} />
      <Row label="Model" value={feature.model_name || '—'} />
      <Row label="Model version" value={feature.model_version || '—'} />
      <Row label="Confidence" value={typeof feature.confidence === 'number' ? `${(feature.confidence * 100).toFixed(1)}%` : '—'} />
      <Row label="Area" value={area} />
      <Row label="Feature count" value={feature.feature_count ?? '—'} />
      <Row label="Feature ID" value={feature.id} />
      <Row label="Analysis ID" value={analysis.id} />
      <Row label="CRS / SRID" value={crs || 'non-georeferenced'} />

      {review && (
        <>
          <div className="md:col-span-2 mt-1.5 pt-1.5 border-t border-slate-800 text-slate-400 font-semibold">Review provenance</div>
          <Row label="Original AI label" value={CLASS_LABELS[review.original_label] || review.original_label} />
          <Row label="Corrected label" value={review.corrected_label ? (CLASS_LABELS[review.corrected_label] || review.corrected_label) : '—'} />
          <Row label="Review status" value={review.status} />
          <Row label="Review source" value={review.review_source || 'human_review'} />
          <Row label="Reviewer" value={review.reviewer_email || review.reviewer_id || '—'} />
          <Row label="Reviewed at" value={review.reviewed_at ? new Date(review.reviewed_at).toLocaleString() : '—'} />
          {review.comment && <div className="md:col-span-2 text-slate-400 italic mt-0.5">“{review.comment}”</div>}
        </>
      )}
    </div>
  );
};
