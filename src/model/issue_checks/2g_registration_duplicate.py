def run_check(attendee):
  rrbid = attendee.reglist_cacher().reglist_rows_by_id(attendee.latest_reglist(), attendee.badgefile())
  if not attendee.id() in rrbid:
    return None
  
  matches_user = rrbid[attendee.id()]
  active = [row for row in matches_user if row['status'].lower() == "open"]

  if len(active) < 2:
    return None

  all_regs = [attendee.__class__(attendee.badgefile).load_reglist_row(row) for row in active]
  reg_details = [ {
    'transrefnum': reg.info()['transrefnum'],
    'regtime': reg.info()['regtime'],
    'primary_aga_id': reg.primary().info()['aga_id'],
    'primary_name': f"{reg.primary().info()['name_given']} {reg.primary().info()['name_family']}",
    'primary_email': reg.primary().info()['email'],
  } for reg in all_regs ]

  return {'msg': "Attendee appears in multiple active registrations",
          'num_registrations': len(all_regs),
          'reg_details': reg_details,
          'category': 'registration',
          'code': '2g'
          }
