def run_check(attendee):
  party = attendee.party()
  if len(party) >= 5:
    return { "msg": "Very large party", "party_size": len(party), 'category': 'registration', 'code': '4b' }
  return None
