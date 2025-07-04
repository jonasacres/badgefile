from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

import subprocess
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from copy import copy

def find_and_register_noto_cjk_fonts():
    """
    Find and register Noto CJK fonts using fc-list command.
    This function should be called once before using CJK fonts.
    """
    try:
        # Use fc-list to find Noto CJK fonts
        result = subprocess.run(['fc-list', ':family=Noto Sans CJK', 'file', 'style'], 
                               capture_output=True, text=True, check=True)
        
        font_mappings = {}
        
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            
            # Parse fc-list output format: /path/to/font.otf: Family:style
            parts = line.split(':')
            if len(parts) >= 3:
                font_path = parts[0].strip()
                style_info = parts[2].strip() if len(parts) > 2 else ""
                
                # Map different styles to ReportLab font names
                if 'Bold' in style_info and 'Italic' not in style_info:
                    font_name = 'NotoSansCJK-Bold'
                elif 'Regular' in style_info or 'Medium' in style_info:
                    font_name = 'NotoSansCJK-Regular'
                elif 'Light' in style_info:
                    font_name = 'NotoSansCJK-Light'
                else:
                    continue  # Skip other styles for now
                
                # Only register if we haven't seen this font name yet
                if font_name not in font_mappings and os.path.exists(font_path):
                    font_mappings[font_name] = font_path
        
        # Register the fonts with ReportLab
        for font_name, font_path in font_mappings.items():
            try:
                # Check if font is already registered
                if font_name not in pdfmetrics._fonts:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    print(f"Registered font: {font_name} from {font_path}")
            except Exception as e:
                print(f"Failed to register font {font_name}: {e}")
        
        # If we didn't find any fonts, try a more comprehensive search
        if not font_mappings:
            # Search for fonts that support multiple CJK languages
            languages = ['zh', 'ko', 'ja']  # Chinese, Korean, Japanese
            for lang in languages:
                try:
                    result = subprocess.run(['fc-list', f':lang={lang}', 'file', 'family'], 
                                           capture_output=True, text=True, check=True)
                    
                    for line in result.stdout.strip().split('\n'):
                        if not line.strip():
                            continue
                        
                        parts = line.split(':')
                        if len(parts) >= 2:
                            font_path = parts[0].strip()
                            family_name = parts[1].strip() if len(parts) > 1 else ""
                            
                            if ('Noto' in family_name or 'CJK' in family_name) and os.path.exists(font_path):
                                try:
                                    font_name = f'NotoSansCJK-Bold-{lang}'
                                    if font_name not in pdfmetrics._fonts:
                                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                                        print(f"Registered fallback font: {font_name} from {font_path}")
                                        
                                        # Also register as generic names if not already registered
                                        if 'NotoSansCJK-Bold' not in pdfmetrics._fonts:
                                            pdfmetrics.registerFont(TTFont('NotoSansCJK-Bold', font_path))
                                            print(f"Registered generic font: NotoSansCJK-Bold from {font_path}")
                                        if 'NotoSansCJK-Regular' not in pdfmetrics._fonts:
                                            pdfmetrics.registerFont(TTFont('NotoSansCJK-Regular', font_path))
                                            print(f"Registered generic font: NotoSansCJK-Regular from {font_path}")
                                        break
                                except Exception as e:
                                    continue
                except subprocess.CalledProcessError:
                    continue
                            
        return True
        
    except subprocess.CalledProcessError:
        print("fc-list command failed - fontconfig may not be available")
        return False
    except Exception as e:
        print(f"Error finding fonts: {e}")
        return False

class InsetBox:
  def __init__(self, x, y, width, height, parent=None, canvas=None):
    self.x = x 
    self.y = y
    self.height = height
    self.width = width
    self.parent = parent

    self.insets = []
    self.content = None
    if canvas is not None:
      self.canvas = canvas
    elif parent is not None:
      self.canvas = parent.canvas
    else:
      self.canvas = None

    self.draw_func = None

  def draw(self, canvas=None):
    if canvas is None:
      canvas = self.canvas
    
    canvas.saveState()
    for inset in self.insets:
      inset.draw()
    
    if self.draw_func is not None:
      self.draw_func(self.canvas)
    canvas.restoreState()

  def absolute_coords(self):
    x = y = 0
    box = self

    while box is not None:
      x += box.x
      y += box.y
      box = box.parent
    
    return [x, y]

  def add_leaf_rounded_rect(self, fill_color, stroke_color, stroke_width, corner_radius):
    inset = self.inset(0, 0, self.width, self.height)
    
    def draw_the_rect(canvas):
      canvas.setFillColor(fill_color)
      canvas.setStrokeColor(stroke_color)
      canvas.setLineWidth(stroke_width)

      canvas.roundRect(
          *inset.absolute_coords(),
          inset.width,
          inset.height,
          corner_radius,
          stroke=1,
          fill=1)
      
    inset.draw_func = lambda canvas: draw_the_rect(canvas)
    self.insets.append(inset)
    return self
  
  def add_leaf_line(self, stroke_color, stroke_width, x0, y0, x1, y1):
    inset = self.inset(x0, y0, x1-x0, y1-y0)

    def draw_the_line(canvas):
      canvas.setStrokeColor(stroke_color)
      canvas.setLineWidth(stroke_width)
      canvas.line(*inset.absolute_coords(), inset.absolute_coords()[0] + inset.width, inset.absolute_coords()[1] + inset.height)
    
    inset.draw_func = lambda canvas: draw_the_line(canvas)
    self.insets.append(inset)
    return self
  
  def add_leaf_text_left(self, text, style, x, y, max_width = None):
    self._add_leaf_text(text, style, x, y, max_width, 0.0)
    return self

  def add_leaf_text_right(self, text, style, x, y, max_width = None):
    if max_width is None:
      max_width = x
    self._add_leaf_text(text, style, x, y, max_width, 1.0)
    return self
    

  def add_leaf_text_centered(self, text, style, x=None, y=None, max_width=None):
    if max_width is None:
      max_width = self.width
      
    if x is None:
      x = 0.5 * self.width
    if y is None:
      y = 0.5 * self.height
    
    self._add_leaf_text(text, style, x, y, max_width, 0.5)
    return self
  
  def _add_leaf_text(self, text, style, x, y, max_width, offset_factor):
    inset_width = self.width - x
    inset_height = self.height - y
    inset = self.inset(x, y, inset_width, inset_height)
    if max_width is None:
      max_width = inset_width

    def draw_the_text(canvas):
      effective_size = font_size_for_width(text, style, max_width, canvas)
      text_width = canvas.stringWidth(text, style.fontName, effective_size)
      
      canvas.setFont(style.fontName, effective_size)
      canvas.setFillColor(style.textColor if hasattr(style, "textColor") else colors.black)
      canvas.drawString(self.absolute_coords()[0] + x - offset_factor*text_width, self.absolute_coords()[1] + y, text)

    inset.draw_func = lambda canvas: draw_the_text(canvas)

    return self

  def add_leaf_image_centered(self, image_path):
    img = Image.open(image_path)
    img_reader = ImageReader(img)
    width_px, height_px = img.size

    img_aspect_ratio = height_px / width_px

    # if we fill the width, does the image spill out vertically?
    img_width = self.width
    img_height = self.width * img_aspect_ratio
    
    if img_height > self.height:
      # yes; better fit to height then
      img_height = self.height
      img_width = self.height / img_aspect_ratio

    # Center the image horizontally and vertically within the InsetBox
    img_x = 0.5 * (self.width - img_width)
    img_y = 0.5 * (self.height - img_height)

    inset = self.inset(img_x, img_y, img_width, img_height)
    
    def draw_the_image(canvas):
      img_left, img_bottom = inset.absolute_coords()
      canvas.drawImage(img_reader, img_left, img_bottom, width=img_width, height=img_height, mask='auto')

    inset.draw_func = lambda canvas: draw_the_image(canvas)
    
    return self

  def inset(self, x, y, width, height):
    new_inset = InsetBox(x, y, width, height, self)
    self.insets.append(new_inset)
    return new_inset
  
  def bottom(self):
    return self.absolute_coords()[1]
  
  def top(self):
    return self.absolute_coords()[1] + self.height
  
  def left(self):
    return self.absolute_coords()[0]
  
  def right(self):
    return self.absolute_coords()[0] + self.width

def style(font_size, color="black", bold=False, font_name=None):
  from reportlab.lib.styles import getSampleStyleSheet
  styles = getSampleStyleSheet()
  style = copy(styles['Normal'])
  style.fontSize = font_size
  style.textColor = color
  
  if font_name is not None:
    style.fontName = font_name
  elif bold:
    style.fontName = 'Helvetica-Bold'
  
  return style

def font_size_for_width(text, style, max_width, canvas, start_size=None):
  if start_size is None:
    start_size = style.fontSize
  if max_width is None:
    return start_size

  effective_size = start_size
  text_width = canvas.stringWidth(text, style.fontName, effective_size)
  while text_width > max_width:
    effective_size -= 1
    text_width = canvas.stringWidth(text, style.fontName, effective_size)
    
  return effective_size
