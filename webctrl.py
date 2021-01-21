import pytest
import time
import json
import mysql
from dbctrl import *
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


class WEBCtrl():
	'''
	1. Get Web connection info from DB
	2. Initiate webdriver
	3. Connect Webpage
	'''

	def __init__(self) :
		pass

    def get_webinfo(self):
        pass

    def init_wd(self):
        pass

    def connect(self):
        pass

    def disconnect(self):
        pass


