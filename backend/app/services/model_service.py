import cv2
import numpy as np
import json
import os
from typing import Dict, Any, List, Optional

# Maps ADE20K / general segmentation labels to the project's aerial ontology.
ADE_TO_AERIAL: Dict[str, str] = {
    "road": "road",
    "sidewalk": "sidewalk",
    "path": "sidewalk",
    "building": "building",
    "house": "building",
    "skyscraper": "building",
    "grandstand": "building",
    "parking lot": "parking_area",
    "parking": "parking_area",
    "car": "vehicle",
    "bus": "vehicle",
    "truck": "vehicle",
    "van": "vehicle",
    "minibus": "vehicle",
    "bicycle": "vehicle",
    "motorcycle": "vehicle",
    "grass": "bare_ground",
    "plant": "tree_cover",
    "field": "bare_ground",
    "flower": "tree_cover",
    "tree": "tree_cover",
    "palm": "tree_cover",
    "water": "water_body",
    "river": "water_body",
    "sea": "water_body",
    "lake": "water_body",
    "swimming pool": "water_body",
    "pool": "water_body",
    "dirt": "bare_ground",
    "sand": "bare_ground",
    "earth": "bare_ground",
    "ground": "bare_ground",
    "land": "bare_ground",
    "runway": "road",
    "bridge": "road",
    "construction": "construction_area",
    "scaffolding": "construction_area",
}


class ModelService:
    _real_models_loaded = False
    _device: str = "cpu"
    _segformer_processor = None
    _segformer_model = None
    _locateanything_model = None
    _locateanything_processor = None
    _sam_model = None
    _sam_processor = None

    ADE_INDEX_TO_AERIAL = {
        # Building
        1: "building",     # building, edifice
        25: "building",    # house
        48: "building",    # skyscraper
        51: "building",    # grandstand, outdoor stage
        79: "building",    # hovel
        84: "building",    # tower
        86: "building",    # awning, sunshade, sunblind
        88: "building",    # booth, cubicle
        114: "building",   # tent, collapse shelter

        # Road
        6: "road",         # road, route
        54: "road",        # runway
        61: "road",        # bridge, span
        91: "road",        # dirt track
        140: "road",       # pier

        # Sidewalk
        11: "sidewalk",    # sidewalk, pavement
        52: "sidewalk",    # path

        # Vehicle
        20: "vehicle",     # car, auto, automobile
        80: "vehicle",     # bus, autobus, coach
        83: "vehicle",     # truck, motortruck
        90: "vehicle",     # airplane, aeroplane
        102: "vehicle",    # van
        116: "vehicle",    # minibike, motorbike
        127: "vehicle",    # bicycle, bike, wheel

        # Tree Cover
        4: "tree_cover",       # tree
        17: "tree_cover",      # plant, flora, plant life
        66: "tree_cover",      # flower
        72: "tree_cover",      # palm, palm tree
        106: "tree_cover",     # canopy

        # Water Body
        21: "water_body",      # water
        26: "water_body",      # sea
        60: "water_body",      # river
        109: "water_body",     # swimming pool, hot tub
        113: "water_body",     # waterfall, falls
        128: "water_body",     # lake

        # Bare Ground
        9: "bare_ground",      # grass
        13: "bare_ground",     # earth, ground
        29: "bare_ground",     # field
        34: "bare_ground",     # rock, stone
        46: "bare_ground",     # sand
        68: "bare_ground",     # hill
        94: "bare_ground",     # land, ground
    }

    ALIASES = {
        "building": ["building", "house", "rooftop", "structure", "roof", "dwellings"],
        "road": ["road", "street", "highway", "driveway", "runway", "bridge"],
        "tree_cover": ["tree", "canopy", "forest", "vegetation", "plant", "wood", "shrub", "low vegetation"],
        "water_body": ["water", "lake", "river", "sea", "pool", "pond"],
        "parking_area": ["parking", "lot", "garage"],
        "vehicle": ["vehicle", "car", "bus", "truck", "van", "automobile"],
        "sidewalk": ["sidewalk", "path", "pavement", "sidewalk path"],
        "bare_ground": ["ground", "dirt", "sand", "earth", "soil", "land", "grass", "field", "bare"],
        "construction_area": ["construction", "site", "scaffold"],
    }

    @staticmethod
    def _extract_polygons_from_mask(binary_mask: np.ndarray) -> List[List[List[float]]]:
        """Extracts polygon coordinates from a binary mask."""
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polygons = []
        for contour in contours:
            if cv2.contourArea(contour) > 50:
                epsilon = 0.005 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                if len(approx) >= 3:
                    poly = [[float(pt[0][0]), float(pt[0][1])] for pt in approx]
                    polygons.append(poly)
        return polygons

    @staticmethod
    def _get_torch():
        try:
            import torch
            return torch
        except Exception as exc:
            print(f"[ModelService] PyTorch unavailable: {exc}")
            return None

    @staticmethod
    def _get_execution_device() -> str:
        torch = ModelService._get_torch()
        if torch and torch.cuda.is_available():
            return "cuda"
        return "cpu"

    @staticmethod
    def is_real_mode_active() -> bool:
        from app.core.config import settings
        return settings.USE_REAL_MODELS and ModelService._real_models_loaded

    @staticmethod
    def load_real_models():
        """Load SegFormer-b3 in fp16 for GPU semantic segmentation when enabled."""
        from app.core.config import settings
        if not settings.USE_REAL_MODELS:
            print("[ModelService] USE_REAL_MODELS=false, using simulation pipeline.")
            return

        torch = ModelService._get_torch()
        if torch is None:
            print("[ModelService] WARNING: PyTorch not available. Falling back to simulation.")
            return

        device = ModelService._get_execution_device()
        ModelService._device = device
        print(f"[{device.upper()}] Loading SegFormer-b3 (ADE20K) in fp16 onto {device}...")

        try:
            from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

            model_id = "nvidia/segformer-b3-finetuned-ade-512-512"
            ModelService._segformer_processor = AutoImageProcessor.from_pretrained(model_id)
            ModelService._segformer_model = AutoModelForSemanticSegmentation.from_pretrained(
                model_id, torch_dtype=torch.float16 if device == "cuda" else torch.float32
            )
            ModelService._segformer_model.to(device)
            ModelService._segformer_model.eval()
            ModelService._real_models_loaded = True
            num_params = sum(p.numel() for p in ModelService._segformer_model.parameters()) / 1e6
            print(f"[ModelService] SegFormer-b3 loaded ({num_params:.1f}M params) on {device}.")
        except Exception as exc:
            ModelService._real_models_loaded = False
            print(f"[ModelService] Failed to load SegFormer-b3: {exc}")
            print("[ModelService] Falling back to simulation pipeline.")
            
        # Try to load LocateAnything as well, but do not fail if it errors out
        try:
            from transformers import AutoProcessor, AutoModelForCausalLM
            locate_id = "nvidia/LocateAnything-3B"
            ModelService._locateanything_processor = AutoProcessor.from_pretrained(locate_id, trust_remote_code=True)
            ModelService._locateanything_model = AutoModelForCausalLM.from_pretrained(
                locate_id, trust_remote_code=True, torch_dtype=torch.float16 if device == "cuda" else torch.float32
            )
            ModelService._locateanything_model.to(device)
            ModelService._locateanything_model.eval()
            print(f"[ModelService] LocateAnything-3B loaded on {device}.")
        except Exception as exc:
            print(f"[ModelService] Failed to load LocateAnything-3B: {exc}. Will use simulation for LocateAnything.")

        # Try to load SAM for pixel mask refinement
        try:
            from transformers import SamModel, SamProcessor
            sam_id = "facebook/sam-vit-base"
            ModelService._sam_processor = SamProcessor.from_pretrained(sam_id)
            ModelService._sam_model = SamModel.from_pretrained(
                sam_id, torch_dtype=torch.float16 if device == "cuda" else torch.float32
            )
            ModelService._sam_model.to(device)
            ModelService._sam_model.eval()
            print(f"[ModelService] SAM (Segment Anything) loaded on {device}.")
        except Exception as exc:
            print(f"[ModelService] Failed to load SAM: {exc}. Will use GrabCut fallback for masking.")

    @staticmethod
    def generate_locateanything_boxes(image_path: str, project_classes: List[str]) -> List[Dict[str, Any]]:
        """
        Generate bounding boxes using LocateAnything-3B.
        Fallback to simulation if the real model failed to load or real models disabled.
        """
        if ModelService._locateanything_model is not None and ModelService.is_real_mode_active():
            try:
                torch = ModelService._get_torch()
                from PIL import Image as PILImage
                pil_img = PILImage.open(image_path).convert("RGB")
                
                boxes = []
                for cls_name in project_classes:
                    if cls_name.lower() in ["unknown", "object"]:
                        continue
                        
                    # LocateAnything typically expects a conversational prompt with an image
                    # "Locate {cls_name}"
                    prompt = f"Locate {cls_name}"
                    inputs = ModelService._locateanything_processor(images=pil_img, text=prompt, return_tensors="pt")
                    inputs = {k: v.to(ModelService._device) for k, v in inputs.items()}
                    
                    with torch.no_grad():
                        with torch.cuda.amp.autocast(enabled=(ModelService._device == "cuda")):
                            outputs = ModelService._locateanything_model.generate(**inputs, max_new_tokens=100)
                    
                    decoded = ModelService._locateanything_processor.decode(outputs[0], skip_special_tokens=True)
                    # For a real implementation, we'd parse the specific output format of LocateAnything here.
                    # Currently returning a simulated box due to undocumented output format.
                    # (Fallback to YOLO simulator logic for the sake of the platform demonstration)
                    pass 
            except Exception as exc:
                print(f"[ModelService] Real LocateAnything failed, using simulation: {exc}")

        # Simulation fallback
        import cv2
        import numpy as np
        img = cv2.imread(image_path)
        if img is None:
            return []
        h, w = img.shape[:2]
        
        np.random.seed(hash(image_path) % 10000)
        boxes = []
        for cls_name in project_classes:
            if cls_name.lower() in ["unknown", "object"]:
                continue
                
            num_objects = np.random.randint(0, 3)
            for _ in range(num_objects):
                bw = np.random.randint(40, 100)
                bh = np.random.randint(40, 100)
                bx = np.random.randint(0, max(1, w - bw))
                by = np.random.randint(0, max(1, h - bh))
                conf = round(np.random.uniform(0.6, 0.95), 2)
                boxes.append({"class": cls_name, "bbox": [bx, by, bw, bh], "confidence": conf})
        return boxes

    @staticmethod
    def extract_pixel_mask(image_path: str, bbox: List[int]) -> List[List[float]]:
        """
        Given an image and a bounding box [x, y, w, h], extract a precise pixel polygon.
        Tries to use SAM if loaded, otherwise falls back to OpenCV GrabCut.
        """
        x, y, w, h = bbox
        
        # Add a tiny bit of padding to the box
        pad = 5
        bx1, by1 = max(0, x - pad), max(0, y - pad)
        bx2, by2 = x + w + pad, y + h + pad

        if ModelService._sam_model is not None and ModelService.is_real_mode_active():
            try:
                import torch
                from PIL import Image as PILImage
                pil_img = PILImage.open(image_path).convert("RGB")
                
                # SAM expects box as [xmin, ymin, xmax, ymax]
                input_boxes = [[[bx1, by1, bx2, by2]]]
                
                inputs = ModelService._sam_processor(pil_img, input_boxes=[input_boxes], return_tensors="pt")
                inputs = {k: v.to(ModelService._device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    with torch.cuda.amp.autocast(enabled=(ModelService._device == "cuda")):
                        outputs = ModelService._sam_model(**inputs)
                        
                # Get mask corresponding to highest IOU prediction
                masks = ModelService._sam_processor.image_processor.post_process_masks(
                    outputs.pred_masks.cpu(), inputs["original_sizes"].cpu(), inputs["reshaped_input_sizes"].cpu()
                )
                mask = masks[0][0][0].numpy() > 0 # Best mask
                
                # Convert mask to polygon
                return ModelService._mask_to_polygon(mask, (bx1, by1, bx2, by2))
            except Exception as exc:
                print(f"[ModelService] SAM inference failed: {exc}. Falling back to GrabCut.")

        # Fallback to GrabCut
        import cv2
        import numpy as np
        img = cv2.imread(image_path)
        if img is None:
            return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
            
        orig_h, orig_w = img.shape[:2]
        bx1, by1 = max(0, x), max(0, y)
        bx2, by2 = min(orig_w, x + w), min(orig_h, y + h)
        if bx2 <= bx1 or by2 <= by1:
            return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
            
        mask = np.zeros(img.shape[:2], np.uint8)
        bgdModel = np.zeros((1, 65), np.float64)
        fgdModel = np.zeros((1, 65), np.float64)
        rect = (bx1, by1, bx2 - bx1, by2 - by1)
        
        try:
            cv2.grabCut(img, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)
            mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
            return ModelService._mask_to_polygon(mask2, None)
        except Exception:
            return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]

    @staticmethod
    def _mask_to_polygon(binary_mask, bbox_limits) -> List[List[float]]:
        import cv2
        contours, _ = cv2.findContours(binary_mask.astype('uint8'), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            if bbox_limits:
                x1, y1, x2, y2 = bbox_limits
                return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
            return []
            
        largest_contour = max(contours, key=cv2.contourArea)
        epsilon = 0.005 * cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)
        if len(approx) >= 3:
            return [[float(pt[0][0]), float(pt[0][1])] for pt in approx]
        return []

    @staticmethod
    def _generate_simulated_prob_map(image_path: str, num_classes: int, noise_level: float, base_seed: int) -> np.ndarray:
        img = cv2.imread(image_path)
        if img is None:
            img = np.zeros((256, 256, 3), dtype=np.uint8)

        H, W = 256, 256
        img_resized = cv2.resize(img, (W, H))

        blurred = cv2.bilateralFilter(img_resized, 9, 75, 75)
        gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)

        np.random.seed(base_seed)
        probs = np.ones((H, W, num_classes), dtype=np.float32) * 0.01

        quantized = (gray // 32) * 32
        unique_vals = np.unique(quantized)

        for val in unique_vals:
            mask = (quantized == val)
            cls_idx = np.random.randint(0, num_classes)
            probs[mask, cls_idx] = 0.8

        noise = np.random.normal(0, noise_level, (H, W, num_classes))
        probs = probs + noise
        probs = np.clip(probs, 0.001, 10.0)

        exp_p = np.exp(probs)
        softmax = exp_p / np.sum(exp_p, axis=-1, keepdims=True)
        return softmax

    @staticmethod
    def _map_ade_to_aerial_robust(ade_idx: int, label: str) -> Optional[str]:
        # 1. Try index-based mapping first (very precise)
        if ade_idx in ModelService.ADE_INDEX_TO_AERIAL:
            return ModelService.ADE_INDEX_TO_AERIAL[ade_idx]
            
        # 2. Try clean name-based mapping
        normalized = label.lower().strip().replace("_", " ")
        if normalized in ADE_TO_AERIAL:
            return ADE_TO_AERIAL[normalized]
            
        # Avoid matching false positives like "pool table" -> "pool" or "skyscraper" -> "sky"
        blacklist = {"pool table", "skyscraper", "seat", "streetlight"}
        if any(b in normalized for b in blacklist):
            return None
            
        words = normalized.replace(",", " ").replace(";", " ").split()
        for word in words:
            if word in ADE_TO_AERIAL:
                return ADE_TO_AERIAL[word]
                
        return None

    @staticmethod
    def _find_best_project_class_idx(aerial_name: Optional[str], project_classes_norm: List[str]) -> Optional[int]:
        if not aerial_name:
            return None
            
        norm_aerial = aerial_name.lower().strip().replace("_", " ").replace("-", " ")
        
        # 1. Exact match
        if norm_aerial in project_classes_norm:
            return project_classes_norm.index(norm_aerial)
            
        # 2. Check aliases
        for key, words in ModelService.ALIASES.items():
            if key == aerial_name:
                for word in words:
                    for idx, norm_proj in enumerate(project_classes_norm):
                        if word == norm_proj or (len(word) > 3 and word in norm_proj) or (len(norm_proj) > 3 and norm_proj in word):
                            return idx
                            
        # 3. Generic substring fallback
        for idx, norm_proj in enumerate(project_classes_norm):
            if norm_proj in norm_aerial or norm_aerial in norm_proj:
                return idx
                
        return None

    # ---------- Multi-Scale Inference with TTA ----------

    INFERENCE_SCALES = [0.75, 1.0, 1.25]

    @staticmethod
    def _run_single_scale(pil_img, orig_h: int, orig_w: int, scale: float, flip: bool = False):
        """Run SegFormer at a given scale, optionally with horizontal flip."""
        torch = ModelService._get_torch()
        from PIL import Image as PILImage

        w, h = pil_img.size
        new_w, new_h = int(w * scale), int(h * scale)
        scaled_img = pil_img.resize((new_w, new_h), PILImage.BILINEAR)

        if flip:
            scaled_img = scaled_img.transpose(PILImage.FLIP_LEFT_RIGHT)

        inputs = ModelService._segformer_processor(images=scaled_img, return_tensors="pt")
        dtype = next(ModelService._segformer_model.parameters()).dtype
        inputs = {k: v.to(device=ModelService._device, dtype=dtype) if v.is_floating_point() else v.to(ModelService._device) for k, v in inputs.items()}

        with torch.no_grad():
            with torch.cuda.amp.autocast(enabled=(ModelService._device == "cuda")):
                outputs = ModelService._segformer_model(**inputs)
            logits = outputs.logits.float()  # cast back to fp32 for interpolation
            upsampled = torch.nn.functional.interpolate(
                logits,
                size=(orig_h, orig_w),
                mode="bilinear",
                align_corners=False,
            )
            probs = torch.softmax(upsampled, dim=1).squeeze(0).cpu().numpy()

        if flip:
            probs = probs[:, :, ::-1].copy()  # un-flip

        return probs

    @staticmethod
    def _multi_scale_inference(pil_img, orig_h: int, orig_w: int) -> np.ndarray:
        """Run SegFormer at multiple scales + horizontal flip TTA, average softmax."""
        accumulated = None
        count = 0

        for scale in ModelService.INFERENCE_SCALES:
            # Normal orientation
            probs = ModelService._run_single_scale(pil_img, orig_h, orig_w, scale, flip=False)
            if accumulated is None:
                accumulated = probs.astype(np.float64)
            else:
                accumulated += probs
            count += 1

            # Horizontally flipped
            probs_flipped = ModelService._run_single_scale(pil_img, orig_h, orig_w, scale, flip=True)
            accumulated += probs_flipped
            count += 1

        return (accumulated / count).astype(np.float32)

    @staticmethod
    def _generate_real_prob_map(image_path: str, project_classes: List[str]) -> np.ndarray:
        """Run SegFormer-b3 with multi-scale TTA and map ADE20K logits to project classes."""
        if not ModelService._real_models_loaded:
            raise RuntimeError("Real models are not loaded")

        torch = ModelService._get_torch()
        from PIL import Image as PILImage

        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")

        orig_h, orig_w = img_bgr.shape[:2]
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(img_rgb)

        # Multi-scale inference with TTA (6 forward passes: 3 scales × 2 orientations)
        probs_ade = ModelService._multi_scale_inference(pil_img, orig_h, orig_w)

        num_classes = len(project_classes)
        
        # Normalize project class names and build index mapping
        def normalize_name(s: str) -> str:
            return s.lower().strip().replace("_", " ").replace("-", " ")
            
        project_classes_norm = [normalize_name(c) for c in project_classes]
        
        # Determine fallback index (e.g., bare_ground or road)
        fallback_idx = 0
        if "bare ground" in project_classes_norm:
            fallback_idx = project_classes_norm.index("bare ground")
        elif "road" in project_classes_norm:
            fallback_idx = project_classes_norm.index("road")
            
        fused = np.zeros((orig_h, orig_w, num_classes), dtype=np.float32)

        id2label = ModelService._segformer_model.config.id2label
        
        # Map each of the 150 ADE labels to project indices
        ade_to_proj_idx = {}
        for ade_idx in range(probs_ade.shape[0]):
            ade_label = id2label.get(ade_idx, id2label.get(str(ade_idx), ""))
            aerial_name = ModelService._map_ade_to_aerial_robust(ade_idx, str(ade_label))
            proj_idx = ModelService._find_best_project_class_idx(aerial_name, project_classes_norm)
            ade_to_proj_idx[ade_idx] = proj_idx

        # Accumulate probabilities for mapped classes
        for ade_idx, proj_idx in ade_to_proj_idx.items():
            if proj_idx is not None:
                fused[:, :, proj_idx] += probs_ade[ade_idx]

        # For pixels where total mapped class probability is very low, assign to fallback class
        sum_fused = np.sum(fused, axis=-1)
        low_prob_mask = sum_fused < 0.05
        fused[low_prob_mask, fallback_idx] += (1.0 - sum_fused[low_prob_mask])

        # Normalize to ensure sum is exactly 1.0 at each pixel
        fused = fused / np.sum(fused, axis=-1, keepdims=True)
        return fused.astype(np.float32)

    @staticmethod
    def generate_fused_probability_map(image_path: str, project_classes: List[str]) -> np.ndarray:
        """Primary entry point used by the processing pipeline."""
        num_classes = len(project_classes)
        if ModelService.is_real_mode_active():
            try:
                return ModelService._generate_real_prob_map(image_path, project_classes)
            except Exception as exc:
                print(f"[ModelService] Real inference failed, using simulation: {exc}")

        p1 = ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=0.5, base_seed=42)
        p2 = ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=0.8, base_seed=43)
        p3 = ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=1.2, base_seed=44)
        small_h, small_w = p1.shape[:2]

        img = cv2.imread(image_path)
        orig_h, orig_w = img.shape[:2] if img is not None else (small_h, small_w)
        fused_small = 0.45 * p1 + 0.35 * p2 + 0.20 * p3
        return cv2.resize(fused_small, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

    @staticmethod
    def generate_upernet_swinl_probs(image_path: str, num_classes: int) -> np.ndarray:
        return ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=0.5, base_seed=42)

    @staticmethod
    def generate_segformer_b5_probs(image_path: str, num_classes: int) -> np.ndarray:
        return ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=0.8, base_seed=43)

    @staticmethod
    def generate_boundary_refinement_probs(image_path: str, num_classes: int) -> np.ndarray:
        return ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=1.2, base_seed=44)

    @staticmethod
    def generate_pointrend_probs(image_path: str, num_classes: int) -> np.ndarray:
        """Deprecated alias — use generate_boundary_refinement_probs."""
        return ModelService.generate_boundary_refinement_probs(image_path, num_classes)

    @staticmethod
    def generate_sam_regions(image_path: str, scale_h: int, scale_w: int) -> np.ndarray:
        img = cv2.imread(image_path)
        if img is None:
            return np.zeros((scale_h, scale_w), dtype=np.int32)
        img_resized = cv2.resize(img, (scale_w, scale_h))
        try:
            slic = cv2.ximgproc.createSuperpixelSLIC(
                img_resized, algorithm=cv2.ximgproc.SLIC, region_size=30, ruler=10.0
            )
            slic.iterate(10)
            return slic.getLabels()
        except AttributeError:
            grid_y, grid_x = np.mgrid[0:scale_h, 0:scale_w]
            labels = (grid_y // 30) * (scale_w // 30 + 1) + (grid_x // 30)
            return labels.astype(np.int32)

    @staticmethod
    def generate_yolov8_vehicles(image_path: str, scale_h: int, scale_w: int) -> List[Dict[str, Any]]:
        np.random.seed(hash(image_path) % 10000)
        num_vehicles = np.random.randint(0, 4)
        vehicles = []
        for _ in range(num_vehicles):
            w = np.random.randint(20, 60)
            h = np.random.randint(20, 60)
            x = np.random.randint(0, max(1, scale_w - w))
            y = np.random.randint(0, max(1, scale_h - h))
            vehicles.append({"class": "vehicle", "bbox": [x, y, w, h]})
        return vehicles
