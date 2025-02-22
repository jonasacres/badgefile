def run_check(attendee):
  if not attendee.is_primary() or not attendee.party_housing():
    return None
  
  party_size = len(attendee.party())
  num_beds = sum([room.num_beds() for room in attendee.party_housing()])

  if party_size > num_beds:
    return {"msg": f"Party size exceeds bed count ({len(attendee.party())} > {num_beds})", "category": 'housing', "code": "3a"}
  elif party_size < num_beds:
    return {"msg": f"Party size is less than bed count ({len(attendee.party())} < {num_beds})", "category": 'housing', "code": "3b"}
  else:
    return None
