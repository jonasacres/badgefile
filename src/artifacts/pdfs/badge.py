from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

from random import randrange
from copy import copy
import os

class Badge:
  def __init__(self, attendee):
    self.attendee = attendee

  def path(self):
    info = self.attendee.info()
    return f"artifacts/badges/{info['name_family']}-{info['name_given']}-{self.attendee.id()}.pdf"
  
  def generate(self):
    BadgeRenderer(self).draw()
    return self

  def upload(self):
    # upload the badge to the Google Drive
    pass

class BadgeRenderer:
  # all the badge generation stuff has to go in here...
  # print onto Avery 8422 stock (6" x 4.25" -- has two badges per sheet, mirror them)

  # badge top:    1-1/2
  # badge bottom: 7-1/2
  # badge1 left:  4-1/4
  # ticket0 bottom: 9
  # ticket1 bottom: 10-1/2
  # 
  # badge shows:
  #   - background image (different versions depending on title/role)
  #   - congress logo
  #   - name (BIG letters)
  #   - rating (less big, but still big)
  #   - AGA number
  #   - city, state
  #   - flag for country
  #   - other flags for languages
  #   - title
  #   - go problem?

  def __init__(self, badge):
    self.badge = badge
    self.attendee = badge.attendee
    self.path = badge.path()

  def draw(self):
    # Create parent directories for the badge file if they don't exist
    os.makedirs(os.path.dirname(self.path), exist_ok=True)
    
    # Initialize the canvas and layout the badge
    self.layout()
    self.main_box.draw()
    self.canvas.showPage()
    self.canvas.save()
    return self
  
  def layout(self):
    # the main box covers the left half of a page and includes the badge, tearaway tickets, etc.
    self.canvas = canvas.Canvas(self.path, pagesize=(8.5*inch, 11*inch))
    self.main_box = InsetBox(0, 0, 4.25*inch, 11.0*inch, canvas=self.canvas)
    self.margin_size = 0.125*inch

    print(f"Main box origin: ({self.main_box.print_coords()[0]}, {self.main_box.print_coords()[1]})")
    print(f"Main box dimensions: {self.main_box.width} x {self.main_box.height}")

    # the badge area is the region of the page that is perforated to be torn off and stuffed in the badge holder
    self.badge_box = self.main_box.inset(0, 1.5*inch, 4.25*inch, 6.0*inch)
    self.badge_box.add_leaf_rounded_rect(colors.white, colors.black, 0.125 * inch, 4.0)
    self.layout_background()

    # next_y = self.layout_logo(self.margin_size).bottom()
    # next_y = self.layout_info_section(next_y+self.margin_size).bottom()
    # next_y = self.layout_title_section(next_y+self.margin_size).bottom()
    # next_y = self.layout_title_section(next_y+self.margin_size).bottom()

    return self
  
  def layout_background(self):
    self.main_box \
        .inset(0, 0, self.badge_box.width, self.badge_box.height) \
        .add_leaf_image_centered("src/static/badge_art/2024-player.png")

  def layout_logo(self, y):
    logo_height = 1.0 * inch
    logo_width  = 5/4 * logo_height
    logo_enclosure = self.main_box.inset(0, y, logo_width, logo_height)
    logo_enclosure.add_leaf_image_centered("src/static/logos/2025-congress-logo.png")
    return logo_enclosure
  
  def layout_info_section(self, y):
    info = self.attendee.info()
    info_height = 4.0*inch

    city_state = "%s, %s" % (info["city"], info["state"])

    info_enclosure = self.main_box.inset(0.5*inch, y, self.main_box.width, info_height)
    info_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    info_enclosure.add_leaf_text_centered(info["name_given"], style(36, colors.black, bold=True), y=0.5*inch)
    info_enclosure.add_leaf_text_centered(info["name_family"], style(28, colors.black, bold=True), y=1.0*inch)
    info_enclosure.add_leaf_text_centered(str(self.attendee.id()), style(24, colors.red, bold=True), y=1.75*inch)
    info_enclosure.add_leaf_text_centered(city_state, style(20, colors.black), y=2.35*inch)
    info_enclosure.add_leaf_text_centered(self.attendee.badge_rating(), style(48, colors.black, bold=True), y=3.75*inch)

    return info_enclosure
  
  def layout_title_section(self, y):
    title_height = 0.5*inch
    title_enclosure = self.main_box.inset(0.5*inch, y, self.main_box.width, title_height)
    title_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    title_enclosure.add_leaf_text_centered(self.attendee.title(), style(28, colors.black, bold=True), y=0.125*inch) # TODO: bold

    return title_enclosure

  def layout_country_flag(self, box):
    pass

  def layout_language_flags(self, box):
    pass

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
  
  def print_coords(self, width=0, height=0):
    x, y = self.absolute_coords()
    return [x + width, 11.0*inch - y + height] # TODO: read the page height from self.canvas

  def add_leaf_rounded_rect(self, fill_color, stroke_color, stroke_width, corner_radius):
    inset = self.inset(0, 0, self.width, self.height)
    
    def draw_the_rect(canvas):
      canvas.setFillColor(fill_color)
      canvas.setStrokeColor(stroke_color)
      canvas.setLineWidth(stroke_width)

      print(f"Rectangle origin: ({inset.print_coords()[0]}, {inset.print_coords()[1]})")
      print(f"Rectangle dimensions: {inset.width} x {inset.height}")

      canvas.roundRect(
          *inset.print_coords(),
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
      canvas.drawString(x - offset_factor*text_width, y, text)

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
      img_width = self.height * img_aspect_ratio
      img_height = self.height

    img_x = 0.5 * (self.width - img_width)
    img_y = 0.5 * (self.height - img_height)

    inset = self.inset(img_x, img_y, img_width, img_height)
    
    def draw_the_image(canvas):
      img_bottom, img_left = inset.print_coords()
      canvas.drawImage(img_reader, img_bottom, img_left, width=img_width, height=img_height, mask='auto')

    inset.draw_func = lambda canvas: draw_the_image(canvas)
    
    return self

  def inset(self, x, y, width, height):
    new_inset = InsetBox(x, y, width, height, self)
    self.insets.append(new_inset)
    return new_inset
  
  def bottom(self):
    return self.print_coords()[1]

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
