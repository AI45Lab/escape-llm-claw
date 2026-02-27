#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RenderGuard - Anti-AI Crawling Web Application

A Flask application that serves encrypted articles using AES-GCM encryption
and LSB steganography. Content is decrypted client-side via JavaScript,
making it resistant to automated content extraction.

Usage:
    python app.py
    # Server runs at http://127.0.0.1:5000
"""

from flask import Flask, request
import base64
import os
import re

app = Flask(__name__)

# ===================== Configuration =====================
PAGE_TITLE = "RenderGuard - Article Viewer"
ICON_SIZE = "80px"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_PNG = os.path.join(BASE_DIR, "encryption", "carrier", "base_image.png")
OUTPUT_PNG_DIR = os.path.join(BASE_DIR, "encryption", "carrier", "encoded")
KEY_INFO_FILE = os.path.join(BASE_DIR, "encryption", "key", "key_mapping.txt")

# Keywords to block AI/crawler requests
AI_KEYWORDS = [
    'bot', 'crawler', 'spider', 'curl', 'wget', 'python', 'requests', 'scrapy',
    'playwright', 'puppeteer', 'chatgpt', 'gpt', 'claude', 'bingbot',
    'googlebot', 'baiduspider'
]


# -------------------------- Utility Functions --------------------------

def reject_ai_crawler():
    """
    Simple User-Agent blocking for AI/crawlers.

    Returns:
        Tuple of (blocked: bool, response_html: str, status_code: int)
    """
    user_agent = request.headers.get('User-Agent', '').lower()
    if any(k in user_agent for k in AI_KEYWORDS) or re.match(r'^python-requests/\d+\.\d+', user_agent):
        html = """<html><head><meta charset="utf-8"></head>
        <body style="text-align:center;margin-top:100px;font-size:20px;">
        Access denied: Crawler/AI detected
        </body></html>"""
        return True, html, 403
    return False, "", 200


def read_article_mapping(mapping_file: str) -> dict:
    """
    Read article-image-key mapping from file.

    Expected format (tab-separated with header):
    ARTICLE_NAME    IMAGE_PATH    AES_KEY_B64    PAYLOAD_LEN

    Args:
        mapping_file: Path to mapping file

    Returns:
        Dict mapping article_id to {img_path, aes_key_b64, payload_len}
    """
    mp = {}
    with open(mapping_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        raise RuntimeError("Mapping file is empty")

    for line in lines[1:]:  # Skip header
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            continue  # Skip malformed lines
        article_id, img_path, aes_key_b64, payload_len = parts
        # Use filename without extension as ID
        article_key = os.path.splitext(article_id)[0]
        mp[article_key] = {
            "id": article_key,
            "img_path": img_path,
            "aes_key_b64": aes_key_b64,
            "payload_len": int(payload_len),
        }
    return mp


def img_to_base64(img_path: str) -> str:
    """
    Convert local image to Base64 data URL.

    Args:
        img_path: Path to image file

    Returns:
        Base64 data URL string
    """
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{b64}"


def safe_title(s: str) -> str:
    """
    Sanitize string for safe use in HTML/URLs.

    Args:
        s: Input string

    Returns:
        Sanitized string with only alphanumeric, underscore, and hyphen
    """
    return re.sub(r"[^a-zA-Z0-9_\-]", "", s)


# -------------------------- Routes: Index Page --------------------------

@app.get("/")
def index_page():
    """Serve the index page with article listing."""
    blocked, html, code = reject_ai_crawler()
    if blocked:
        return html, code

    mapping = read_article_mapping(KEY_INFO_FILE)
    base_img_b64 = img_to_base64(INPUT_PNG)

    # Generate sorted list of article IDs
    ids = sorted(mapping.keys())

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>{PAGE_TITLE}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow, noarchive, nosnippet">
    <style>
      body {{
        font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        padding: 25px;
        margin: 0;
        background: #f8f8f8;
      }}
      #steg-icon {{
        position: fixed;
        top: 25px;
        left: 25px;
        width: {ICON_SIZE};
        height: {ICON_SIZE};
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        z-index: 9999;
        object-fit: cover;
      }}
      .container {{
        width: 800px;
        margin: 0 auto;
      }}
      .title {{
        text-align:center;
        font-size: 22px;
        font-weight: 600;
        color: #2d3748;
        margin-bottom: 8px;
      }}
      .hint {{
        text-align:center;
        color:#666;
        margin-bottom: 18px;
      }}
      .list {{
        background:#fff;
        border-radius: 8px;
        padding: 14px 18px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.06);
      }}
      .item {{
        padding: 10px 6px;
        border-bottom: 1px solid #eee;
      }}
      .item:last-child {{
        border-bottom: none;
      }}
      a {{
        text-decoration:none;
        color:#1a73e8;
      }}
      a:hover {{
        text-decoration: underline;
      }}
    </style>
  </head>
  <body>
    <img id="steg-icon" src="{base_img_b64}" alt="base icon">
    <div class="container">
      <div class="title">RenderGuard</div>
      <div class="hint">Click an article to view (decrypted client-side)</div>
      <div class="list">
        {''.join([f'<div class="item"><a href="/{safe_title(i)}">{safe_title(i)}</a></div>' for i in ids])}
      </div>
    </div>
  </body>
</html>
"""


# -------------------------- Routes: Article Page --------------------------

@app.get("/<article_id>")
def article_page(article_id: str):
    """Serve individual article page with encrypted content."""
    blocked, html, code = reject_ai_crawler()
    if blocked:
        return html, code

    article_id = safe_title(article_id)
    mapping = read_article_mapping(KEY_INFO_FILE)

    if article_id not in mapping:
        return f"""<html><head><meta charset="utf-8"></head>
        <body style="font-family:system-ui;padding:30px;">
        <h3>404: Article not found</h3>
        <p>Unknown id: <b>{article_id}</b></p>
        <p><a href="/">Back to index</a></p>
        </body></html>""", 404

    art = mapping[article_id]
    base_img_b64 = img_to_base64(INPUT_PNG)

    # Load the steganographic image for this article
    img_b64 = img_to_base64(art["img_path"])

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>{PAGE_TITLE} - {article_id}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <meta name="robots" content="noindex, nofollow, noarchive, nosnippet">

    <style>
      body {{
        font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        padding: 25px;
        margin: 0;
        background: #f8f8f8;
      }}
      #steg-icon {{
        position: fixed;
        top: 25px;
        left: 25px;
        width: {ICON_SIZE};
        height: {ICON_SIZE};
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        z-index: 9999;
        object-fit: cover;
      }}
      .wrap {{
        width: 800px;
        margin: 0 auto;
      }}
      .topbar {{
        display:flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
      }}
      .page-title {{
        font-size: 22px;
        font-weight: 600;
        color: #2d3748;
      }}
      .back a {{
        color:#1a73e8;
        text-decoration:none;
      }}
      .back a:hover {{
        text-decoration: underline;
      }}
      .card {{
        font-size: 18px;
        line-height: 1.6;
        white-space: pre-wrap;
        padding: 25px;
        background: #ffffff;
        border-radius: 8px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.06);
        user-select: none;
        -webkit-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
      }}
      .article-title {{
        font-size: 20px;
        font-weight: 700;
        color: #2d3748;
        margin-bottom: 8px;
        padding-bottom: 8px;
        border-bottom: 1px solid #eee;
      }}
      .content-loading {{
        color: #999;
        font-style: italic;
      }}
      ::selection {{background: transparent;}}
      ::-moz-selection {{background: transparent;}}
    </style>

    <script>
      // Anti-crawling: disable right-click, view-source, copy shortcuts
      document.addEventListener('contextmenu', e => e.preventDefault());
      document.addEventListener('keydown', e => {{
        if ((e.ctrlKey && e.key === 'u') || (e.ctrlKey && e.key === 'c') || (e.shiftKey && e.key === 'i')) {{
          e.preventDefault();
        }}
      }});
    </script>
  </head>

  <body>
    <img id="steg-icon" src="{base_img_b64}" alt="base icon">
    <div class="wrap">
      <div class="topbar">
        <div class="page-title">RenderGuard</div>
        <div class="back"><a href="/">Back</a></div>
      </div>

      <div class="card"
           id="article-card"
           data-key="{art['aes_key_b64']}"
           data-payload="{art['payload_len']}"
           data-img="{img_b64}">
        <div class="article-title">{article_id}</div>
        <div class="content content-loading" id="content">(loading...)</div>
      </div>
    </div>

    <script>
      function b64ToBytes(b64) {{
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) {{
          bytes[i] = bin.charCodeAt(i);
        }}
        return bytes;
      }}

      function lsbBitsToBytes(bits) {{
        const data = new Uint8Array(Math.floor(bits.length / 8));
        for (let i = 0; i < data.length; i++) {{
          let byte = 0;
          for (let j = 0; j < 8; j++) {{
            if (i + j >= bits.length) break;
            byte = (byte << 1) | bits[i * 8 + j];
          }}
          data[i] = byte;
        }}
        return data;
      }}

      async function extractDataFromPng(imgB64, dataLen) {{
        const img = new Image();
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        await new Promise((resolve, reject) => {{
          img.crossOrigin = 'anonymous';
          img.onload = resolve;
          img.onerror = () => reject(new Error("Image load failed"));
          img.src = imgB64;
        }});

        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);

        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const pixels = imageData.data;
        const w = canvas.width, h = canvas.height;

        const needBits = dataLen * 8;
        const maxBits = w * h * 3;
        if (needBits > maxBits) {{
          throw new Error(`Data too long! Need ${{needBits}} bits, image only has ${{maxBits}} bits`);
        }}

        const bits = [];
        let bitIdx = 0;
        for (let y = 0; y < h && bitIdx < needBits; y++) {{
          for (let x = 0; x < w && bitIdx < needBits; x++) {{
            const off = (y * w + x) * 4;
            const r = pixels[off];
            const g = pixels[off + 1];
            const b = pixels[off + 2];

            bits.push(r & 1); bitIdx++;
            if (bitIdx >= needBits) break;
            bits.push(g & 1); bitIdx++;
            if (bitIdx >= needBits) break;
            bits.push(b & 1); bitIdx++;
            if (bitIdx >= needBits) break;
          }}
        }}
        return lsbBitsToBytes(bits);
      }}

      async function aesGcmDecrypt(nonce, ct, key) {{
        const cryptoKey = await window.crypto.subtle.importKey(
          'raw', key, {{ name: 'AES-GCM' }}, false, ['decrypt']
        );
        const plainBuf = await window.crypto.subtle.decrypt(
          {{ name: 'AES-GCM', iv: nonce }}, cryptoKey, ct
        );
        return new TextDecoder('utf-8').decode(plainBuf);
      }}

      async function extractAndDecryptPng(key, imgB64, totalPayloadLen) {{
        const payload = await extractDataFromPng(imgB64, totalPayloadLen);
        const nonce = payload.slice(0, 12);
        const ctLenView = new DataView(payload.buffer, 12, 4);
        const ctLen = ctLenView.getUint32(0, false);
        const ct = payload.slice(16, 16 + ctLen);
        return await aesGcmDecrypt(nonce, ct, key);
      }}

      async function decryptOne() {{
        const card = document.getElementById('article-card');
        const out = document.getElementById('content');

        try {{
          const keyB64 = card.dataset.key;
          const payloadLen = parseInt(card.dataset.payload);
          const imgB64 = card.dataset.img;

          const key = b64ToBytes(keyB64);
          const plaintext = await extractAndDecryptPng(key, imgB64, payloadLen);
          out.textContent = plaintext;
          out.classList.remove('content-loading');
        }} catch (e) {{
          out.textContent = "Decryption failed: " + e.message;
          out.style.color = "#ff4444";
        }}
      }}

      // Delayed decryption: ensure functions are defined before execution
      setTimeout(() => {{
        window.onload = decryptOne;
      }}, 1);
    </script>
  </body>
</html>
"""


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
