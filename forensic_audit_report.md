# UrbanSense — Forensic Audit & Runtime Verification Report

**Date:** 2026-08-18
**Scope:** "No infrastructure detection is happening" — full runtime verification of the AI inference pipeline.
**Verdict:** The inference pipeline is **functionally correct**. The failure is caused by **input imagery that does not match the model's training domain**, compounded by **broken handling of non‑georeferenced images** (NaN areas, off‑world coordinates).

---

## TL;DR

| Question | Answer |
|---|---|
| Is the model loading / preprocessing broken? | **No.** Verified correct (see Steps 2–4). |
| Is the class mapping wrong (as the handoff assumed)? | **No.** The model has **8 classes**; `ai_service.py` maps them correctly. `URBANSENSE_REMEDIATION.md` documents them **wrong** (7-class assumption). |
| Is the UTM `zone=114` crash fixed? | **Yes**, patch is live in the container; jobs no longer crash. |
| Why does the user see "no detection"? | **Wrong-domain imagery** (oblique VisDrone drone photos + a 300 m/px satellite tile) → model detects **0% road**, mislabels most pixels as *Background*; and non‑georeferenced JPGs yield **NaN areas** + **off‑world map placement**. |

---

## Active Pipeline (confirmed by trace)

```
POST /api/v1/inference/upload
  → ImageryAnalysis + ProcessingJob rows
  → Celery: process_imagery_analysis (workers/tasks.py)
      → GeoService.read_raster_metadata (transform, crs)
      → AIService.run_inference(path, transform, meta)      ← THE detection code
      → SpatialFeature persistence (PostGIS)
      → OSMService enrichment
      → AnalyticsService.calculate_analytics
```

> Note: `services/processing_service.py` and `tiling_service.py` reference ORM models
> (`Image`, `Annotation`, `ProcessingQueue`) that **do not exist** in `models.py`. That is
> **legacy/dead code** and is NOT part of the live path. The live detector is `AIService.run_inference`.

---

## Step 2 — Model configuration (VERIFIED)

Loaded `wu-pr-gw/segformer-b2-finetuned-with-LoveDA` offline from the container cache:

```
NUM CLASSES: 8
id2label: {0:'Ignore', 1:'Background', 2:'Building', 3:'Road',
           4:'Water', 5:'Barren', 6:'Forest', 7:'Agricultural'}
```

- `ai_service.py` `LOVEDA_TO_URBANSENSE = {2:building,3:road,4:water,5:barren,6:forest,7:agri}` → **CORRECT**.
- **`URBANSENSE_REMEDIATION.md` is WRONG** — it lists a 7-class 0-indexed table (`Building(1), Road(2)…`).
  Anyone "fixing" the code to match that doc would **introduce** an off-by-one bug. Do not.
- Model training domain: **LoveDA = 0.3 m/px NADIR (top-down) aerial imagery**.

## Steps 3–4 — Image prep & preprocessing (VERIFIED CLEAN)

| Check | Result |
|---|---|
| Tile array | `(512,512,3)`, `uint8`, min 0 / max 255 — correct RGB |
| Processor output | min **-2.118**, max **2.640** — correct ImageNet normalization |
| Double normalization? | **No.** Range is the expected `[-2.1, 2.6]`, not a collapsed `~[-0.01,0.01]` |
| `do_reduce_labels` | `False` (labels not shifted) |

Preprocessing is textbook-correct. Not the problem.

---

## Steps 5–6 — Raw model output on REAL inputs

### Input A — user's actual data: `VisDrone .../0000002_00448_d_0000015.jpg`

This is an **oblique, low-altitude street-level drone photo** (building seen from the side, cars,
crowds with umbrellas, a plaza). It is **not** nadir aerial imagery.

Raw argmax histogram (518,400 px):

| id | class | % pixels | mean conf |
|---|---|---:|---:|
| 1 | Background | **67.74%** | 0.932 |
| 2 | Building | 25.73% | 0.896 |
| 6 | Forest | 5.88% | 0.832 |
| 0 | Ignore | 0.58% | 0.125 |
| 4 | Water | 0.07% | 0.593 |
| **3** | **Road** | **0.00%** | — |

- **Road = 0%** — the model recognizes no road at all, despite an obvious car-filled street.
- 68% dumped into *Background* (unmapped → discarded). The building blob bleeds off the roof into the plaza.
- **High confidence, wrong answer** = classic out-of-domain overconfidence.

### Input B — `RGB.byte.tif` (the "working" example in the DB)

Metadata shows **300 m/pixel** (rasterio's sample Landsat coastal scene) — ~1000× coarser than LoveDA.

| id | class | % pixels |
|---|---|---:|
| 4 | Water | 55.13% |
| 0 | Ignore (rotation border) | 32.00% |
| 1 | Background | 9.05% |
| 5 | Barren | 3.82% |

Plausible water/land split → the "2 features" seen in the DB. No buildings/roads because none are
visible at 300 m/px. **Also wrong-domain**, just fails more gracefully.

**Neither input is anywhere near the model's 0.3 m/px nadir training domain.**

Colored-mask visualizations saved (orig | mask | overlay): `drone_mask.png`, `nadir_mask.png`.

---

## Additional confirmed bugs (non-georeferenced path)

End-to-end run of the drone JPG through the live pipeline (post-patch):

```
crs=None  transform=Affine(1,0,0, 0,1,0)  (identity)
building     area=NaN m2  n=2  centroid=(500.79, 118.53)
water        area=NaN m2  n=1  centroid=(942.61,   6.18)
tree_cover   area=NaN m2  n=3  centroid=(846.85, 392.27)
```

1. **`area = NaN` for every feature.** Reproduced root cause: a JPG has no CRS → identity transform →
   polygons are in **pixel coordinates** → `ai_service.py` labels them `EPSG:4326` (default at line ~167) →
   pixel value 500 is treated as **500° longitude** → `choose_metric_crs` picks a bogus UTM zone (was the
   `zone=114` crash; now clamped to 60) → reprojecting impossible coordinates returns **NaN**.
   This NaN then propagates into `SpatialAnalytics` area sums and the infrastructure score.

2. **Off-world map placement.** Centroids like `(500°, 392°)` are invalid lon/lat → features render near
   null-island / nowhere. This is the real cause of the "map shows the wrong place" complaint.

3. **Hardcoded Bangalore fallback bounds.** `tasks.py:86`
   `bounds = tuple(analysis.bounds or [77.58, 12.96, 77.60, 12.98])` — for any non-georeferenced image,
   OSM enrichment is fetched for **Bangalore** regardless of the actual scene. Data-integrity bug.

---

## Root Cause

> **The detector works. The data is wrong.**
>
> `segformer-b2-finetuned-with-LoveDA` is a semantic-segmentation model trained on **0.3 m/px nadir
> aerial imagery**. The project is feeding it **oblique street-level drone footage (VisDrone)** and a
> **300 m/px satellite tile** — both far outside its domain. On oblique imagery it detects **zero roads**
> and mislabels ~68% as background. Separately, non-georeferenced JPG/PNG inputs produce **NaN areas and
> off-world geometry**, so even the features it does find are unusable downstream.

---

## Recommendations (in priority order)

1. **Fix the input, not the model.** For LoveDA-SegFormer to detect roads/buildings you must feed
   **nadir orthorectified imagery at ~0.3–1 m/px** (drone *orthomosaics*, or high-res satellite tiles).
   VisDrone is an **oblique object-detection benchmark** (cars/pedestrians) — semantically incompatible
   with top-down infrastructure segmentation.
   - If oblique drone footage must be supported, switch that path to a **detection** model (e.g. YOLO
     trained on VisDrone) — a different task than pixel segmentation.

2. **Stop silently corrupting non-georeferenced uploads.** Either:
   - **Reject** JPG/PNG without a world file / CRS with a clear error, **or**
   - Treat them explicitly as **pixel-space only**: skip CRS reprojection & area-in-m², and store
     pixel geometry with `crs=null` (never mislabel pixels as `EPSG:4326`).
   Guard against `NaN`: if projected area is non-finite, drop the feature and log it.

3. **Remove the hardcoded Bangalore OSM fallback** (`tasks.py:86`). Skip OSM enrichment when true bounds
   are unavailable instead of querying a default city.

4. **Correct `URBANSENSE_REMEDIATION.md`** class table to the verified 8-class LoveDA mapping to prevent a
   future "fix" from breaking the correct code.

5. (Housekeeping) Delete or quarantine the dead `processing_service.py` / `tiling_service.py` legacy path
   to stop it from misleading future audits.

---

## Evidence / repro artifacts

- `forensic_diag.py` — offline diagnostic (tiling identical to `AIService`), emits Steps 3–6.
- `drone_mask.png`, `nadir_mask.png` — orig | predicted-mask | overlay.
- Model config verified offline against the container's HF cache (no re-download).

---

# IMPLEMENTED SOLUTION — Dual-Mode Analysis (segmentation **or** detection)

Decision (user): support **both** modes behind a UI toggle rather than replacing the model.

## What was built

**Backend**
- `ImageryAnalysis.analysis_mode` = `'segmentation'` (default) | `'detection'`
  (+ `detection_overlay_key`, `detection_summary` columns). Live `ALTER TABLE` applied and
  Alembic migration `a1b2c3d4e5f6` added + stamped.
- New `app/services/detection_service.py` — COCO object detection via **`hustvl/yolos-tiny`**,
  loaded through the already-installed `transformers` (no new pip deps, no Docker rebuild).
  Classes filtered to `person, bicycle, car, motorcycle, bus, truck, train, boat`. Aggregates
  detections per class into a `SpatialFeature` (MultiPolygon of boxes) + writes an annotated
  overlay image to MinIO. Georeferenced input → world-coord boxes + metric area; non-georef →
  clean pixel-space geometry, area 0 (never NaN).
- `workers/tasks.py` routes on `analysis_mode`. Detection mode uploads the overlay, stores the
  summary, and skips land-cover OSM/analytics.
- `api/v1/inference.py` `/upload` accepts `analysis_mode`; new `GET /inference/{id}/detection-overlay`
  streams the annotated image.
- **Bug fixes shipped alongside:**
  - `ai_service.py` no longer reprojects non-georeferenced pixel geometry as EPSG:4326 →
    **NaN areas eliminated**, no more off-world placement.
  - Removed the hardcoded **Bangalore** OSM fallback (`tasks.py`); OSM is skipped when there
    are no real bounds.

**Frontend**
- Upload workspace has a **mode toggle** (Segmentation vs Object Detection), persisted across
  navigation via `UploadContext`.
- Detection-mode results render the **annotated overlay** (fetched with the bearer token as an
  object URL) + per-class count chips + a "not georeferenced" notice. Segmentation mode keeps
  the GIS-map flow.

## Verification (all passed)

| Test | Result |
|---|---|
| Model `id2label` (offline) | 8 classes, mapping correct |
| Detection on user's drone JPG (service) | 28 objects: 17 person / 10 car / 1 bus; overlay OK |
| Full Celery task (detection) | `SUCCESS`; features persisted, no NaN, overlay in MinIO, OSM skipped |
| Segmentation NaN fix | non-georef → area 0.0 (pixel); georef → finite area |
| **Real HTTP round-trip** | `POST /upload` (mode=detection) → worker → `GET /status` returns `detection_summary` → `GET /detection-overlay` = 200 image/jpeg |
| Frontend | `tsc -b` clean, `vite build` OK, deployed, app loads with no console errors |

## Notes / follow-ups

- YOLOS-tiny is fast (~0.2–1.8s CPU) but a light detector; occasional low-confidence misfires
  (e.g. a storefront tagged "bus" @0.60). Swappable via `DETECTION_MODEL` env.
- Visual click-through of the authed UI still pending — needs a login (env has no seed
  password set; no account was modified).
- Legacy dead code (`processing_service.py`, `tiling_service.py`, `segmentation_artifact_service.py`)
  still references non-existent ORM models; recommend quarantine.
