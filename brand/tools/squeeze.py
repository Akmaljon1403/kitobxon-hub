"""Re-save every PNG under a folder with the strongest lossless compression (same pixels, smaller file)."""

import sys
from pathlib import Path

from PIL import Image

before = after = 0
for path in Path(sys.argv[1]).rglob("*.png"):
    size = path.stat().st_size
    with Image.open(path) as image:
        image.load()
        info = {"dpi": (300, 300)}
        image.save(path, format="PNG", optimize=True, **info)
    before += size
    after += path.stat().st_size
print(f"PNG: {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB")
