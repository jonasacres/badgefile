def run_check(attendee):
  if attendee.info()["registrant_fees"] > 2000 and attendee.is_primary():
    return {
      "msg": f"Total fees are very high (${attendee.info()['registrant_fees']})",
      "code": "4a",
    }
  return None

