class Badge:
  def __init__(self, attendee):
    self.attendee = attendee
  
  def generate(self, path):
    # render the badge to a PDF file saved at 'path'
    pass

  def upload(self, path):
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

    def draw(self):
      self.draw_background()
      main_box = InsetBox(...) # some bounding rect with a reasonable margin from the badge edges

      title_box = box.inset(...) # some bounding box
      for box in [main_box, title_box]:
        box.corner_radius(12)
        box.background(1.0, 1.0, 1.0, 1.0)
      
      self.draw_main_section(main_box)
      self.draw_title_section(title_box)
    
    def draw_background(self):
      pass

    def draw_logo(self):
      pass
    
    def draw_main_section(self, box):
      pass

    def draw_name(self, box):
      pass

    def draw_rating(self, box):
      pass

    def draw_aga_number(self, box):
      pass

    def draw_region(self, box):
      pass
    
    def draw_title_section(self, box):
      pass

    def draw_country_flag(self, box):
      pass

    def draw_language_flags(self, box):
      pass
    