import os
import urllib.request
import base64
from fontTools import subset

FONT_URL = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf/JetBrainsMono-Regular.ttf"
FONT_FILENAME = "JetBrainsMono-Regular.ttf"

def download_font():
    if not os.path.exists(FONT_FILENAME):
        print(f"Downloading JetBrains Mono from {FONT_URL}...")
        urllib.request.urlretrieve(FONT_URL, FONT_FILENAME)
        print("Download complete.")
    else:
        print("Font already downloaded.")

def subset_font(text_charset, output_woff2_name):
    print(f"Subsetting font for charset: {repr(text_charset)} -> {output_woff2_name}")
    
    # Setup pyftsubset options programmatically
    options = subset.Options()
    options.flavor = 'woff2'
    options.layout_features = ['*']
    options.hinting = False
    options.desubroutinize = True
    
    # Load and subset
    font = subset.load_font(FONT_FILENAME, options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text=text_charset)
    subsetter.subset(font)
    
    # Save the font
    subset.save_font(font, output_woff2_name, options)
    print(f"Saved subsetted font to {output_woff2_name}")
    
    # Read and encode to base64
    with open(output_woff2_name, 'rb') as f:
        font_data = f.read()
    
    b64_data = base64.b64encode(font_data).decode('utf-8')
    b64_uri = f"data:font/woff2;charset=utf-8;base64,{b64_data}"
    
    # Also write a base64 txt file for easy inclusion
    output_txt_name = output_woff2_name.replace('.woff2', '_b64.txt')
    with open(output_txt_name, 'w') as f:
        f.write(b64_uri)
    
    print(f"Saved base64 URI to {output_txt_name} (Size: {len(b64_uri)/1024:.2f} KB)")
    return b64_uri

def main():
    download_font()
    
    # 1. Ramp subset (only the characters used in the ASCII portrait)
    # The default ramp characters are: ' .`:-=+*cs#%@'
    ramp_chars = " .`:-=+*cs#%@"
    subset_font(ramp_chars, "font_ramp.woff2")
    
    # 2. Stats/UI subset (alphanumeric, punctuation, symbols)
    # Includes common chars for stats display: labels, numbers, dates, streaks, metrics.
    ui_chars = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        " .,:;-_+*=/%#@$()[]{}<>|&\\'\"`~"
    )
    subset_font(ui_chars, "font_ui.woff2")

if __name__ == "__main__":
    main()
