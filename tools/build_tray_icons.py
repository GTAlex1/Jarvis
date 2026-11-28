"""Render fat-stroke, transparent tray artwork. Requires Inkscape and Pillow."""
from io import BytesIO
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/tray"
OUT.mkdir(parents=True, exist_ok=True)
MOTIFS = {
    "waiting": ("#00E5FF", "En espera", 'M22 36q5-8 10 0 M40 36q5-8 10 0', 'M64 60h0'),
    "listening": ("#A855F7", "Escuchando", 'M23 29v8 M31 29v8 M41 29v8 M49 29v8', 'M58 61v-5 M64 66V51 M70 61v-5'),
    "processing": ("#3B82F6", "Procesando", 'M22 33h7 M39 33h3 M47 33h3', 'M60 60h0 M67 60h0'),
    "executing": ("#22E38A", "Ejecutando", 'M22 37l6-8 5 8 M39 37l6-8 5 8', 'M65 52l-6 9h5l-2 7 8-10h-6z'),
    "error": ("#FF5277", "Error", 'M23 27l3 5-3 5 M50 27l-3 5 3 5', 'M64 53v7 M64 66h0'),
    "muted": ("#9CA3AF", "Micrófono desactivado", 'M21 34h12 M39 34h12', 'M59 65l10-10'),
}
SIZES = (16, 24, 32, 48, 64, 128, 256)
images = {}
for state, (color, _, expression, indicator) in MOTIFS.items():
    badge = (f'<path d="{indicator}" fill="{color}"/>' if state == "executing"
             else f'<path d="{indicator}" fill="none" stroke="{color}" stroke-width="4.8" stroke-linecap="round"/>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 76 76" width="256" height="256">
  <path d="M9 32 11 9q1-5 5-2l12 10q8-3 16 0L56 7q4-3 5 2l2 23-3 13-6 14q-18 15-36 0l-6-14z"
        fill="#0B1020" stroke="#E5E7EB" stroke-width="2.6" stroke-linejoin="round"/>
  <path d="M14 24l3-11 8 7m22 0 8-7 3 11" stroke="{color}" stroke-width="3.5"
        stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  <rect x="7" y="32" width="7" height="16" rx="3" fill="{color}"/>
  <rect x="58" y="32" width="7" height="16" rx="3" fill="#A855F7"/>
  <rect x="13" y="22" width="46" height="27" rx="11" fill="#070B14" stroke="{color}" stroke-width="3"/>
  <path d="M19 28q4-4 12-4h17" fill="none" stroke="#E5E7EB" stroke-opacity=".30" stroke-width="1.8"/>
  <path d="{expression}" stroke="{color}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  <path d="M28 54h16" stroke="#E5E7EB" stroke-opacity=".66" stroke-width="2" stroke-linecap="round"/>
  <circle cx="64" cy="60" r="11" fill="#0B1020" stroke="{color}" stroke-width="2.4"/>
  {badge}
</svg>
'''
    vector = OUT / f"{state}.svg"
    vector.write_text(svg, encoding="utf-8")
    png = subprocess.check_output(["inkscape", str(vector), "--export-type=png", "--export-filename=-"])
    raster = Image.open(BytesIO(png)).convert("RGBA")
    raster.save(OUT / f"{state}.ico", format="ICO", sizes=[(size, size) for size in SIZES])
    images[state] = raster

preview = Image.new("RGB", (768, 325), "#0B1020")
draw = ImageDraw.Draw(preview)
draw.rectangle((0, 239, 767, 324), fill="#E5E7EB")
font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
title = ImageFont.truetype(font, 25)
label_font = ImageFont.truetype(font, 15)
draw.text((24, 18), "JARVIS · Estados de la bandeja", font=title, fill="#E5E7EB")
for i, (state, (color, label, _, _)) in enumerate(MOTIFS.items()):
    x = 65 + 127 * i
    avatar = images[state].resize((88, 88), Image.Resampling.LANCZOS)
    preview.paste(avatar, (x - 44, 72), avatar)
    if state == "muted":
        label = "Micrófono\ndesactivado"
    draw.multiline_text((x, 176), label, anchor="ma", align="center", font=label_font, fill="#E5E7EB")
    for size, offset in ((16, -29), (24, -9), (32, 19)):
        small = images[state].resize((size, size), Image.Resampling.LANCZOS)
        preview.paste(small, (x + offset, 267 + (32-size)//2), small)
preview.save(ROOT / "docs/tray-preview.png", optimize=True)
