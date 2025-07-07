from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

import os
import io
from pylibdmtx.pylibdmtx import encode
from PIL import Image as PILImage

from artifacts.pdfs.inset_box import InsetBox, style, font_size_for_width, find_and_register_noto_cjk_fonts

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

  def already_exists(self):
    return os.path.exists(self.path()) and self._has_correct_hash()
  
  def _has_correct_hash(self):
    """Check if the existing PDF has the correct badge hash in its metadata."""
    try:
      from PyPDF2 import PdfReader
      reader = PdfReader(self.path())
      metadata = reader.metadata
      if metadata and metadata.get('/Title'):
        return self.attendee.badge_hash() in metadata['/Title']
      return False
    except Exception:
      # If we can't read the PDF or metadata, assume it needs regeneration
      return False

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
    
    # Register CJK fonts at the start
    find_and_register_noto_cjk_fonts()

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
    self.set_metadata()
        
    self.main_box = InsetBox(0, 0.5*inch, 4.25*inch, 9.0*inch, canvas=self.canvas)
    self.margin_size = 0.125*inch

    # the badge area is the region of the page that is perforated to be torn off and stuffed in the badge holder
    self.badge_box = self.main_box.inset(0, 3.0*inch, 4.25*inch, 6.0*inch)
    self.badge_box.add_leaf_rounded_rect(colors.white, colors.lightgrey, 1.0/64.0 * inch, 0.0)
    self.layout_background()

    next_y = self.badge_box.height - self.margin_size
    next_y -= self.layout_logo(next_y).height + self.margin_size
    next_y -= self.layout_info_section(next_y).height + self.margin_size
    next_y -= self.layout_title_section(next_y).height + self.margin_size
    
    return self
  
  def set_metadata(self):
    # Set PDF metadata including badge hash
    from datetime import datetime
    import time
    
    self.canvas.setTitle(f"2025 US Go Congress Badge - {self.attendee.id()} - {self.attendee.badge_hash()}")
    self.canvas.setAuthor("American Go Association")
    self.canvas.setSubject("Attendee Badge")
    self.canvas.setCreator("Badgefile")
    self.canvas.setProducer("ReportLab")
    
    # Add custom metadata for badge hash
    info = self.attendee.final_info()
    name_given = info.get('name_given', '')
    name_family = info.get('name_family', '')
    attendee_name = f"{name_given} {name_family}".strip()
    
    # Get current timestamp with timezone
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S %z")
    
    # Set keywords metadata to include badge hash and timestamp
    keywords = f"US Go Congress 2025, Austin TX, Badge, {attendee_name}, {self.attendee.id()}, {self.attendee.badge_hash()}, Generated: {current_time}"
    self.canvas.setKeywords(keywords)

  
  def layout_background(self):
    self.badge_box \
        .add_leaf_image_centered(f"src/static/badge_art/2025-{self.attendee.badge_type()}.png")

  def layout_logo(self, y):
    logo_height = 1.0 * inch
    logo_width  = 5/4 * logo_height
    logo_enclosure = self.badge_box.inset(0, y - logo_height, self.badge_box.width, logo_height)
    logo_enclosure.add_leaf_image_centered("src/static/logos/2025-congress-logo.png")
    return logo_enclosure
  
  def layout_info_section(self, y):
    info = self.attendee.final_info()
    info_height = 4.0*inch

    name_given = info.get('name_given')
    name_family = info.get('name_family')

    city = str(info.get('city') or "")
    state = str(info.get('state') or "")

    city_state = ", ".join(filter(lambda x: x and x.strip(), [city, state]))

    info_enclosure = self.badge_box.inset(0.5*inch, y - info_height, self.badge_box.width-1.0*inch, info_height)
    info_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    info_enclosure.add_leaf_text_centered(name_given, style(36, colors.black, bold=True), y=3.5*inch)
    info_enclosure.add_leaf_text_centered(name_family, style(28, colors.black, bold=True), y=3.0*inch)
    info_enclosure.add_leaf_text_centered("#" + str(self.attendee.id()), style(24, colors.red, bold=True), y=2.25*inch)
    info_enclosure.add_leaf_text_centered(city_state, style(20, colors.black), y=1.65*inch)
    info_enclosure.add_leaf_text_centered(self.attendee.badge_rating(), style(48, colors.black, bold=True), y=0.25*inch)

    self.layout_scannable(info_enclosure)
    self.layout_country_flag(info_enclosure)
    self.layout_banquet_mark(info_enclosure)
    self.layout_language_pips(info_enclosure)

    return info_enclosure
  
  def layout_title_section(self, y):
    title_height = 0.5*inch
    title_enclosure = self.badge_box.inset(0.5*inch, y - title_height, self.badge_box.width - 1.0*inch, title_height)
    title_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    title_enclosure.add_leaf_text_centered(self.attendee.title(), style(28, colors.black, bold=True), y=0.125*inch, max_width=title_enclosure.width-2*self.margin_size) # TODO: bold

    return title_enclosure

  def layout_scannable(self, box):
    scan_height = 0.65*inch
    scan_enclosure = box.inset(0, 0.85*inch, box.width, scan_height)
    
    # Generate Data Matrix with attendee ID
    data = self.attendee.datamatrix_content('b')
    encoded = encode(data, size='14x14')
    
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
    info = self.attendee.final_info()
    country = info.get('country').lower()
    if not country:
      return

    flag_img = f"src/static/flags/{country}.png"

    img = Image.open(flag_img)
    width_px, height_px = img.size
    aspect_ratio = height_px / width_px
    

    flag_width = 0.8*inch
    flag_height = flag_width * aspect_ratio
    flag_box = box.inset(0.15*inch, 0.25*inch, flag_width, flag_height)
    flag_box.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 0.0)
    flag_box.add_leaf_image_centered(flag_img)
  
  def layout_banquet_mark(self, box):
    if self.attendee.is_attending_banquet():
      mark_box = box.inset(0.15*inch, 0.95*inch, 0.8*inch, 0.8*inch)
      mark_box.add_leaf_text_centered("Banquet", style(18, bold=True), y=0)

  def layout_language_pips(self, box):
    pip_spacing = 0.05*inch
    pip_width = 0.8*inch
    pip_height = 0.4*inch

    codes = {
      "english": ("EN", style(18)),
      "korean": ("한글", style(18, bold=False, font_name="NotoSansKR-Regular")),
      "chinese": ("中文", style(18, bold=True, font_name="NotoSansSC-ExtraBold")),
      "japanese": ("日本語", style(18, bold=False, font_name="NotoSansJP-Regular")),
      "spanish": ("Español", style(18)),
    }

    lang_box = box.inset(2.3 * inch, 0.25 *inch, 2*pip_width+pip_spacing, 3*pip_height+2*pip_spacing)
    languages = self.attendee.languages()
    
    count = 0
    for language in languages:
      pip_code, font_style = codes[language]
      pip_x = 0 # (count %  2) * (pip_width  + pip_spacing)
      pip_y = (count) * (pip_height + pip_spacing)

      y_base = 0.10*inch
      if language == "spanish":
        y_base += 0.025*inch
      
      pip_box = lang_box.inset(pip_x, pip_y, pip_width, pip_height)
      pip_box.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 0.04*inch)
      pip_box.add_leaf_text_centered(pip_code, font_style, y=y_base, max_width=pip_box.width-0.1*inch)

      count += 1

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
      "spanish":  ["src/static/flags/mex.png", 0 * hz_space, 2 * vt_space],
    }

    if self.attendee.final_info()['country'].lower() == 'twn':
      lang_defs['chinese'][0] = "src/static/flags/twn.png" # ooof

    lang_box = box.inset(2.3 * inch, 0.25 *inch, 2*hz_space, 3*vt_space)
    languages = self.attendee.languages()

    count = 0
    for language in languages:
      flag_img, flag_x, flag_y = lang_defs[language]
      flag_x = (count %  2) * hz_space
      flag_y = (count // 2) * vt_space

      box = lang_box.inset(flag_x, flag_y, flag_width, flag_height)
      box.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 0.0)
      box.add_leaf_image_centered(flag_img)

      count += 1

