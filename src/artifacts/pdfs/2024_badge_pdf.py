# Copied over for reference. Don't try to use it with the 2025 code, since it is expecting a completely different kind of entity for badge_file and attendee!

from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from PIL import Image
from copy import copy
import os

class BadgePDF:
  def __init__(self, badge_file, attendee):
    self.badge_file = badge_file
    self.supervisor = badge_file.supervisor
    self.attendee = attendee
    self.log = self.supervisor.log

  def country_name_for_code(self, country_code):
    match country_code.lower():
      case "aus":
        return "Australia"
      case "can":
        return "Canada"
      case "chn":
        return "China"
      case "jpn":
        return "Japan"
      case "kor":
        return "Korea"
      case "nzl":
        return "New Zealand"
      case "pol":
        return "Poland"
      case "twn":
        return "Taiwan"
      case "usa":
        return "United States"
      case "cascadia":
        return "Cascadia"
      case "":
        return ""
      case _:
        self.log.error(f"Unrecognized country code {country_code} for attendee badge_aga_id={self.attendee['badge_aga_id']}, badge_top_name={self.attendee['badge_top_name']}, badge_bottom_name={self.attendee['badge_bottom_name']}")
        return country_code

  def background_for_status(self):
    match self.attendee["badge_type"].lower():
      case "pro":
        return "assets/backgrounds/space.png"
      case "vip":
        return "assets/backgrounds/red.png"
      case "staff":
        return "assets/backgrounds/blue.png"
      case "td":
        return "assets/backgrounds/green.png"
      case "np":
        return "assets/backgrounds/oranges.png"
      case "player":
        return "assets/backgrounds/wood.png"
      case _:
        self.log.error(f"Unrecognized badge status {self.attendee['badge_type']} for attendee badge_aga_id={self.attendee['badge_aga_id']}, badge_top_name={self.attendee['badge_top_name']}, badge_bottom_name={self.attendee['badge_bottom_name']}")
        return "assets/backgrounds/wood.png"
          
  def badge_status_line(self):
    if "badge_title" in self.attendee and len(self.attendee["badge_title"]) > 0:
      return self.attendee["badge_title"]
    
    match self.attendee["badge_type"].lower():
      case "pro":
        return "Go Professional"
      case "vip":
        return "VIP"
      case "staff":
        return "Volunteer"
      case "td":
        return "Tournament Director"
      case "np":
        return "Non-participant"
      case "player":
        return "Player"
      case _:
        self.log.error(f"Unrecognized badge status {self.attendee['badge_type']} for attendee badge_aga_id={self.attendee['badge_aga_id']}, badge_top_name={self.attendee['badge_top_name']}, badge_bottom_name={self.attendee['badge_bottom_name']}")
        return self.attendee["badge_type"]
          
  def center_text(self, text, c, style, centerx, maxwidth, y):
    effective_size = style.fontSize
    text_width = c.stringWidth(text, style.fontName, effective_size)
    while text_width > maxwidth:
      effective_size -= 1
      text_width = c.stringWidth(text, style.fontName, effective_size)
    
    c.setFont(style.fontName, effective_size)
    c.setFillColor(style.fillColor if hasattr(style, "fillColor") else colors.black)
    x = centerx - 0.5*text_width
    c.drawString(x, y, text)

  def filename(self):
    if self.attendee["memo"] == "blank":
      return "generated/badges/blank.pdf"
    
    if self.attendee["is_participant"]:
      if self.attendee["badge_bottom_name"] != "":
        return "generated/badges/badge %s, %s - %05d.pdf" % (self.attendee["badge_bottom_name"], self.attendee["badge_top_name"], self.attendee["badge_aga_id"])
      else:
        return "generated/badges/badge %s - %05d.pdf" % (self.attendee["badge_top_name"], self.attendee["badge_aga_id"])
    else:
      if self.attendee["badge_bottom_name"] != "":
        return "generated/badges/badge %s, %s - np.pdf" % (self.attendee["badge_bottom_name"], self.attendee["badge_top_name"])
      else:
        return "generated/badges/badge %s - np.pdf" % (self.attendee["badge_top_name"])

  def create_pdf(self):
    filename = self.filename()
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    self.log.debug(f"Generating PDF: {filename}")

    # Avery 8522 dimensions
    width, height = 8.5 * inch, 11 * inch

    # badge top:    1-1/2
    # badge bottom: 7-1/2
    # badge1 left:  4-1/4
    # ticket0 bottom: 9
    # ticket1 bottom: 10-1/2

    margin = 0
    bleedv  = 0
    bleedh  = 0

    index_left = 0.5*inch
    index_bottom = height - 1 * inch 

    badge_width  = 4.25 * inch
    badge_height = 6 * inch
    badge_bottom = 3.5 * inch + margin
    ticket0_bottom = 2 * inch
    ticket1_bottom = 0.5 * inch

    badge0_left  = margin
    badge1_left  = badge0_left + badge_width

    bg_bottom = badge_bottom - bleedv
    bg_width  = badge_width  + 2*bleedh
    bg_height = badge_height + 2*bleedv

    status_height = 0.5 * inch
    rect_status_space = 0.125 * inch
    status_bottom = badge_bottom + 0.125 * inch

    rect_margin = 0.5 * inch
    rect_bottom = rect_status_space + status_height + status_bottom
    rect_height = badge_height * 0.75 - rect_margin
    rect_width  = badge_width  - 2*rect_margin

    # Create a canvas object
    c = canvas.Canvas(filename, pagesize=(width, height))
    styles = getSampleStyleSheet()

    index_style = copy(styles['Title'])
    index_style.fontSize = 32
    
    c.setFont(index_style.fontName, index_style.fontSize)
    c.setFillColor(index_style.fillColor if hasattr(index_style, "fillColor") else colors.black)

    try:
      bf_index = self.badge_file.attendees.index(self.attendee) + 2
    except:
      bf_index = -1

    if self.attendee["memo"] == "blank":
      c.drawString(
        index_left,
        index_bottom,
        "blank %s" % (self.attendee["badge_type"])
      )
    else:
      c.drawString(
        index_left,
        index_bottom,
        "#%d   %s" % (
          bf_index,
          self.badge_file.listing_name(self.attendee)
        )
      )

    reglist_style = copy(styles['Normal'])
    reglist_style.fontSize = 14
    c.setFont(reglist_style.fontName, reglist_style.fontSize)
    c.drawString(
      index_left,
      index_bottom - 0.3*inch,
      "reg #%d" % (
        self.attendee["reglist_rownum"],
      )
    )


    for left in (badge0_left, badge1_left):
      # Draw the background image
      rect_left = left + rect_margin
      bg_left = left
      centerx = rect_left + 0.5*rect_width

      # draw the background (depends on status)
      background_img = self.background_for_status()
      c.drawImage(background_img, bg_left, bg_bottom, width=bg_width, height=bg_height)
      c.saveState()

      # draw the logo
      logo_path = "assets/logo.png"
      logo_img = Image.open(logo_path).convert("RGBA")
      logo_reader = ImageReader(logo_img)
      logo_margin = 0*inch
      logo_height = badge_height - rect_height - rect_bottom - 2*logo_margin + badge_bottom
      logo_width = logo_height
      logo_left = centerx - 0.5*logo_width
      logo_bottom = rect_bottom + rect_height + logo_margin
      c.drawImage(logo_reader, logo_left, logo_bottom, width=logo_width, height=logo_width, mask="auto")

      radius = 4.0 # rounded rectangle corner radius
      c.setFillColor(colors.white)
      c.setStrokeColorRGB(0.5, 0.5, 0.5)
      c.setLineWidth(0.05)
      c.roundRect(rect_left, rect_bottom, rect_width, rect_height, radius, stroke=1, fill=1)

      # Set up styles
      first_name_style = copy(styles['Title'])
      last_name_style = copy(styles['Title'])
      status_style = copy(styles['Title'])
      agaid_style = copy(styles['Normal'])
      city_state_style = copy(styles['Normal'])
      country_style = copy(styles['Normal'])

      # Customizing styles
      first_name_style.fontSize = 36
      last_name_style.fontSize = 28
      city_state_style.fontSize = 20
      country_style.fontSize = 20
      status_style.fontSize = 28

      agaid_style.fontSize = 24
      agaid_style.fillColor = colors.red

      rating_style = copy(first_name_style)
      rating_style.fontSize = 48

      override_style = copy(styles['Title'])
      override_style.font_size = 48

      max_width = rect_width - 0.125*inch

      # Draw text
      self.center_text(self.attendee["badge_top_name"], c, first_name_style, centerx, max_width, rect_bottom + rect_height - 0.5*inch)
      self.center_text(self.attendee["badge_bottom_name"], c, last_name_style, centerx, max_width, rect_bottom + rect_height - 1.0*inch)
      
      if "badge_aga_id" in self.attendee and self.attendee["badge_aga_id"] != None and self.attendee["badge_aga_id"] != "":
          self.center_text("AGA #%d" % (self.attendee["badge_aga_id"]), c, agaid_style, centerx, max_width, rect_bottom + rect_height - 1.75*inch)
      
      location_text = "%s, %s" % (self.attendee["badge_city"], self.attendee["badge_state"])
      if location_text == ", ":
        location_text = ""
      elif location_text.startswith(", "):
        location_text = self.attendee["badge_state"]
      elif location_text.endswith(", "):
        location_text = self.attendee["badge_city"]

      self.center_text(location_text, c, city_state_style, centerx, max_width, rect_bottom + rect_height - 2.35*inch)
      self.center_text(self.country_name_for_code(self.attendee["badge_country"]), c, country_style, centerx, max_width, rect_bottom + rect_height - 2.75*inch)

      self.center_text(self.attendee["badge_rating"], c, rating_style, centerx, max_width, rect_bottom + 0.25 * inch)
      
      if self.attendee["td_badge_override"] != "":
        self.center_text("*", c, override_style, centerx, max_width, rect_bottom + 0.025 * inch)

      c.setStrokeColorRGB(0.5, 0.5, 0.5)
      c.setLineWidth(0.05)

      flag_path = "assets/flags/%s.png" % (self.attendee["badge_country"].lower())
      if os.path.exists(flag_path):
        flag_img = Image.open(flag_path)
        flag_img_reader = ImageReader(flag_img)
        flag_width_px, flag_height_px = flag_img.size
        flag_aspect_ratio = flag_height_px / flag_width_px

        flag_width = 0.75*inch
        flag_height = flag_width * flag_aspect_ratio
        flag_bottom = rect_bottom + 0.25*inch
        flag_left = rect_left + 0.15*inch
        c.drawImage(flag_img_reader, flag_left, flag_bottom, width=flag_width, height=flag_height, mask='auto')
        c.rect(flag_left, flag_bottom, flag_width, flag_height)

      # draw the status description box
      c.setFillColor(colors.white)
      c.setStrokeColorRGB(0.5, 0.5, 0.5)
      c.setLineWidth(0.05)
      c.roundRect(rect_left, status_bottom, rect_width, status_height, radius, stroke=1, fill=1)
      self.center_text(self.badge_status_line(), c, status_style, centerx, max_width, status_bottom + 0.125*inch)

      # draw the drink ticket
      for bottom in [ ticket0_bottom, ticket1_bottom ]:
        ticket_height = 1.5 * inch
        padding = 0.25 * inch

        c.drawImage(logo_reader, left + padding, bottom + padding, width=ticket_height - 2*padding, height=ticket_height - 2*padding, mask="auto")
        drink_style = copy(styles['Title'])
        drink_style.fontSize = 24
        c.setFont(drink_style.fontName, drink_style.fontSize)
        c.setFillColor(colors.black)
        c.drawString(left + ticket_height, bottom + 0.65 * inch, "Banquet Drink")

      c.restoreState()

    c.showPage()
    c.save()
    self.log.info(f"Saved badge PDF: {filename}")
    return filename