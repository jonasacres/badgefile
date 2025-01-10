def run_check(attendee):
  regs = [x for x in attendee.activities() if "registration fee" in x.info()['activity_title'].lower()]
  if len(regs) >= 2:
    # The only way we can get 2 or more is if they pick both full and partial
    return {"msg": "Has Full Week and Partial registrations"}
  return None