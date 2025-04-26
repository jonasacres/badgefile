#!/usr/bin/env python

import sys
import os
import time

from model.badgefile import Badgefile
from util.util import *
from log.logger import log
from artifacts.html.friends_of_congress_page import DonorPage

badgefile = Badgefile()
DonorPage(badgefile).generate()
print("Generated donor page")
