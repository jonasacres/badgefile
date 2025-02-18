def run_check(attendee):
  banquet_regs = [x for x in attendee.activities() if x.is_banquet() and x.is_open()]
  if len(banquet_regs) > 1:
    return { "msg": f"Multiple banquet registrations ({len(banquet_regs)})",
             "num_banquet_regs": len(banquet_regs),
             "category": "banquet",
             "code": "9a" }
  return None