import cv2
import numpy as np
from PIL import Image as PILImage
from transformers import SamModel, SamProcessor
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Loading SAM on {device}...")
processor = SamProcessor.from_pretrained("facebook/sam-vit-base")
model = SamModel.from_pretrained("facebook/sam-vit-base").to(device)
print("SAM loaded!")

img = np.zeros((1024, 1024, 3), dtype=np.uint8)
pil_img = PILImage.fromarray(img)

bx1, by1, bx2, by2 = 10, 10, 50, 50
input_boxes = [[[bx1, by1, bx2, by2]]]

try:
    print("Running processor...")
    inputs = processor(pil_img, input_boxes=[input_boxes], return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    print(f"Processor output keys: {inputs.keys()}, shape of input_boxes: {inputs.get('input_boxes', 'None').shape}")
    
    print("Running model inference...")
    with torch.no_grad():
        with torch.amp.autocast("cuda"):
            outputs = model(**inputs)
            
    print("Model ran!")
    masks = processor.image_processor.post_process_masks(
        outputs.pred_masks.cpu(), inputs["original_sizes"].cpu(), inputs["reshaped_input_sizes"].cpu()
    )
    print(f"Masks generated! Shape: {masks[0].shape}")
except Exception as e:
    print(f"Processor error: {e}")
