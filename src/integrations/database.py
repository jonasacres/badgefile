import sqlite3
from typing import List, Dict, Any, Optional
import os

from log.logger import log

class Database:
  _shared = None

  @classmethod
  def shared(cls):
    if cls._shared == None:
      cls._shared = Database("badgefile.sqlite3")
    return cls._shared
  
  def __init__(self, path: str):
    """
    Initialize the Database instance.

    :param path: Path to the SQLite database file.
    """
    self.path = path
    self.conn = sqlite3.connect(self.path)

  def query(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    """
    Execute a SELECT query and return the results as an array of rows.

    :param sql: SQL query string (SELECT statement).
    :param params: Optional list of parameters for the query.
    :return: List of rows, each row as a dictionary.
    """

    if params is None:
      params = []
    self.conn.row_factory = sqlite3.Row  # Allows rows to be accessed as dictionaries
    cursor = self.conn.cursor()
    cursor.execute(sql, params)
    return [dict(row) for row in cursor.fetchall()]

  def execute(self, sql: str, params: Optional[List[Any]] = None) -> int:
    """
    Execute a non-SELECT query and return the number of rows affected.

    :param sql: SQL query string (INSERT, UPDATE, DELETE, CREATE TABLE, etc.).
    :param params: Optional list of parameters for the query.
    :return: Number of rows affected for INSERT, UPDATE, DELETE; undefined for other statements.
    """

    if params is None:
      params = []
    cursor = self.conn.cursor()
    try:
      cursor.execute(sql, params)
      self._last_id = cursor.lastrowid
      self.conn.commit()
      return cursor.rowcount
    except sqlite3.OperationalError as exc:
      log.warn(f"Encountered exception executing statement SQL", data=sql, exception=exc)
      os._exit(1)
  
  def columns_of_table(self, table_name):
    """
    Return a list of columns of a given table.
    
    :param table_name: Name of the table, string
    :return: A list of string names of columns in the table
    """

    cursor = self.conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [row[1] for row in cursor.fetchall()]
    return columns
  
  def last_id(self):
    return self._last_id

