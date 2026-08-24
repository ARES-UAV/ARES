"""Time a model honestly: warm up first, then take the median of many runs."""

import sys, time, statistics
from ultralytics import YOLO

MODEL = sys.argv[1]
IMGSZ = int(sys.argv[2]) if len(sys.argv) > 2 else 640
IMAGE = sys.argv[3] if len(sys.argv) > 3 else "test_frame.jpg"

model = YOLO(MODEL)

# Warm up — never time these. The first calls include model load,
# memory allocation and cache warming.
for _ in range(5):
    model.predict(IMAGE, imgsz=IMGSZ, conf=0.18, max_det=1000, verbose=False)

times = []
for _ in range(30):
    t0 = time.perf_counter()
    r = model.predict(IMAGE, imgsz=IMGSZ, conf=0.18, max_det=1000, verbose=False)
    times.append((time.perf_counter() - t0) * 1000)

med = statistics.median(times)
print(f"model      {MODEL}  @ {IMGSZ}px")
print(f"median     {med:.1f} ms")
print(f"mean       {statistics.mean(times):.1f} ms")
print(f"best/worst {min(times):.1f} / {max(times):.1f} ms")
print(f"FPS        {1000/med:.2f}")
print(f"stages     {r[0].speed}")     # preprocess / inference / postprocess