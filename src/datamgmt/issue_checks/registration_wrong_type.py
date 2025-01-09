from datetime import datetime

def run_check(attendee):
  # TODO: figure out actual youth registration cutoff
  type = attendee.info()['regtype'].lower()
  dob = attendee.date_of_birth()
  youth_cutoff = datetime(2002, 7, 13)

  if "adult aga member" in type:
    if dob < youth_cutoff:
      return {'msg': "Attendee is registered as adult, but is eligible for youth pricing", 'type': 'too-old'}
  elif "youth aga member" in type:
    if dob >= youth_cutoff:
      return {'msg': "Attendee is registered as youth, but is not eligible for youth pricing", 'type': 'too-young'}
  return None