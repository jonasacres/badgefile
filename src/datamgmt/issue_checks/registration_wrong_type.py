from datetime import datetime

def run_check(attendee):
  # TODO: figure out actual youth registration cutoff
  type = attendee.info()['regtype'].lower()
  dob = attendee.date_of_birth()
  youth_cutoff = datetime(2002, 7, 20)

  if "adult aga member" in type:
    if dob > youth_cutoff:
      return {'msg': "Eligible for youth pricing but registered as adult", 'type': 'too-old'}
  elif "youth aga member" in type:
    if dob <= youth_cutoff:
      return {'msg': "Not eligible for youth pricing but registered as youth", 'type': 'too-young'}
  return None