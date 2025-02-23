def run_check(attendee):
   # this issue should only show under a non-primary registrant who booked housing
  if not attendee.party_housing():
    return None # there's no housing, so no problem under this test
  if attendee.is_primary():
    return None # there is housing, but the primary registrant is incapable of generating a problem under 3(d)
  if not any([booking.info()['badgefile_id'] == attendee.id() for booking in attendee.party_housing()]):
    return None # no issue if this attendee did not book any housing themselves
  
  # if the housing registration is not under the primary attendee, then there's an issue (code 3d)
  return {"msg": f"Housing registration is not under the primary attendee", "category": 'housing', "code": "3d"}
  
