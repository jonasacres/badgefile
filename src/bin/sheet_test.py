#!/usr/bin/env python3

import time
import pathlib
import sys
src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from log.logger import log
from integrations.google_api import sync_sheet_table, authenticate_service_account
from util.secrets import secret

start_time = time.time()
test_header = ["Col1", "Col2", "Col3", "Comment"]
test_data = [ [ 1, 2, 3 ], [ 7, 8, 1002 ], [10, 11, 12] ]

service = authenticate_service_account()
sync_sheet_table(service, "test_sheet_02", test_header, test_data, 0, "test_sheet", secret("folder_id"))
