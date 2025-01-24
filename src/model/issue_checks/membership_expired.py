from datetime import datetime

def run_check(attendee):
  # TODO: find out actual cutoff, and determine if we're testing expdate < cutoff or expdate <= cutoff
  expdate = attendee.membership_expiration()
  if expdate is None:
    return None
  
  congress_start_cutoff = datetime.strptime("2025-07-13", "%Y-%m-%d")
  congress_end_cutoff = datetime.strptime("2025-08-01", "%Y-%m-%d")
  processing_cutoff = datetime.strptime("2025-08-01", "%Y-%m-%d")
  expdate_fmt = expdate.strftime("%m/%d/%Y")
  
  if expdate < congress_start_cutoff:
    return {"msg": f"AGA membership expires prior to Congress ({expdate_fmt})", "code": "1"}
  elif expdate < congress_end_cutoff:
    return {"msg": f"AGA membership expires during Congress ({expdate_fmt})", "code": "1"}
  elif expdate < processing_cutoff:
    return {"msg": f"AGA membership expires before ratings can be processed ({expdate_fmt})", "code": "1"}
  else:
    return None

