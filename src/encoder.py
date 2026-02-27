#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Encoder module for AES-GCM encryption and LSB steganography.

This module provides functions to:
1. Encrypt plaintext using AES-GCM
2. Embed encrypted data into PNG images using LSB steganography
3. Batch process multiple articles
"""

import os
import struct
import base64
from typing import Tuple, List

from PIL import Image
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# -------------------------- Core Utility Functions --------------------------

def aes_gcm_encrypt(plaintext: str, key: bytes) -> Tuple[bytes, bytes]:
    """
    Encrypt plaintext using AES-GCM.

    Args:
        plaintext: The text to encrypt
        key: AES key (16 or 32 bytes for AES-128/256)

    Returns:
        Tuple of (nonce, ciphertext with authentication tag)
    """
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # GCM standard: 12-byte nonce
    pt_bytes = plaintext.encode("utf-8")
    ct = aesgcm.encrypt(nonce, pt_bytes, None)
    return nonce, ct


def bytes_to_lsb_bits(data: bytes) -> List[int]:
    """
    Convert byte stream to list of 0/1 bits for LSB steganography.

    Args:
        data: Bytes to convert

    Returns:
        List of bits (0 or 1)
    """
    bits = []
    for b in data:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    return bits


def embed_data_in_png(input_png: str, output_png: str, data: bytes) -> None:
    """
    Embed binary data into PNG image using LSB steganography.

    Modifies the least significant bit of each RGB channel to store data.

    Args:
        input_png: Path to carrier image
        output_png: Path to save encoded image
        data: Binary data to embed

    Raises:
        FileNotFoundError: If carrier image doesn't exist
        ValueError: If data is too large for the image
    """
    # Ensure output directory exists
    out_dir = os.path.dirname(output_png) or "."
    os.makedirs(out_dir, exist_ok=True)

    # Open image and convert to RGB (compatible with RGBA)
    if not os.path.exists(input_png):
        raise FileNotFoundError(f"Carrier image not found: {input_png}")

    img = Image.open(input_png).convert("RGB")
    pixels = img.load()
    w, h = img.size

    bits = bytes_to_lsb_bits(data)
    bit_len = len(bits)
    max_bits = w * h * 3  # 3 channels per pixel, 1 bit per channel

    if bit_len > max_bits:
        raise ValueError(
            f"Data too large! Need {bit_len} bits, image only supports {max_bits} bits. "
            "Use a larger PNG image."
        )

    # Write LSB to each pixel
    bit_idx = 0
    for y in range(h):
        for x in range(w):
            if bit_idx >= bit_len:
                break

            r, g, b = pixels[x, y]

            # R channel
            r = (r & 0xFE) | bits[bit_idx]
            bit_idx += 1
            if bit_idx >= bit_len:
                pixels[x, y] = (r, g, b)
                break

            # G channel
            g = (g & 0xFE) | bits[bit_idx]
            bit_idx += 1
            if bit_idx >= bit_len:
                pixels[x, y] = (r, g, b)
                break

            # B channel
            b = (b & 0xFE) | bits[bit_idx]
            bit_idx += 1

            pixels[x, y] = (r, g, b)

        if bit_idx >= bit_len:
            break

    img.save(output_png, format="PNG")
    print(f"Encoded image saved: {output_png}")


def encrypt_and_embed(plaintext: str, key: bytes, input_png: str, output_png: str) -> int:
    """
    Encrypt plaintext and embed into PNG image.

    Payload structure: [12-byte nonce][4-byte ciphertext length][ciphertext with tag]

    Args:
        plaintext: Text to encrypt and embed
        key: AES key
        input_png: Path to carrier image
        output_png: Path to save encoded image

    Returns:
        Total payload length in bytes
    """
    nonce, ct = aes_gcm_encrypt(plaintext, key)
    ct_len = len(ct)
    payload = nonce + struct.pack(">I", ct_len) + ct
    embed_data_in_png(input_png, output_png, payload)
    return len(payload)


# -------------------------- Main Execution --------------------------

if __name__ == "__main__":
    # Configuration
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    INPUT_PNG = os.path.join(BASE_DIR, "encryption", "carrier", "base_image.png")
    OUTPUT_PNG_DIR = os.path.join(BASE_DIR, "encryption", "carrier", "encoded")
    KEY_INFO_FILE = os.path.join(BASE_DIR, "encryption", "key", "key_mapping.txt")
    ARTICLE_DIR = os.path.join(BASE_DIR, "data", "articles")
    AES_BIT_LENGTH = 128  # AES key length (128 or 256)

    # Ensure directories exist
    os.makedirs(OUTPUT_PNG_DIR, exist_ok=True)
    os.makedirs(ARTICLE_DIR, exist_ok=True)

    # Get all txt files in article directory
    txt_files = [f for f in os.listdir(ARTICLE_DIR) if f.lower().endswith(".txt")]
    if not txt_files:
        print(f"Warning: No txt files found in {ARTICLE_DIR}")
        exit(0)

    # Write article-image-key mapping (overwrite to ensure latest)
    with open(KEY_INFO_FILE, "w", encoding="utf-8") as f:
        f.write("ARTICLE_NAME\tIMAGE_PATH\tAES_KEY_B64\tPAYLOAD_LEN\n")

        print("===== Starting batch encryption and embedding =====")
        for txt_file in txt_files:
            # Read article content
            article_path = os.path.join(ARTICLE_DIR, txt_file)
            with open(article_path, "r", encoding="utf-8") as af:
                secret_text = af.read().strip()

            if not secret_text:
                print(f"Skipping empty file: {txt_file}")
                continue

            # Generate unique AES key for this article
            aes_key = AESGCM.generate_key(bit_length=AES_BIT_LENGTH)
            aes_key_b64 = base64.b64encode(aes_key).decode("utf-8")

            # Define output image path (same name as article, with .png extension)
            img_name = os.path.splitext(txt_file)[0] + ".png"
            output_png = os.path.join(OUTPUT_PNG_DIR, img_name)

            # Encrypt and embed
            try:
                payload_len = encrypt_and_embed(
                    plaintext=secret_text,
                    key=aes_key,
                    input_png=INPUT_PNG,
                    output_png=output_png
                )
                # Write mapping (tab-separated for easy parsing)
                f.write(f"{txt_file}\t{output_png}\t{aes_key_b64}\t{payload_len}\n")
                print(f"Processed: {txt_file} -> {img_name}")
            except Exception as e:
                print(f"Failed: {txt_file} - {str(e)}")

    print(f"\nBatch processing complete!")
    print(f"Key mapping file: {KEY_INFO_FILE}")
    print(f"Encoded images directory: {OUTPUT_PNG_DIR}")
