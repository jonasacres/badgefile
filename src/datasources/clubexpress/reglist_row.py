from log.logger import log

# wrap up a specific row from the reglist
class ReglistRow:
  def __init__(self, reglist, row):
    self.reglist = reglist
    self.row = row
    self._info = self.parse_info()

  def parse_info(self):
    info = {}
    fields = self.reglist.heading_map().keys()

    for field in fields:
      index = self.reglist.index_for_field(field)
      if index is None:
        log.warn(f"Failed to locate reglist column: {field} ({self.reglist.heading_map()[field]})")
      raw_value = self.row[index]
      
      if "phone" in field or field == "postcode":
        info[field] = raw_value # ensure these remain as strings, even if they happen to have been written exclusively with numerics
      elif raw_value == "":
        info[field] = None  # Blank string becomes None
      elif raw_value.replace(".", "", 1).isdigit():
        # Check if it's a float or int
        info[field] = float(raw_value) if "." in raw_value else int(raw_value)
      else:
        info[field] = raw_value  # Use the original string if it's not numeric

    return info
    
  # return data lining up with info dict from Attendee
  def info(self):
    return self._info
