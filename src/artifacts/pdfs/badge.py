from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

from random import randrange
from copy import copy
import os
import io
from pylibdmtx.pylibdmtx import encode
from PIL import Image as PILImage

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
  # or taken from the bottom of the page:
  # ticket1 bottom: 0.5"
  # ticket0 bottom: 2"
  # badge bottom: 3.5"
  # badge top: 9.5"
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

    # draw the copy so the badge is double-sided
    self.main_box.x += 4.25*inch
    self.main_box.draw()

    self.canvas.showPage()
    self.canvas.save()
    return self
  
  def layout(self):
    # the main box covers the left half of a page and includes the badge, tearaway tickets, etc.
    self.canvas = canvas.Canvas(self.path, pagesize=(8.5*inch, 11*inch))
    self.main_box = InsetBox(0, 0.5*inch, 4.25*inch, 9.0*inch, canvas=self.canvas)
    self.margin_size = 0.125*inch

    # the badge area is the region of the page that is perforated to be torn off and stuffed in the badge holder
    self.badge_box = self.main_box.inset(0, 3.0*inch, 4.25*inch, 6.0*inch)
    self.badge_box.add_leaf_rounded_rect(colors.white, colors.black, 1.0/16.0 * inch, 4.0)
    self.layout_background()

    next_y = self.badge_box.height - self.margin_size
    next_y -= self.layout_logo(next_y).height + self.margin_size
    next_y -= self.layout_info_section(next_y).height + self.margin_size
    next_y -= self.layout_title_section(next_y).height + self.margin_size
    
    return self
  
  def layout_background(self):
    self.badge_box \
        .add_leaf_image_centered("src/static/badge_art/2024-player.png")

  def layout_logo(self, y):
    logo_height = 1.0 * inch
    logo_width  = 5/4 * logo_height
    logo_enclosure = self.badge_box.inset(0, y - logo_height, self.badge_box.width, logo_height)
    logo_enclosure.add_leaf_image_centered("src/static/logos/2025-congress-logo.png")
    return logo_enclosure
  
  def layout_info_section(self, y):
    info = self.attendee.info()
    info_height = 4.0*inch

    city_state = "%s, %s" % (info["city"], info["state"])

    info_enclosure = self.badge_box.inset(0.5*inch, y - info_height, self.badge_box.width-1.0*inch, info_height)
    info_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    info_enclosure.add_leaf_text_centered(info["name_given"], style(36, colors.black, bold=True), y=3.5*inch)
    info_enclosure.add_leaf_text_centered(info["name_family"], style(28, colors.black, bold=True), y=3.0*inch)
    info_enclosure.add_leaf_text_centered("#" + str(self.attendee.id()), style(24, colors.red, bold=True), y=2.25*inch)
    info_enclosure.add_leaf_text_centered(city_state, style(20, colors.black), y=1.65*inch)
    info_enclosure.add_leaf_text_centered(self.attendee.badge_rating(), style(48, colors.black, bold=True), y=0.25*inch)

    self.layout_scannable(info_enclosure)
    self.layout_country_flag(info_enclosure)
    self.layout_language_flags(info_enclosure)

    return info_enclosure
  
  def layout_title_section(self, y):
    title_height = 0.5*inch
    title_enclosure = self.badge_box.inset(0.5*inch, y - title_height, self.badge_box.width - 1.0*inch, title_height)
    title_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    title_enclosure.add_leaf_text_centered(self.attendee.title(), style(28, colors.black, bold=True), y=0.125*inch) # TODO: bold

    return title_enclosure

  def layout_scannable(self, box):
    scan_height = 0.5*inch
    scan_enclosure = box.inset(0, 0.90*inch, box.width, scan_height)
    
    # Generate Data Matrix with attendee ID
    data = str(self.attendee.id()).encode('utf8')
    encoded = encode(data, size='10x10')
    
    # Convert to PIL Image
    dm_img = PILImage.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
    
    # Create a BytesIO buffer to hold the image data
    buffer = io.BytesIO()
    dm_img.save(buffer, format="PNG")
    buffer.seek(0)
    
    # Create an ImageReader from the buffer
    img_reader = ImageReader(buffer)
    
    # Calculate dimensions and position for centered placement
    dm_size = min(scan_height * 0.9, scan_enclosure.width * 0.3)
    dm_x = (scan_enclosure.width - dm_size) / 2
    dm_y = (scan_height - dm_size) / 2
    
    # Draw the Data Matrix
    dm_box = scan_enclosure.inset(dm_x, dm_y, dm_size, dm_size)
    
    def draw_datamatrix(canvas):
      img_left, img_bottom = dm_box.absolute_coords()
      canvas.drawImage(img_reader, img_left, img_bottom, width=dm_size, height=dm_size)
    
    dm_box.draw_func = lambda canvas: draw_datamatrix(canvas)
    
    return scan_enclosure
  
  def layout_country_flag(self, box):
    country = self.attendee.info()["country"].lower()
    flag_img = f"src/static/flags/{country}.png"

    img = Image.open(flag_img)
    width_px, height_px = img.size
    aspect_ratio = height_px / width_px
    

    flag_width = 0.8*inch
    flag_height = flag_width * aspect_ratio
    flag_box = box.inset(0.15*inch, 0.25*inch, flag_width, flag_height)
    flag_box.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 0.0)
    flag_box.add_leaf_image_centered(flag_img)

  def layout_language_flags(self, box):
    flag_width = 0.4 * inch
    flag_height = flag_width / 1.5
    flag_margin = 0.05 * inch

    hz_space = flag_width + flag_margin
    vt_space = flag_height + flag_margin

    lang_defs = {
      "english":  ["src/static/flags/uk.png",  0 * hz_space, 0 * vt_space],
      "korean":   ["src/static/flags/kor.png", 1 * hz_space, 0 * vt_space],
      "chinese":  ["src/static/flags/chn.png", 0 * hz_space, 1 * vt_space],
      "japanese": ["src/static/flags/jpn.png", 1 * hz_space, 1 * vt_space],
      "spanish":  ["src/static/flags/spn.png", 0 * hz_space, 2 * vt_space],
    }

    lang_box = box.inset(2.3 * inch, 0.25 *inch, 2*hz_space, 3*vt_space)
    # langauges = self.attendee.languages()
    languages = [
      "english",
      "japanese",
      "korean",
      "chinese",
      "spanish"
    ]

    for language in languages:
      flag_img, flag_x, flag_y = lang_defs[language]
      box = lang_box.inset(flag_x, flag_y, flag_width, flag_height)
      box.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 0.0)
      box.add_leaf_image_centered(flag_img)

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
