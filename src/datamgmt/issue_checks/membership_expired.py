from datetime import datetime

def run_check(attendee):
  # TODO: find out actual cutoff, and determine if we're testing expdate < cutoff or expdate <= cutoff
  expdate = attendee.membership_expiration()
  if expdate is None:
    return None
  cutoff = datetime.strptime("2025-08-01", "%Y-%m-%d")
  if expdate > cutoff:
    return None
  
  return {'msg': 'Attendee must renew AGA membership prior to Congress'}

