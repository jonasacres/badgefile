def run_check(attendee):
  party = attendee.party()
  if len(party) >= 5:
    return { "msg": "Very large party", "party_size": len(party) }
  return None
