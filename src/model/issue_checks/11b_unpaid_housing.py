def run_check(attendee):
  balance_due = attendee.housing_balance_due()
  if balance_due > 0:
    return { "msg": "Unpaid balance (Housing)", 'balance_due': balance_due, 'category': 'payment', 'code': '11b' }
  return None
