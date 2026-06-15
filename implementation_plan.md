# Label Studio Human Review Architecture & Active Learning Extension

The system has successfully integrated Label Studio and pixel-level semantic extraction. Based on the expanded PRD, we must now build the actual "Intelligence" layer that learns from these human corrections, applies geometric validation rules, and exports retraining packages.

## Goal Description

1. **Misclassification Tracking**: When a user corrects a label in Label Studio, the webhook must precisely track the exact class transition (e.g., `Building -> Tree`) by matching region IDs and logging it to the `PredictionVsCorrection` database table for analytics.
2. **Classification Improvement (Dynamic Confidence)**: The processing engine must learn from historical mistakes. If a specific class (like Building) is frequently corrected to something else, the engine will automatically apply a confidence penalty to future Building predictions to prevent dataset poisoning.
3. **Class Identification Validation**: We will add strict geometric and contextual rules for specific classes before finalizing their labels. We already have rules for Buildings (regularity) and Trees (circularity). We will add:
   - **Road Rules**: Check for linear geometry (aspect ratio > threshold).
   - **Water Rules**: Check for region smoothness (solidity > threshold).
4. **Retraining Pipeline Export**: Build a `/retraining-package` API endpoint to zip and download the `corrections_dataset/` directory so you can extract it weekly for fine-tuning SegFormer/UperNet.

## User Review Required

> [!IMPORTANT]
> **Dynamic Confidence Adjustments**: I plan to implement a feedback loop where if a class has a >50% correction rate in the database history, the processing engine will penalize its confidence by `0.15` in future images. If its confidence drops below `0.60`, it will automatically be assigned as `unknown` (per your instructions). Does a `0.15` penalty sound appropriate for the heuristic?

> [!WARNING]
> **Region Matching Logic**: Label Studio allows users to redraw, split, or merge regions. Tracking an exact 1-to-1 "Building -> Tree" transition works best when the user just changes the class label of an existing polygon. If a user entirely deletes a polygon and draws a new one, the system will track it as a `new_region` correction rather than a direct class swap.

## Proposed Changes

### 1. Active Learning Webhook (`backend/app/api/review.py`)
#### [MODIFY] `label_studio_webhook`
- Parse the `annotation` payload to find specific region ID matches between the AI's original prediction and the human's correction.
- Extract the `predicted_class` and `corrected_class`.
- Save these strings explicitly to the `PredictionVsCorrection` table to track the confusion matrix.

### 2. Processing Engine Intelligence (`backend/app/services/processing_service.py`)
#### [MODIFY] `_process_image`
- **Dynamic Learning**: Query `PredictionVsCorrection` to calculate a localized historical error rate for the current `class_name`. Apply a confidence penalty if the error rate is high.
- **Geometric Validation**: 
  - Add `Road` validation: Calculate bounding box aspect ratio and penalize non-linear/blocky roads.
  - Add `Water` validation: Calculate contour solidity (Area / Convex Hull Area) and penalize highly irregular "water" shapes.

### 3. Retraining Pipeline (`backend/app/api/exports.py`)
#### [NEW] `download_retraining_package`
- Create a new endpoint `GET /api/v1/exports/{project_id}/retraining-package`.
- It will zip the `data/corrections_dataset/` folder containing the image patches, masks, and JSON metadata, and return it as a `.zip` download.

## Verification Plan

### Automated/Local Tests
1. Simulate a Label Studio webhook payload where `building_rooftop` is changed to `tree_canopy`. Verify the database logs `predicted_class="building_rooftop"` and `corrected_class="tree_canopy"`.
2. Process a new image containing a "Building" and verify that its confidence is dynamically penalized because of the previous correction.
3. Test the Retraining Package export to ensure it properly zips the directory.

### Manual Verification
- You will be asked to correct several labels in Label Studio.
- You will then download the Retraining Package via the API/Frontend to verify the corrected data is properly formatted for model fine-tuning.
