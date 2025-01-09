# pull data from CE on an interval; data is only new if the CSV has a new hash
# for each of reglist, housing info, payment info, event registration and TD list...
#   map each CSV line to an attendee, or nil/-1/etc if no attendee is found
#   compare data from CSV line to existing badgefile; if mismatch, add update line to journal
# update the badgefile
#   regenerate the directory
#   scan people for registration issues
# run the web service

# TODO: when do we run reports?
