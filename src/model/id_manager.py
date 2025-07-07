import hashlib

from integrations.database import Database

class IdManager:
  """Manages assignment of badgefile IDs and remapping of IDs."""

  _shared = None
  
  @classmethod
  def shared(cls):
    if cls._shared == None:
      cls._shared = cls()
    return cls._shared

  def __init__(self):
    self.db = Database.shared()
    self.create_tables()

  def first_guest_id(self):
    # must be higher than the highest AGAID we will encounter.
    return 1000000

  def create_tables(self):
    self.create_badgefile_id_maps_table()
    self.create_guest_id_maps_table()

  def create_badgefile_id_maps_table(self):
    # Create the table
    self.db.execute("""
        CREATE TABLE IF NOT EXISTS BadgefileIdMaps (
            badgefile_id INTEGER NOT NULL,
            canonical_badgefile_id INTEGER NOT NULL
        )
    """)

    # Add an index on badgefile_id
    self.db.execute("""
        CREATE INDEX IF NOT EXISTS idx_badgefile_id ON BadgefileIdMaps (badgefile_id)
    """)

    # Add an index on canonical_badgefile_id
    self.db.execute("""
        CREATE INDEX IF NOT EXISTS idx_canonical_badgefile_id ON BadgefileIdMaps (canonical_badgefile_id)
    """)

    # Add a uniqueness constraint on badgefile_id
    self.db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS unique_badgefile_id ON BadgefileIdMaps (badgefile_id)
    """)

  def create_guest_id_maps_table(self):
    starting_value = self.first_guest_id()

    # Create the table
    self.db.execute("""
        CREATE TABLE IF NOT EXISTS GuestIdMaps (
            guest_id INTEGER PRIMARY KEY AUTOINCREMENT,
            userhash TEXT NOT NULL
        )
    """)

    # Add an index on guest_id (though unnecessary since guest_id is the PRIMARY KEY)
    self.db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_guest_id ON GuestIdMaps (guest_id)
    """)

    # Add an index on userhash
    self.db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_userhash ON GuestIdMaps (userhash)
    """)

    count = self.db.query("SELECT COUNT(*) AS count FROM GuestIdMaps")[0]["count"]
    if count == 0:
      # The table is empty, so it's probably brand new.
      # We want guest_ids to start with a number way beyond the highest AGA number.
      # If we insert and delete a row with guest_id=x-1, then sqlite3 will issue 'x' as the next guest_id (assuming the table was never used before)
      dummy_id = starting_value - 1
      self.db.execute("INSERT INTO GuestIdMaps (guest_id, userhash) VALUES (?, 'temp')", [dummy_id])
      self.db.execute("DELETE FROM GuestIdMaps WHERE guest_id=?", [dummy_id])

  def map_aga_id(self, aga_id):
    return self.canonical_id(aga_id)

  def map_reg_info(self, info):
    guest_id = self.lookup_reg_info(info)
    if guest_id is not None:
      return guest_id
    
    # We don't have an ID for this userhash, so issue one
    userhash = self.calculate_userhash(info)
    return self.issue_id(userhash)
  
  def lookup_reg_info(self, info):
    # If the user info includes an AGA number, that's their official ID. So work with that.
    if info.get("aga_id") != None:
      return self.map_aga_id(info["aga_id"])
    
    # No AGA number, so digest their info into a hash we can use as a lookup key to see if we've issued a guest ID to this person.
    userhash = self.calculate_userhash(info)
    rows = self.db.query("SELECT guest_id FROM GuestIdMaps WHERE userhash=?", [userhash])
    if len(rows) > 0:
      # We found a match, so reuse the existing ID.
      return self.canonical_id(rows[0]["guest_id"])
    
    return None

  # Returns the canonical ID for a person. This is intended to resolve some confusing cases:
  #  - people who have more than one AGA number (it happens)
  #  - people who signed up for congress without an AGA number, got issued a guest ID, then added an AGA number later
  #  - people who signed up for congress, then cancelled, then signed up again with a different name or DOB causing them to get more than one guest ID
  # the idea here is that in all these cases, we will manually identify a "canonical ID" for a person by choosing exactly one AGA number or guest ID,
  # and also manually identify every alternate ID, and make entries in the BadgefileIdMaps table associating each alternate ID to the canonical ID.
  def canonical_id(self, badgefile_id):
    badgefile_id = int(badgefile_id)
    rows = self.db.query("SELECT canonical_badgefile_id FROM BadgefileIdMaps WHERE badgefile_id=?", [badgefile_id])
    if len(rows) == 0:
      return badgefile_id
    return rows[0]["canonical_badgefile_id"]
  
  def issue_id(self, userhash):
    self.db.execute("INSERT INTO GuestIdMaps (userhash) VALUES (?)", [userhash])
    return self.db.last_id()

  def calculate_userhash(self, info):
    name_given = info.get("name_given").lower()
    name_family = info.get("name_family").lower()
    name_mi = info.get("name_mi").lower() if info.get("name_mi") != None else ""

    dob = info.get("date_of_birth")

    hash_input = f"{name_family}|{name_given}|{name_mi}|{dob}"

    return hashlib.sha256(hash_input.encode()).hexdigest()

  def set_id_alias(self, canonical_id, alias_id):
    self.db.execute("INSERT INTO BadgefileIdMaps (canonical_badgefile_id, badgefile_id) VALUES (?, ?)", [int(canonical_id), int(alias_id)])

