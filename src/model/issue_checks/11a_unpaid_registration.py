def run_check(attendee):
  balance_due = attendee.congress_balance_due()
  if balance_due > 0:
    return { "msg": "Unpaid balance (Congress registration)", 'balance_due': balance_due, 'category': 'payment', 'code': '11a' }
  return None
