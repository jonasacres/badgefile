from datetime import datetime

def run_check(attendee):
  # TODO: find actual cutoff for requiring youth form
  cutoff = datetime(2007, 7, 12)
  dob = attendee.date_of_birth()

  if dob >= cutoff:
    has_youth_form = False # TODO: get a way to access this. apparently there will be a Google Sheet?
    if not has_youth_form:
      return {'msg': "Youth form required", 'code': '2d'}
  
  return None