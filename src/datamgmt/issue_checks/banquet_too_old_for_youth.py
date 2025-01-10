from datetime import datetime

def run_check(attendee):
  dob = attendee.info()["date_of_birth"]  # dob is in mm/dd/yyyy format
  dob_date = datetime.strptime(dob, "%m/%d/%Y")
  cutoff_date_10yo = datetime(2015, 7, 20)
  
  over_10 = dob_date < cutoff_date_10yo # they're too old for under-10 admission to the banquet!
  
  activities = [x for x in attendee.activities() if x.is_banquet()]
  if len(activities) == 0:
    return None
  
  # ignore multiple activities; another issue checks for that
  banquet = activities[0]
  booked_under10 = "under 10" in banquet.info()['activity_title'].lower()
  if booked_under10 and over_10:
    return {"msg": f"Banquet reservation is for Youth Under 10; too old (dob: {dob_date})"}
  elif not over_10 and not booked_under10:
    return {"msg": f"Eligible for under-10 banquet pricing (dob: {dob_date})"}
  return None
