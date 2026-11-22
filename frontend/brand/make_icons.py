"""Renders the app icons from khoj-mark.svg on the UI's page colour. Run from this folder; needs Edge for the SVG."""
import subprocess
from PIL import Image

EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
HERE = "c:/Users/Anvay Anturkar/Khoj/frontend/brand"
BG = "#f7f9fd"
for name, fill in (("any", 0.74), ("maskable", 0.54)):
    html = f'<body style="margin:0;overflow:hidden;background:{BG};width:1024px;height:1024px;display:grid;place-items:center"><img src="khoj-mark.svg" style="height:{int(1024*fill)}px"></body>'
    open(f"{HERE}/_icon_{name}.html", "w").write(html)
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--allow-file-access-from-files", f"--screenshot={HERE}/_icon_{name}.png", "--window-size=1024,1024", f"file:///c:/Users/Anvay%20Anturkar/Khoj/frontend/brand/_icon_{name}.html"], check=True, capture_output=True)
big = Image.open(f"{HERE}/_icon_any.png").convert("RGB").crop((0, 0, 1024, 1024))
mask = Image.open(f"{HERE}/_icon_maskable.png").convert("RGB").crop((0, 0, 1024, 1024))
big.resize((512, 512), Image.LANCZOS).save("../public/icon-512.png", optimize=True)
big.resize((192, 192), Image.LANCZOS).save("../public/icon-192.png", optimize=True)
mask.resize((512, 512), Image.LANCZOS).save("../public/icon-512-maskable.png", optimize=True)
print("icons written")
