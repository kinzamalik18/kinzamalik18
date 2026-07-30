import os
import cv2
import numpy as np
from PIL import Image
from rembg import remove

# Configuration
INPUT_IMAGE = "picture.jpg"
OUTPUT_SVG = "portrait.svg"
FONT_B64_FILE = "font_ramp_b64.txt"
RAMP = " .:-=+*#%@"  # Clean symmetric 9-level brightness ramp
COLS = 80
CHAR_W = 8.5  # Horizontal character width spacing in pixels
Y_SPACING = 15.0  # Line height spacing in pixels
ANIM_SPEED = 0.08  # Stagger delay between rows in seconds
ROW_DUR = 0.4  # Duration of typing animation for a single row in seconds

def load_font_b64():
    if os.path.exists(FONT_B64_FILE):
        with open(FONT_B64_FILE, 'r') as f:
            return f.read().strip()
    # Fallback to empty if not subsetted yet
    print("Warning: font_ramp_b64.txt not found. Font will not be embedded.")
    return ""

def process_image(img_path):
    if not os.path.exists(img_path):
        raise FileNotFoundError(f"Input image not found: {img_path}")
    
    # 1. Load image and remove background
    print(f"Loading {img_path} and removing background...")
    img = Image.open(img_path)
    rgba = remove(img)
    
    # Convert PIL Image to OpenCV format (RGBA)
    rgba_np = np.array(rgba)
    
    # 2. Extract channels and make background white
    # rembg sets background pixels to alpha=0.
    r, g, b, a = cv2.split(rgba_np)
    gray = cv2.cvtColor(rgba_np, cv2.COLOR_RGBA2GRAY)
    gray[a == 0] = 255  # Force background to white (maps to space character)
    
    # 3. Apply Unsharp Masking & Bilateral Filter to sharpen boundaries while smoothing skin
    print("Applying sharpening filter and bilateral edge preservation...")
    blur = cv2.GaussianBlur(gray, (0, 0), 3.0)
    sharpened = cv2.addWeighted(gray, 1.8, blur, -0.8, 0)
    smoothed = cv2.bilateralFilter(sharpened, d=7, sigmaColor=50, sigmaSpace=50)
    
    # 4. Detect boundary edges (eyes, lips, jawline, hair, collar) using Canny
    print("Extracting boundary edges...")
    edges = cv2.Canny(smoothed, threshold1=40, threshold2=120)
    
    # 5. Apply CLAHE local contrast enhancement
    print("Applying CLAHE local contrast enhancement...")
    clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
    contrast = clahe.apply(smoothed)
    
    # 6. Apply Darkening Curve and superimpose boundary edge map
    print("Applying darkening curve and superimposing boundary edges...")
    normalized = contrast / 255.0
    darkened = np.power(normalized, 1.8) * 255.0
    darkened = darkened.astype(np.uint8)
    
    # Darken detected boundary edges so outlines stand out clearly
    edge_mask = (edges > 0) & (a > 0)
    darkened[edge_mask] = np.clip(darkened[edge_mask].astype(int) - 90, 0, 255).astype(np.uint8)
    
    # 7. Resize to target columns while maintaining aspect ratio and correcting for font height
    h, w = darkened.shape
    aspect_ratio = h / w
    # Monospace characters are roughly 0.48 times as wide as they are tall in our layout
    rows = int(COLS * aspect_ratio * 0.48)
    print(f"Resizing to {COLS} columns x {rows} rows...")
    resized = cv2.resize(darkened, (COLS, rows), interpolation=cv2.INTER_AREA)
    
    return resized, COLS, rows

def generate_svg(pixel_grid, cols, rows):
    print("Generating animated SVG...")
    font_b64 = load_font_b64()
    
    # Calculate dimensions
    width = int(cols * CHAR_W)
    height = int(rows * Y_SPACING) + 5
    
    # Header of SVG
    svg_parts = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">')
    
    # Embed Font Styles
    svg_parts.append('  <defs>')
    if font_b64:
        svg_parts.append('    <style>')
        svg_parts.append('      @font-face {')
        svg_parts.append("        font-family: 'JetBrains Mono';")
        svg_parts.append(f"        src: url('{font_b64}') format('woff2');")
        svg_parts.append('        font-weight: normal;')
        svg_parts.append('        font-style: normal;')
        svg_parts.append('      }')
        svg_parts.append('    </style>')
    
    svg_parts.append('    <style>')
    svg_parts.append("      .row { font-family: 'JetBrains Mono', monospace; font-size: 13px; letter-spacing: 0.5px; fill: #c9d1d9; white-space: pre; }")
    svg_parts.append('      .cursor { fill: #58a6ff; }')
    svg_parts.append('      @media (prefers-color-scheme: light) {')
    svg_parts.append('        .row { fill: #24292f; }')
    svg_parts.append('        .cursor { fill: #0969da; }')
    svg_parts.append('      }')
    svg_parts.append('    </style>')
    
    # Define ClipPaths for typing animation
    for i in range(rows):
        start_time = f"{i * ANIM_SPEED:.3f}"
        svg_parts.append(f'    <clipPath id="clip-{i}">')
        svg_parts.append(f'      <rect x="0" y="{i * Y_SPACING:.1f}" width="0" height="15">')
        svg_parts.append(f'        <animate attributeName="width" from="0" to="{width}" dur="{ROW_DUR}s" begin="{start_time}s" fill="freeze" />')
        svg_parts.append('      </rect>')
        svg_parts.append('    </clipPath>')
    svg_parts.append('  </defs>')
    
    # Draw Character Rows
    for i in range(rows):
        row_chars = []
        for j in range(cols):
            val = pixel_grid[i, j]
            # Map 0-255 to 0-12 (index into RAMP)
            # 255 (white) -> index 0 (space)
            # 0 (black) -> index 12 (@)
            idx = int((255 - val) / 255.0 * (len(RAMP) - 1))
            row_chars.append(RAMP[idx])
        
        row_str = "".join(row_chars)
        # Escape HTML special entities
        row_str_escaped = row_str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # Row text with clip path
        y_pos = (i * Y_SPACING) + 11.0  # Align baseline
        svg_parts.append(f'  <text x="0" y="{y_pos:.1f}" class="row" clip-path="url(#clip-{i})">{row_str_escaped}</text>')
        
        # Cursor overlay riding the edge of typing animation
        start_time = f"{i * ANIM_SPEED:.3f}"
        svg_parts.append(f'  <rect x="0" y="{i * Y_SPACING:.1f}" width="{CHAR_W:.2f}" height="13" class="cursor" visibility="hidden">')
        svg_parts.append(f'    <set attributeName="visibility" to="visible" begin="{start_time}s" dur="{ROW_DUR}s" />')
        svg_parts.append(f'    <animate attributeName="x" from="0" to="{width}" dur="{ROW_DUR}s" begin="{start_time}s" fill="freeze" />')
        svg_parts.append('  </rect>')
        
    svg_parts.append('</svg>')
    
    # Write output
    with open(OUTPUT_SVG, 'w', encoding='utf-8') as f:
        f.write("\n".join(svg_parts))
    print(f"Successfully generated {OUTPUT_SVG}")

def main():
    try:
        pixel_grid, cols, rows = process_image(INPUT_IMAGE)
        generate_svg(pixel_grid, cols, rows)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please place your headshot photo as 'profile.jpg' in the root of the repository directory.")

if __name__ == "__main__":
    main()
