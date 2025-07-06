#!/usr/bin/env python

import pathlib
import sys
src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

import os
import io
from pylibdmtx.pylibdmtx import encode
from PIL import Image as PILImage


from artifacts.pdfs.inset_box import find_and_register_noto_cjk_fonts, InsetBox, style

codes = {
  "english": ("EN", style(18)),
  "korean": ("한글", style(18, bold=False, font_name="NotoSansKR-Regular")),
  "chinese": ("中文", style(18, bold=True, font_name="NotoSansSC-ExtraBold")),
  "japanese": ("日本", style(18, bold=False, font_name="NotoSansJP-Regular")),
  "spanish": ("ES", style(18)),
}

canvas = canvas.Canvas("artifacts/cjk-test.pdf", pagesize=(8.5*inch, 11*inch))
main_box = InsetBox(0, 0, 8.5*inch, 11.0*inch, canvas=canvas)

find_and_register_noto_cjk_fonts()

count = 0
for lang_name, (text, font_style) in codes.items():
  count += 1
  vspace = 1.0*inch
  
  # Try to use the specific font, fall back to generic CJK font if needed
  text_style = font_style
  main_box.add_leaf_text_centered(text, text_style, 0.5*main_box.width, main_box.height - vspace*count)

main_box.draw()
canvas.showPage()
canvas.save()