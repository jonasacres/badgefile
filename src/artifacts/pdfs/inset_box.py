from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

from copy import copy

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
  
  def add_leaf_text_left(self, text, style, x, y, max_width = None):
    self._add_leaf_text(text, style, x, y, max_width, 0.0)
    return self

  def add_leaf_text_right(self, text, style, x, y, max_width = None):
    self._add_leaf_text(text, style, x, y, max_width, 1.0)
    return self

  def add_leaf_text_centered(self, text, style, x=None, y=None, max_width=None):
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
      canvas.setFillColor(style.fillColor if hasattr(style, "fillColor") else colors.black)
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

def style(font_size, color="black", bold=False):
  from reportlab.lib.styles import getSampleStyleSheet
  styles = getSampleStyleSheet()
  style = copy(styles['Normal'])
  style.fontSize = font_size
  style.textColor = color
  if bold:
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
