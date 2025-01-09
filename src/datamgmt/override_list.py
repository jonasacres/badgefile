# a spreadsheet allowing respecification of attendee data
class OverrideList:
  def __init__(self):
    pass

  # return the sha256 of a given row
  def datahash(self, row):
    pass
  
  # apply all pending changes to the badgefile
  def apply(self, badgefile):
    pass

