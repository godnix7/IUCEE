"""
Forensic diagnostic for UrbanSense AI inference.
Faithfully replicates AIService.run_inference tiling/inference math, then:
  Step 3: reports tile array bands/dtype/min-max
  Step 4: reports processor pixel-value stats (double-normalization check)
  Step 5: raw argmax -> per-class pixel percentage histogram
  Step 6: saves colored mask + side-by-side overlay PNG
Runs OFFLINE against the cached model.
"""
import os, sys, math
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
import numpy as np
import rasterio
import torch
from PIL import Image
from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation

MODEL = "wu-pr-gw/segformer-b2-finetuned-with-LoveDA"
TILE, STRIDE = 512, 384
ID2LABEL = {0:"Ignore",1:"Background",2:"Building",3:"Road",4:"Water",5:"Barren",6:"Forest",7:"Agricultural"}
# distinct colors per class (RGB)
COLORS = {
 0:(0,0,0), 1:(120,120,120), 2:(220,20,60), 3:(255,255,0),
 4:(0,90,255), 5:(160,110,60), 6:(0,100,0), 7:(120,220,120)
}

def hann(h,w):
    return np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)

def run(image_path, out_png):
    print(f"\n{'='*70}\nIMAGE: {image_path}")
    proc = SegformerImageProcessor.from_pretrained(MODEL)
    model = SegformerForSemanticSegmentation.from_pretrained(MODEL).eval()
    n_cls = len(model.config.id2label)

    with rasterio.open(image_path) as src:
        print(f"  raster: {src.width}x{src.height}, bands={src.count}, crs={src.crs}, dtype={src.dtypes}")
        print(f"  transform={src.transform!r}")
        W, H = src.width, src.height
        img = np.transpose(src.read([1,2,3]), (1,2,0))   # H,W,3

    # STEP 3: tile array stats (sample center tile)
    cy, cx = max(0,H//2-256), max(0,W//2-256)
    sample = img[cy:cy+TILE, cx:cx+TILE, :]
    print(f"  [Step3] sample tile shape={sample.shape} dtype={sample.dtype} "
          f"min={sample.min()} max={sample.max()} mean={sample.mean():.1f}")

    # STEP 4: processor output stats (double-normalization check)
    pin = proc(images=sample, return_tensors="pt")["pixel_values"]
    print(f"  [Step4] processed tensor shape={tuple(pin.shape)} "
          f"min={pin.min():.3f} max={pin.max():.3f} mean={pin.mean():.3f}  "
          f"(ImageNet-normalized range ~[-2.1,2.6] expected; NOT ~[-0.01,0.01])")

    xs = math.ceil((W-TILE)/STRIDE)+1 if W>TILE else 1
    ys = math.ceil((H-TILE)/STRIDE)+1 if H>TILE else 1
    glogits = np.zeros((n_cls,H,W), np.float32)
    gw = np.zeros((H,W), np.float32)
    with torch.inference_mode():
        for yi in range(ys):
            for xi in range(xs):
                sy, sx = yi*STRIDE, xi*STRIDE
                if sy+TILE>H: sy=max(0,H-TILE)
                if sx+TILE>W: sx=max(0,W-TILE)
                ey, ex = min(H,sy+TILE), min(W,sx+TILE)
                th, tw = ey-sy, ex-sx
                tile = img[sy:ey, sx:ex, :]
                inp = proc(images=tile, return_tensors="pt")
                out = model(**inp).logits
                up = torch.nn.functional.interpolate(out, size=(th,tw), mode="bilinear", align_corners=False)
                ln = up.squeeze(0).cpu().numpy()
                wt = hann(th,tw)
                glogits[:, sy:ey, sx:ex] += ln*wt
                gw[sy:ey, sx:ex] += wt
    gw[gw==0]=1.0
    glogits /= gw
    probs = torch.softmax(torch.from_numpy(glogits).unsqueeze(0), dim=1)
    conf, mask = torch.max(probs, dim=1)
    mask = mask.squeeze(0).numpy().astype(np.uint8)
    conf = conf.squeeze(0).numpy()

    # STEP 5: histogram
    print(f"  [Step5] RAW ARGMAX CLASS HISTOGRAM (of {H*W} px):")
    total = mask.size
    for c in range(n_cls):
        cnt = int((mask==c).sum())
        if cnt:
            mc = float(conf[mask==c].mean())
            print(f"     {c} {ID2LABEL[c]:<12} {100*cnt/total:6.2f}%   mean_conf={mc:.3f}")

    # STEP 6: colored mask + overlay
    color = np.zeros((H,W,3), np.uint8)
    for c in range(n_cls):
        color[mask==c] = COLORS[c]
    orig = img[:,:,:3].astype(np.uint8)
    overlay = (0.55*orig + 0.45*color).astype(np.uint8)
    combo = np.concatenate([orig, color, overlay], axis=1)
    Image.fromarray(combo).save(out_png)
    print(f"  [Step6] saved -> {out_png}  (left=orig | mid=mask | right=overlay)")

if __name__ == "__main__":
    for p, o in zip(sys.argv[1::2], sys.argv[2::2]):
        run(p, o)
