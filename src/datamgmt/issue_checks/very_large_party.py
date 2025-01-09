def run_check(attendee):
  party = attendee.party()
  if len(party) >= 5:
    return { "msg": "Attendee has very large party", "party_size": len(party) }
  return None
