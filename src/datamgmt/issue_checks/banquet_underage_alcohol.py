from datetime import datetime

def run_check(attendee):
  dob = attendee.info()["date_of_birth"]  # dob is in mm/dd/yyyy format
  dob_date = datetime.strptime(dob, "%m/%d/%Y")
  cutoff_date = datetime(2025, 7, 20)
  minor = dob_date > cutoff_date # they're a minor if they'll be under 21 on the night of the banquet

  if minor and attendee.is_attending_banquet() and attendee.has_banquet_alcohol():
    return {"msg": "Attendee is minor, but registered for banquet alcohol"}
  
