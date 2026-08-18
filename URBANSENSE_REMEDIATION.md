# UrbanSense Production Remediation

## Overview

This document tracks the systematic remediation of the UrbanSense AI-Powered Urban Infrastructure Intelligence System.
A comprehensive audit was completed on 2026-08-16 which identified multiple features falsely claimed as implemented,
hardcoded/mocked data, security vulnerabilities, and incorrect AI model selection.

## Baseline Commit

`9639426` — pre-remediation snapshot (2026-08-16)

---

## Discovered Issues Summary

### Critical
1. **Wrong pretrained model**: `nvidia/segformer-b3-finetuned-ade-512-512` (ADE20K indoor/street) used for aerial imagery
2. **Hardcoded geospatial bounds**: `[77.58, 12.96, 77.60, 12.98]` used instead of parsing GeoTIFF CRS/affine
3. **Fake SVG GIS map**: `GisExplorerView.tsx` renders hardcoded SVG paths, not real GeoJSON on MapLibre
4. **Synchronous AI inference**: Blocks FastAPI HTTP worker thread

### Security
5. **Hardcoded JWT secret**: `urbansense_super_secret_jwt_key_2026_gis_ai_infrastructure`
6. **Hardcoded DB/MinIO passwords**: In `docker-compose.yml` and `database.py`
7. **Hardcoded seed passwords**: Weak development passwords created unconditionally (REDACTED)
8. **JWT in localStorage**: Access and refresh tokens exposed to XSS
9. **No refresh token revocation**: Stateless JWT refresh with no blacklist

### Data Integrity
10. **Hardcoded dashboard statistics**: Fallback values `68.5`, `18.4%`, `64.2%` in `analytics.py`
11. **Fake historical chart data**: `DashboardView.tsx` contains hardcoded monthly population points
12. **Synthetic OSM geometries**: 30m×30m squares with hardcoded areas (`3500.0`, `4500.0`)
13. **False AI attribution in fallback**: OpenCV HSV thresholding tagged as `source: "ai_segformer"`

### GIS/Spatial
14. **No PostGIS native geometry**: Uses JSON text columns instead of `Geometry(Polygon, 4326)`
15. **No GeoTIFF metadata parsing**: Missing `rasterio`/`pyproj` integration
16. **No image tiling**: Full images passed to model without windowing
17. **Duplicate feature generation**: Individual ADE20K class IDs processed separately

### Missing/Broken
18. **`SUPPORTED_EXTENSIONS` undefined**: Referenced in `inference.py` but never defined — runtime crash
19. **Non-functional GIS toolbar buttons**: Draw, Distance, Area, Compare do nothing
20. **No file size/MIME validation**: Upload accepts anything

---

## Selected Pretrained Model

| Property | Value |
|---|---|
| Model | `wu-pr-gw/segformer-b2-finetuned-with-LoveDA` |
| Dataset | LoveDA (0.3m resolution aerial imagery) |
| Classes | Background(0), Building(1), Road(2), Water(3), Barren(4), Forest(5), Agriculture(6) |
| Architecture | SegFormer MiT-B2 |
| License | Apache 2.0 |

### UrbanSense Class Mapping

| LoveDA Class | UrbanSense Class |
|---|---|
| Background (0) | ignored |
| Building (1) | `building` |
| Road (2) | `road` |
| Water (3) | `water` |
| Barren (4) | `barren_land` |
| Forest (5) | `tree_cover` |
| Agriculture (6) | `agriculture` |

---

## Implementation Order

| Phase | Scope | Status |
|---|---|---|
| 0 | Baseline & documentation | ✅ Complete |
| 1 | Security & authentication | 🔄 In Progress |
| 2 | Real PostGIS spatial engine | ⬜ Pending |
| 3 | GeoTIFF spatial processing (rasterio/pyproj) | ⬜ Pending |
| 4 | Image tiling pipeline | ⬜ Pending |
| 5 | AI segmentation (LoveDA SegFormer) | ⬜ Pending |
| 6 | Mask consolidation & polygonization | ⬜ Pending |
| 7 | OSM enrichment corrections | ⬜ Pending |
| 8 | Async job queue | ⬜ Pending |
| 9 | Real MapLibre GIS map | ⬜ Pending |
| 10 | Real analytics (remove mocks) | ⬜ Pending |
| 11 | Reports & export | ⬜ Pending |
| 12 | Error handling & file validation | ⬜ Pending |
| 13 | Testing | 🔄 In Progress |

---

## Phase 1 — Security & Authentication

### Expected Behavior After Phase 1

- All secrets loaded from environment variables; production refuses to start without them
- Seed users only created when `ENVIRONMENT=development`
- Access tokens expire in 15 minutes
- Refresh tokens stored in DB with rotation and revocation
- Refresh tokens delivered via HttpOnly cookies, never exposed to JavaScript
- Reuse of revoked refresh tokens is rejected
- Frontend stores access token in memory only
- Logout revokes active refresh token
- `SUPPORTED_EXTENSIONS` crash bug fixed
