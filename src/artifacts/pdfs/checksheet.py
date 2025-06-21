from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

import os
import io
from pylibdmtx.pylibdmtx import encode
from PIL import Image as PILImage

from inset_box import InsetBox

class Checksheet:
  def __init__(self, attendee):
    self.attendee = attendee
  
  def generate(self):
    pass

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
    self.badge_box.add_leaf_rounded_rect(colors.white, colors.lightgrey, 1.0/64.0 * inch, 0.0)
    self.layout_background()

    next_y  = self.badge_box.height - self.margin_size
    next_y -= self.layout_logo(next_y).height + self.margin_size
    next_y -= self.layout_info_section(next_y).height + self.margin_size
    next_y -= self.layout_title_section(next_y).height + self.margin_size
    
    return self