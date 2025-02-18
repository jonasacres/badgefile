def run_check(attendee):
  if float(attendee.info()["registrant_fees"]) > 2000 and attendee.is_primary():
    return {
      "msg": f"Total fees are very high (${attendee.info()['registrant_fees']})",
      "code": "4a",
      'category': 'registration',
    }
  return None

