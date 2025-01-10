from datetime import datetime

def run_check(attendee):
  if not attendee.is_participant():
    return None
  
  cutoff = datetime(1970, 7, 13)
  if attendee.date_of_birth() > cutoff:
    return {'msg': f"Requests Seniors, but was born {attendee.date_of_birth().strftime('%m/%d/%Y')}"}
  return None