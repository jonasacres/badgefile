from datetime import datetime

def run_check(attendee):
  # TODO: figure out actual youth registration cutoff
  type = attendee.info()['regtype'].lower()
  dob = attendee.date_of_birth()
  youth_cutoff = datetime(2008, 7, 20)
  ya_cutoff = datetime(2002, 7, 20)

  if "adult member" in type:
    if dob > youth_cutoff:
      return {'msg': "Eligible for Free Youth admission but registered as Full-rate Adult", 'type': 'too-young', 'code': '2e'}
    elif dob > ya_cutoff:
      return {'msg': "Eligible for Young Adult admission but registered as Full-rate Adult", 'type': 'too-young', 'code': '2e'}
  elif "young adult" in type:
    if dob > youth_cutoff:
      return {'msg': "Eligible for Free Youth admission, but registered as Young Adult", 'type': 'too-young', 'code': '2d'}
    elif dob <= ya_cutoff:
      return {'msg': "Registered as Young Adult, but too old to be eligible for discount", 'type': 'too-old', 'code': '2c'}
  elif "youth member" in type:
    if dob <= ya_cutoff:
      return {'msg': "Registered for Free Youth admission, but too old for any youth discount", 'type': 'too-old', 'code': '2b'}
    elif dob <= youth_cutoff:
      return {'msg': "Registered for Free Youth admission, but only qualifies for Young Adult discount", 'type': 'too-old', 'code': '2b'}
      
  return None
