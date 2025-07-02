from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

import os
import io
from pylibdmtx.pylibdmtx import encode
from PIL import Image as PILImage

from artifacts.pdfs.inset_box import InsetBox, style, font_size_for_width

class Checksheet:
  def __init__(self, attendee):
    self.attendee = attendee

  def issues_of_type(self, type):
    import json
    open_issues = self.attendee.open_issues()
    parsed = [json.loads(issue) for issue in open_issues.values()]
    in_category = [issue for issue in parsed if issue['category'] == type]
    return in_category
  
  def path(self):
    info = self.attendee.info()
    return f"artifacts/checksheets/{info['name_family']}-{info['name_given']}-{self.attendee.id()}.pdf"
  
  def generate(self):
    # Create parent directories for the badge file if they don't exist
    os.makedirs(os.path.dirname(self.path()), exist_ok=True)
    
    # Initialize the canvas and layout the badge
    self.layout()
    self.main_box.draw()
    self.canvas.showPage()
    
    # Add second page with Payment Information
    self.layout_details_page()
    self.details_box.draw()
    self.canvas.showPage()

    self.canvas.save()
    return self
  
  def create_grayscale_logo_reader(self):
    """Create a grayscale version of the logo and return an ImageReader"""
    # Load the original logo
    logo_img = Image.open("src/static/logos/2025-congress-logo.png")
    
    # Handle transparency by compositing onto white background
    if logo_img.mode in ('RGBA', 'LA') or (logo_img.mode == 'P' and 'transparency' in logo_img.info):
      # Create a white background image
      white_bg = Image.new('RGB', logo_img.size, (255, 255, 255))
      
      # Convert logo to RGBA if needed
      if logo_img.mode != 'RGBA':
        logo_img = logo_img.convert('RGBA')
      
      # Composite the logo onto the white background
      white_bg.paste(logo_img, mask=logo_img.split()[-1])  # Use alpha channel as mask
      logo_img = white_bg
    
    # Convert to grayscale
    grayscale_img = logo_img.convert('L')
    
    # Create a BytesIO buffer to hold the grayscale image data
    buffer = io.BytesIO()
    grayscale_img.save(buffer, format="PNG")
    buffer.seek(0)
    
    # Create an ImageReader from the buffer
    return ImageReader(buffer)
  
  def layout(self):
    # the main box covers the left half of a page and includes the badge, tearaway tickets, etc.
    self.canvas = canvas.Canvas(self.path(), pagesize=(8.5*inch, 11*inch))
    self.margin_size = 0.125*inch
    self.main_box = InsetBox(self.margin_size, self.margin_size, 8.5*inch - 2*self.margin_size, 11.0*inch - 2*self.margin_size, canvas=self.canvas)
    self.default_section_height = 0.8*inch

    next_y  = self.main_box.height - self.margin_size
    next_y -= self.layout_header(next_y).height + self.margin_size
    next_y -= self.layout_info(next_y).height + self.margin_size
    next_y -= self.layout_youth(next_y).height + self.margin_size
    next_y -= self.layout_payments(next_y).height + self.margin_size
    next_y -= self.layout_hospitality(next_y).height + self.margin_size
    next_y -= self.layout_tournaments(next_y).height + self.margin_size
    next_y -= self.layout_swag(next_y).height + self.margin_size
    next_y -= self.layout_badge(next_y).height + self.margin_size
    
    return self
  
  def layout_header(self, y):
    title_height = 0.5*inch
    title_enclosure = self.main_box.inset(self.margin_size, y - title_height, self.main_box.width - self.margin_size, title_height)
    title_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    title_enclosure.add_leaf_text_right(f"#{self.attendee.id()} {self.attendee.full_name()}", style(24, colors.black, bold=True), x=title_enclosure.width - self.margin_size, y=self.margin_size)
    
    logo_height = title_height - 0.05*inch
    logo_width  = 5/4 * logo_height
    logo_enclosure = title_enclosure.inset(0.025*inch, 0.025*inch, logo_width, logo_height)
    
    # Create grayscale logo and draw it
    grayscale_logo_reader = self.create_grayscale_logo_reader()
    
    def draw_grayscale_logo(canvas):
      img_left, img_bottom = logo_enclosure.absolute_coords()
      canvas.drawImage(grayscale_logo_reader, img_left, img_bottom, width=logo_width, height=logo_height, mask='auto')
    
    logo_enclosure.draw_func = lambda canvas: draw_grayscale_logo(canvas)
  
    return title_enclosure

  def layout_info(self, y):
    ii = self.attendee.final_info()
    pp = self.attendee.primary().final_info()

    info_height = 1.0*inch
    info_enclosure = self.main_box.inset(self.margin_size, y - info_height, self.main_box.width - self.margin_size, info_height)
    info_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    info_enclosure.add_leaf_text_left(
      f"{ii['name_given']} {ii['name_family']}  |  #{ii['aga_id']}, {ii['badge_rating']}  |  {ii['city']}, {ii['state']}, {ii['country']}",
      style(16, colors.black, bold=True),
      x=self.margin_size, y=info_height - 0.2*inch)
    info_enclosure.add_leaf_text_left(
      f"Primary Registrant: {pp['name_given']} {pp['name_family']}, AGA #{pp['aga_id']}, {self.attendee.primary().phone()}",
      style(12, colors.black, bold=False),
      x=self.margin_size, y=info_height - 0.45*inch)
    info_enclosure.add_leaf_text_left(
      self.attendee.title(),
      style(12, colors.black, bold=True),
      x=self.margin_size, y=info_height - 0.7*inch)
    if self.attendee.languages():
      lang_str = "Speaks " + ', '.join([lang.capitalize() for lang in self.attendee.languages()])
      if (ii.get('translator') or '').strip().lower() == 'yes':
        lang_str += ", can translate"
      info_enclosure.add_leaf_text_left(
        lang_str,
        style(12, colors.black, bold=False),
        x=self.margin_size, y=info_height - 0.95*inch)
    

    scan_height = info_enclosure.height - self.margin_size
    scan_enclosure = info_enclosure.inset(info_enclosure.width - scan_height - 0.0625*inch, 0.0625*inch, scan_height, scan_height)
    
    # Generate Data Matrix with attendee ID
    data = self.attendee.datamatrix_content()
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
    dm_size = scan_height
    dm_x = (scan_enclosure.width - dm_size) / 2
    dm_y = (scan_height - dm_size) / 2
    
    # Draw the Data Matrix
    dm_box = scan_enclosure.inset(dm_x, dm_y, dm_size, dm_size)
    
    def draw_datamatrix(canvas):
      img_left, img_bottom = dm_box.absolute_coords()
      canvas.drawImage(img_reader, img_left, img_bottom, width=dm_size, height=dm_size)
    
    dm_box.draw_func = lambda canvas: draw_datamatrix(canvas)

    return info_enclosure

  def layout_youth(self, y):
    needs_youth_form = self.attendee.still_needs_youth_form()
    if self.attendee.is_primary():
      need_sigs = [guest for guest in self.attendee.party() if guest.still_needs_youth_form()]
    elif self.attendee.still_needs_youth_form():
      need_sigs = [self.attendee]
    else:
      need_sigs = []

    stop_enclosure, content_enclosure = self.draw_table_stop(y, self.default_section_height, "2", "Youth", needs_youth_form)
    count = 0
    if need_sigs:
      for youth in need_sigs:
        count += 1
        yi = youth.final_info()
        content_enclosure.add_leaf_text_left(
          f"{yi['name_given']} {yi['name_family']}, #{youth.id()}, age {youth.age_at_congress()}",
          style(12.0, colors.black, bold=False),
          self.margin_size,
          content_enclosure.height - 0.2*inch*count)
    else:
      content_enclosure.add_leaf_text_left(
          f"No forms needed",
          style(12.0, colors.black, bold=False),
          self.margin_size,
          content_enclosure.height - 0.2*inch)
    return stop_enclosure

  def layout_payments(self, y):
    balance_due = self.attendee.balance_due()
    needs_renewal = self.attendee.needs_renewal()
    needs_stop = balance_due > 0 or needs_renewal
    stop_enclosure, content_enclosure = self.draw_table_stop(y, self.default_section_height, "3", "Payments", needs_stop)
    info = self.attendee.final_info()

    if balance_due == 0:
      content_enclosure.add_leaf_text_left(
        f"No balance due",
        style(12.0, colors.black, bold=False),
        self.margin_size,
        content_enclosure.height - 0.2*inch)
    elif self.attendee.is_primary():
      content_enclosure.add_leaf_text_left(
        f"Congress balance due: ${balance_due}",
        style(12.0, colors.black, bold=True),
        self.margin_size,
        content_enclosure.height - 0.2*inch)
    else:
      content_enclosure.add_leaf_text_left(
        f"Unpaid congress balance; contact primary registrant",
        style(12.0, colors.black, bold=False),
        self.margin_size,
        content_enclosure.height - 0.2*inch)
      
    if self.attendee.needs_renewal():
      content_enclosure.add_leaf_text_left(
        f"NEEDS AGA RENEWAL (expiration {info['aga_expiration_date']})",
        style(12.0, colors.black, bold=True),
        self.margin_size,
        content_enclosure.height - 0.45*inch)
    elif self.attendee.is_participant():
      content_enclosure.add_leaf_text_left(
        f"Membership OK (expiration {info['aga_expiration_date']})",
        style(12.0, colors.black, bold=False),
        self.margin_size,
        content_enclosure.height - 0.45*inch)

    return stop_enclosure

  def layout_hospitality(self, y):
    ai = self.attendee.final_info()
    issues = self.issues_of_type('housing')
    issues = [issue for issue in issues if issue['code'] != '3e'] # ignore issues about attendee not making housing choices
    
    if ai.get('housing_card_number'):
      needs_stop = True
    elif issues:
      needs_stop = True
    else:
      needs_stop = False
    
    stop_enclosure, content_enclosure = self.draw_table_stop(y, self.default_section_height, "4", "Hospitality", needs_stop)

    banquet_str = "Has Banquet" if self.attendee.is_attending_banquet() else "No Banquet"

    if ai.get('housing_card_number'):
      if ai.get('housing_building'):
        room_str = f"Room: {ai['housing_building']} {ai['housing_room_number']}"
        if ai.get('housing_roommate'):
          room_str += f", Roommate: {ai['housing_roommate']}"
      else:
        room_str = "No housing assigned"

      card_contents_str = f"Card {ai['housing_card_number']}"
      card_contents_str += " | " + ("Has meal plan" if ai.get('housing_meal_plan') else "No meal plan")
      card_contents_str += " | " + banquet_str
      card_contents_str += " | " + room_str
      content_enclosure.add_leaf_text_left(
        card_contents_str,
        style(12.0, colors.black, bold=True),
        self.margin_size,
        content_enclosure.height - 0.2*inch)
    else:
      content_enclosure.add_leaf_text_left(
        "No card | " + banquet_str,
        style(12.0, colors.black, bold=False),
        self.margin_size,
        content_enclosure.height - 0.2*inch)
    
    count = 0
    for issue in issues:
      print(f"{self.attendee.full_name()} {self.attendee.id()} -- Issue {issue['category']}: {issue['msg']}")
      content_enclosure.add_leaf_text_left(
          str(f"Issue: {issue['msg']}"),
          style(12.0, colors.black, bold=True),
          self.margin_size,
          content_enclosure.height - 0.45*inch - 0.2*inch*count)
      count += 1
    
    return stop_enclosure


  def layout_tournaments(self, y):
    if 'masters' in self.attendee.tournaments() and self.attendee.is_in_tournament('masters') and self.attendee.effective_rank() >= 5.0:
      needs_stop = True
    elif self.issues_of_type('tournament'):
      # TODO: need to write the issue on here
      needs_stop = True
    else:
      needs_stop = False
    
    stop_enclosure, content_enclosure = self.draw_table_stop(y, 1.85*inch, "5", "Tourney", needs_stop)
    tournaments = self.attendee.tournaments()

    content_enclosure.add_leaf_text_left(
        f"AGA Rating {self.attendee.aga_rating()}, Playing as {self.attendee.badge_rating()}",
        style(12.0, colors.black, bold=False),
        self.margin_size,
        content_enclosure.height - 0.2*inch)
    content_enclosure.add_leaf_text_left(
        f"US Open: {'YES' if 'open' in tournaments else 'NO'}",
        style(12.0, colors.black, bold=False),
        self.margin_size,
        content_enclosure.height - 0.50*inch)
    content_enclosure.add_leaf_text_left(
        f"Womens: {'YES' if 'womens' in tournaments else 'NO'}",
        style(12.0, colors.black, bold=False),
        self.margin_size + 2*inch,
        content_enclosure.height - 0.50*inch)
    content_enclosure.add_leaf_text_left(
        f"Seniors: {'YES' if 'seniors' in tournaments else 'NO'}",
        style(12.0, colors.black, bold=False),
        self.margin_size + 4*inch,
        content_enclosure.height - 0.50*inch)
    content_enclosure.add_leaf_text_left(
        f"Diehard: {'YES' if 'open' in tournaments else 'NO'}",
        style(12.0, colors.black, bold=False),
        self.margin_size,
        content_enclosure.height - 0.75*inch)
    
    bye_margin = 0.5*inch
    bye_width = content_enclosure.width - 2*bye_margin
    bye_enclosure = content_enclosure.inset(bye_margin, 0.3*inch, bye_width, 0.5*inch)
    bye_enclosure.add_leaf_rounded_rect(colors.white, colors.black, 0.01*inch, 0.05*inch)
    bye_enclosure.add_leaf_line(colors.black, 0.01*inch, 0, 0.5*bye_enclosure.height, bye_enclosure.width, 0.5*bye_enclosure.height)
    
    content_enclosure.add_leaf_text_centered("Bye Requests", style(10), y=0.1*inch)
    content_enclosure.add_leaf_text_right("PM", style(10, colors.darkgray), bye_margin-0.08*inch, 0.38*inch)
    content_enclosure.add_leaf_text_right("AM", style(10, colors.darkgray), bye_margin-0.08*inch, 0.6*inch)

    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for i in range(0, 7):
      x_position = (bye_width/7)*(i+0.5) + bye_margin
      content_enclosure.add_leaf_text_centered(days[i], style(10, colors.darkgray), x_position, 0.84*inch)

    # Draw vertical lines to partition bye_enclosure into 7 equal areas
    for i in range(1, 7):  # Draw 6 lines to create 7 areas
      x_position = (bye_width / 7) * i
      bye_enclosure.add_leaf_line(colors.black, 0.01*inch, x_position, 0.0, x_position, 0.5*inch)
    
    if self.attendee.is_in_tournament('masters'):
      masters_str = "YES"
    elif 'masters' in tournaments:
      masters_str = "Not Admitted"
    else:
      masters_str = "NO"

    content_enclosure.add_leaf_text_left(
        f"Masters: {masters_str}",
        style(12.0, colors.black, bold=False),
        self.margin_size + 2*inch,
        content_enclosure.height - 0.75*inch)
    return stop_enclosure

  def layout_swag(self, y):
    stop_enclosure, content_enclosure = self.draw_table_stop(y, self.default_section_height, "6", "Swag", True)
    content_enclosure.add_leaf_text_left(
        f"{self.attendee.final_info()['tshirt']}",
        style(18.0, colors.black, bold=True),
        self.margin_size,
        content_enclosure.height - 0.5*inch)
    return stop_enclosure
  
  def layout_badge(self, y):
    stop_enclosure, content_enclosure = self.draw_table_stop(y, 3.0*inch, "7", "Badge", True)
    content_enclosure.add_leaf_text_left(
      f"Write Corrections Below",
      style(16.0, bold=True),
      self.margin_size,
      content_enclosure.height - 0.25*inch
    )

    def correction_line(title, x, row, width):
      row_height = 0.65*inch
      row_start = content_enclosure.height - 0.7*inch
      y = row_start - row_height*row

      content_enclosure.add_leaf_line(colors.black, 0.05, x, y, x+width, y)
      content_enclosure.add_leaf_text_centered(title, style(10.0), x+0.5*width, y-0.2*inch, width)
    
    
    correction_line("Given Name (top)",       self.margin_size,              0, 3.125*inch)
    correction_line("Family Name (bottom)", 2*self.margin_size + 3.125*inch, 0, 3.0*inch)

    correction_line("City",                   self.margin_size,              1, 2.0*inch)
    correction_line("State/Province",       2*self.margin_size + 2.0*inch,   1, 2.0*inch)
    correction_line("Country",              3*self.margin_size + 4.0*inch,   1, 2.0*inch)

    correction_line("AGA #",                  self.margin_size,              2, 1.5*inch)
    correction_line("Title",                2*self.margin_size + 1.5*inch,   2, 4.625*inch)

    correction_line("Languages",              self.margin_size,              3, 6.25*inch)

    return stop_enclosure

  def draw_table_stop(self, y, height, number, title, needs_stop):
    stop_enclosure = self.main_box.inset(self.margin_size, y - height, self.main_box.width - self.margin_size, height)

    title_width = 1.0*inch
    if needs_stop:
      stop_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.15, 4.0)
      title_box = stop_enclosure.inset(0, 0, title_width, height)
      title_box.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
      title_box.add_leaf_text_centered(number, style(36, colors.black, bold=True), y=0.45*height)
      title_box.add_leaf_text_centered(title, style(12, colors.black, bold=True), y=0.15*height, max_width=title_width-0.125*inch)
    else:
      stop_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
      title_box = stop_enclosure.inset(0, 0, title_width, height)
      title_box.add_leaf_rounded_rect(colors.lightgrey, colors.gray, 0.05, 4.0)
      title_box.add_leaf_text_centered(number, style(36, colors.black, bold=True), y=0.45*height)
      title_box.add_leaf_text_centered(title, style(12, colors.black, bold=True), y=0.15*height, max_width=title_width-0.125*inch)

    check_width = 0.5*inch
    check_box = stop_enclosure.inset(stop_enclosure.width - check_width, 0, check_width, height)

    if needs_stop:
      check_box.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    else:
      check_box.add_leaf_rounded_rect(colors.lightgrey, colors.gray, 0.05, 4.0)
      check_box.add_leaf_text_centered("SKIP", style(12, bold=True), y=0.45*height)

    content_box = stop_enclosure.inset(title_width, 0, stop_enclosure.width - title_width - check_width, height)

    return stop_enclosure, content_box

  def layout_details_page(self):
    # Use the existing canvas instead of creating a new one
    self.details_box = InsetBox(self.margin_size, self.margin_size, 8.5*inch - 2*self.margin_size, 11.0*inch - 2*self.margin_size, canvas=self.canvas)

    next_y  = self.details_box.height - self.margin_size
    next_y -= self.layout_details_header(next_y).height + self.margin_size
    next_y -= self.layout_party(next_y).height + self.margin_size
    if self.attendee.is_primary():
      next_y -= self.layout_activities(next_y).height + self.margin_size
    
    return self
  
  def layout_details_header(self, y):
    title_height = 0.5*inch
    title_enclosure = self.details_box.inset(self.margin_size, y - title_height, self.details_box.width - self.margin_size, title_height)
    title_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    title_enclosure.add_leaf_text_right(f"#{self.attendee.id()} {self.attendee.full_name()}", style(24, colors.black, bold=True), x=title_enclosure.width - self.margin_size, y=self.margin_size)
    
    logo_height = title_height - 0.05*inch
    logo_width  = 5/4 * logo_height
    logo_enclosure = title_enclosure.inset(0.025*inch, 0.025*inch, logo_width, logo_height)
    
    # Create grayscale logo and draw it
    grayscale_logo_reader = self.create_grayscale_logo_reader()
    
    def draw_grayscale_logo(canvas):
      img_left, img_bottom = logo_enclosure.absolute_coords()
      canvas.drawImage(grayscale_logo_reader, img_left, img_bottom, width=logo_width, height=logo_height, mask='auto')
    
    logo_enclosure.draw_func = lambda canvas: draw_grayscale_logo(canvas)
  
    return title_enclosure

  def layout_party(self, y):
    party = self.attendee.party()
    line_height = 0.2*inch

    height = (len(party)+2)*line_height + self.margin_size
    party_enclosure = self.details_box.inset(self.margin_size, y - height, self.details_box.width - self.margin_size, height)
    party_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    count = 0

    party_enclosure.add_leaf_text_left(
        f"Party of {len(party)}",
        style(14, bold=True),
        self.margin_size,
        height - 0.25*inch
      )

    for person in party:
      count += 1
      pi = person.final_info()
      info_row = f"{pi['name_given']} {pi['name_family']}, {person.title()}, #{person.id()}"
      if person.is_primary():
        info_row += f", {person.phone()}"
      if pi.get('housing_building'):
        info_row += f", {pi['housing_building']} {pi['housing_room_number']}"
      party_enclosure.add_leaf_text_left(
        info_row,
        style(10, bold=person.is_primary()),
        self.margin_size,
        height - line_height*count - self.margin_size - 0.25*inch
      )


    return party_enclosure

  def layout_activities(self, y):
    activities = {}
    payments = []

    for person in self.attendee.party():
      for act in person.activities():
        if not act.is_open():
          continue
        title = act.info()['activity_title']
        regtype = act.info()['regtype']
        if title == "Registration Fee - Full Week":
          if "Adult Member" in regtype:
            title = "Registration - Full Week, Adult"
          elif "Youth Member" in regtype:
            title = "Registration - Full Week, Youth"
          elif "Non-Participant" in regtype:
            title = "Registration - Full Week, Non-participant"
          else:
            title = "Registration - Full Week, " + regtype
        if not title in activities:
          activities[title] = []
        activities[title].append(act)
      payments += person.housing_payment_lines() + person.congress_payment_lines()
    
    payments_by_trn = {}
    for payment in payments:
      if payment['payment_amount'] and float(payment['payment_amount']) > 0:
        payments_by_trn[payment['transrefnum']] = payment

    line_height = 0.2*inch
    height = (len(activities) + len(payments_by_trn) + 4) * line_height + self.margin_size + 1.5*inch

    activity_enclosure = self.details_box.inset(self.margin_size, y - height, self.details_box.width - self.margin_size, height)
    activity_enclosure.add_leaf_rounded_rect(colors.white, colors.gray, 0.05, 4.0)
    count = 0

    activity_enclosure.add_leaf_text_left(
        f"Invoice",
        style(14, bold=True),
        self.margin_size,
        height - self.margin_size - 0.25*inch
      )

    activity_enclosure.add_leaf_text_left(
        f"Item",
        style(10, bold=False),
        self.margin_size,
        height - self.margin_size - 0.50*inch
      )
    activity_enclosure.add_leaf_text_right(
        f"Unit Price",
        style(10, bold=True),
        activity_enclosure.width - 2.0*inch,
        height - self.margin_size - 0.50*inch
      )
    activity_enclosure.add_leaf_text_right(
        f"Qty",
        style(10, bold=True),
        activity_enclosure.width - 1.25*inch,
        height - self.margin_size - 0.50*inch
      )
    activity_enclosure.add_leaf_text_right(
        f"Subtotal",
        style(10, bold=True),
        activity_enclosure.width - self.margin_size,
        height - self.margin_size - 0.50*inch
      )

    grand_total = 0
    for title, acts in sorted(activities.items()):
      count += 1
      if acts[0].is_housing():
        qty = sum([act.num_units() for act in acts])
      elif acts[0].is_meal_plan():
        qty = sum([act.num_meal_plans() for act in acts])
      else:
        qty = len(acts)

      fee = sum([act.fee() for act in acts])/qty
      grand_total += fee*qty
      
      ai = act.info()
      activity_enclosure.add_leaf_text_left(
        f"{title}",
        style(10, bold=True),
        self.margin_size,
        height - line_height*count - self.margin_size - 0.5*inch
      )

      activity_enclosure.add_leaf_text_right(
        f"${fee:.2f}",
        style(10),
        activity_enclosure.width - 2*inch,
        height - line_height*count - self.margin_size - 0.5*inch
      )

      activity_enclosure.add_leaf_text_right(
        f"{int(qty)}",
        style(10),
        activity_enclosure.width - 1.25*inch,
        height - line_height*count - self.margin_size - 0.5*inch
      )

      activity_enclosure.add_leaf_text_right(
        f"${fee*qty:.2f}",
        style(10),
        activity_enclosure.width - self.margin_size,
        height - line_height*count - self.margin_size - 0.5*inch
      )
    
      activity_enclosure.add_leaf_text_right(
        f"${fee*qty:.2f}",
        style(10),
        activity_enclosure.width - self.margin_size,
        height - line_height*count - self.margin_size - 0.5*inch
      )

    activity_enclosure.add_leaf_text_left(
        f"Grand Total: ${grand_total:.2f}",
        style(12, bold=True),
        self.margin_size,
        height - line_height*(count) - self.margin_size - 0.8*inch
      )
    
    base_y = height - line_height*(count) - self.margin_size - 1.5*inch

    activity_enclosure.add_leaf_text_left(
        f"Payments",
        style(12, bold=True),
        self.margin_size,
        base_y + 0.20*inch,
      )

    activity_enclosure.add_leaf_text_left(
        f"Trans. Num",
        style(10, bold=True),
        self.margin_size,
        base_y
      )

    activity_enclosure.add_leaf_text_left(
      f"Payment Date",
      style(10, bold=True),
      self.margin_size + 1.0*inch,
      base_y
    )

    activity_enclosure.add_leaf_text_right(
      f"Amount",
      style(10, bold=True),
      self.margin_size + 3.0*inch,
      base_y
    )
  
    count = 0
    total_payments = 0
    for trn, payment in payments_by_trn.items():
      count += 1
      amount = payment['payment_amount'] or 0
      total_payments += float(amount)
      activity_enclosure.add_leaf_text_left(
        f"{trn}",
        style(10, bold=False),
        self.margin_size,
        base_y - line_height*count
      )

      activity_enclosure.add_leaf_text_left(
        f"{payment['payment_date']}",
        style(10, bold=False),
        self.margin_size + 1.0*inch,
        base_y - line_height*count
      )

      activity_enclosure.add_leaf_text_right(
        f"${amount}",
        style(10, bold=False),
        self.margin_size + 3.0*inch,
        base_y - line_height*count
      )
    
    activity_enclosure.add_leaf_text_left(
        f"Total Payments: ${total_payments:.2f}",
        style(12, bold=True),
        self.margin_size,
        base_y - line_height*(count) - 0.25*inch
      )
    
    activity_enclosure.add_leaf_text_left(
        f"Balance Due: ${grand_total - total_payments:.2f}",
        style(12, bold=True),
        self.margin_size,
        base_y - line_height*(count) - 0.60*inch
      )

    return activity_enclosure
