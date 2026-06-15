# Active Learning Intelligence Loop Tasks

- `[x]` 1. **Misclassification Tracking (`review.py`)**
  - `[x]` Update webhook to map AI regions to Human regions
  - `[x]` Extract specific `predicted_class` and `corrected_class`
  - `[x]` Save extracted classes and `region_id` to `PredictionVsCorrection` table
- `[x]` 2. **Geometric Validation (`processing_service.py`)**
  - `[x]` Implement Road Rules (check linear geometry/aspect ratio)
  - `[x]` Implement Water Rules (check contour solidity/smoothness)
- `[x]` 3. **Dynamic Confidence Adjustment (`processing_service.py`)**
  - `[x]` Query historical misclassifications from `PredictionVsCorrection`
  - `[x]` Calculate error rate per class
  - `[x]` Apply `0.15` penalty to historically confused classes
  - `[x]` Force `unknown` class assignment if confidence drops below `< 0.60`
- `[x]` 4. **Retraining Pipeline (`exports.py`)**
  - `[x]` Create `GET /api/v1/exports/{project_id}/retraining-package` endpoint
  - `[x]` Zip the `data/corrections_dataset/` directory
  - `[x]` Return zip file to frontend for download
