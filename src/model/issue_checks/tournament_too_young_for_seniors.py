from datetime import datetime

def run_check(attendee):
  if not attendee.is_participant():
    return None
  
  if not "seniors" in attendee.tournaments():
    return None
  
  cutoff = datetime(1970, 7, 13)
  if attendee.date_of_birth() > cutoff:
    return {'msg': f"Requests Seniors, but was born {attendee.date_of_birth().strftime('%m/%d/%Y')}", 'code': '5d'}
  return None