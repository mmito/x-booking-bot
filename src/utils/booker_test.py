from abc import ABC
import functools
import threading
import time
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service

from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException

from webdriver_manager.chrome import ChromeDriverManager
from collections import deque
from datetime import datetime

import sys
import getpass
import json

HEADLESS = False
NO_LOG = False

URL_LOGIN = 'https://x.tudelft.nl/pages/login'
URL_HOMEPAGE = 'https://x.tudelft.nl/products/bookable-product-schedule'
URL_BOOKINGS = 'https://x.tudelft.nl/dashboard'

VALID_USER_FIELDS = set(
    [
    'username',
    'password',
    'login_status',
    'day',
    'hours',
    'activity',
    'booked_slots'
    ]
)

######################################################
##################### DECORATORS #####################
######################################################

def check_login(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        self = args[0]
        if not self.get('login_status'):
            return 'User not logged in.'
        return func(*args, **kwargs)
    return wrapper

######################################################
###################### PARSERS #######################
######################################################

def parse_input(input):
    try:
        day_kw_index = input.index('-d')
        hours_to_book = parse_booking_times(input[:day_kw_index])
        day_to_book = parse_booking_day(input[day_kw_index+1:])
    except Exception as e:
        print(f'Exception in function parse_input\n{e}')
        hours_to_book = parse_booking_times(input)
        day_to_book = datetime.now().day
    finally:
        return hours_to_book, day_to_book
        

def parse_booking_times(input_split):
    # print(f'Hours split: {input_split}')
    hours_to_book = []
    for message_token in input_split:
        if '-d' in message_token:
            break
        if '-' in message_token:
            start_hour, end_hour = message_token.split('-')
            start_hour = int(start_hour)
            end_hour = int(end_hour)
            hours_to_book += [*range(start_hour,end_hour+1)]
        elif message_token.isdigit():
            hours_to_book.append(int(message_token))
    return sorted(hours_to_book)

def parse_booking_day(input_split):
    # print(f'Day split: {input_split}')
    for message_token in input_split:
        if message_token.isdigit():
            return int(message_token)
    return datetime.now().day

def parse_booking_activity(input_split):
    print(f'Booking split: {input_split}')
    # for message_token in input_split:
    #     if message_token == 'Fitness':
    #         return 28
    #     if message_token.isdigit():
    #         return int(message_token)
    if input_split == '':
        return 'Fitness'

    return str(input_split)

######################################################
############### STANDALONE USE METHODS ###############
######################################################

def standalone_booking(input_to_parse):
    manager = UserManager()

    # booker.set('username', input("Please enter your username: "))
    # booker.set('password', getpass.getpass(prompt="Please enter your password: "))

    manager.start_browser() \
        .set('username', 'ttofacchi') \
        .set('password', 'Quadronno99!2') \
        .login() \
        .cancel_booking(2) \
        .check_bookings()

    print(manager.get('booked_slots'))

    # quit = False
    # while not quit:
    #     for thread in manager.booker_threads.values():
    #         if thread[1]:
    #             print(thread[1])
    #             quit = True

    manager.quit()

######################################################
###################### CLASSES #######################
######################################################

class DriverManager(ABC):

    driver = None
    user_data = dict()

    def __init__(self, driver=None, user_data=dict()):
        self.driver = driver
        self.user_data = user_data

    def set(self, key, value):
        ### TODO: Change with match --> PYTHON 3.10
        if key in VALID_USER_FIELDS:
            self.user_data[key] = value
            return self
        else:
            return 'Invalid key for SETTING a user_data dict property.'

    def get(self, key):
        ### TODO: Change with match --> PYTHON 3.10
        if key in VALID_USER_FIELDS:
            return self.user_data[key]
        else:
            return 'Invalid key for GETTING a user_data dict property.'

    def quit(self):
        self.driver.quit()
        return self

    def click(self, element : WebElement):
        time.sleep(0.5)
        self.driver.execute_script("arguments[0].click();", element)
        return self

    def go_to(self, url):
        self.driver.get(url)
        return self

    def start_browser(self):
        chrome_options = Options()
        if HEADLESS: chrome_options.add_argument("--headless=new")
        if NO_LOG: chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        self.driver = webdriver.Chrome(options=chrome_options)

        self.go_to(URL_LOGIN)
        self.click(WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-test-id^='oidc-login-button']"))))
        self.click(WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "h3[id^='idp__titleremaining1']"))))
        return self

    def login(self):
        WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id^='username']"))).send_keys(self.get('username'))
        WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id^='password']"))).send_keys(self.get('password'))
        self.click(WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[id^='submit_button']"))))

        tag_success = "input[class^='datepicker-input ng-untouched ng-pristine ng-valid']"
        tag_fail = "div[class^='message-box error']"

        found_element = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, tag_success + "," + tag_fail)))
        found_element : WebElement = found_element
        print(found_element.tag_name)

        if found_element.tag_name == 'input':
            self.set('login_status', True)
        else:
            print('Login failed, retry.')
            self.set('login_status', False)
        return self


class UserManager(DriverManager):
    booker_threads = dict()

    def __init__(self, driver=None, user_data=dict(), booker_threads=dict()):
        self.booker_threads = booker_threads
        super().__init__(driver, user_data)

    @check_login
    def book(self, booker_id):
        result_for_thread = []
        booker = Booker(self.user_data).start_browser().login()
        booker.spawn_booking_thread(result_for_thread)
        self.booker_threads[booker_id] = [booker, result_for_thread]
        return self

    @check_login
    def check_bookings(self):
        self.go_to(URL_BOOKINGS)
        no_booking_tag = "h3[data-test-id^='no-upcoming.bookings']"
        bookings_tags = "div[class^='card border mb-3']"
        found_elements = WebDriverWait(self.driver, 20).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, no_booking_tag + "," + bookings_tags)))
        if type(found_elements) is not list:
            found_elements = [found_elements]
        
        bookings = []
        for index, element in enumerate(found_elements):
            if element.tag_name == 'h3':
                break
            elif element.tag_name == 'div':
                activity_regex = f"//*[@id=\"{index + 1}\"]/div[2]/div/h2"
                date_regex = f"//*[@id=\"{index + 1}\"]/div[3]/div/p[1]/strong"
                activity = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, activity_regex))).text
                date = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, date_regex))).text
                bookings.append([activity, date])

        self.set('booked_slots', bookings)
        return self
    
    @check_login
    def cancel_booking(self, booking_id):
        self.go_to(URL_BOOKINGS)
        correct_div : WebElement = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, f"//div[@id=\"{booking_id}\"]")))
        cancel_button = correct_div.find_element(By.XPATH, f"//button[contains(text(), 'Annuleer')]")
        self.click(cancel_button)
        confirm_cancel_button = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, f"button[data-test-id^='booking-confirm-cancel']")))
        div_to_print = confirm_cancel_button.find_element(By.XPATH, './../../../')
        print(div_to_print.get_attribute("innerHTML"))

        while True:
            pass

        self.click(confirm_cancel_button)
        WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, f"//div[contains(text(), 'Boeking geannuleerd')]")))
        print('Successfully cancelled booking!')
        return self

class Booker(DriverManager):
    to_kill = False

    def __init__(self, user_data, to_kill=False, driver=None):
        self.to_kill = to_kill
        super().__init__(driver, user_data)
    
    def kill(self):
        self.to_kill = True
        return self
    
    def spawn_booking_thread(self, result_list : list):
        thread = threading.Thread(target=self.attempt_booking, args=(result_list,))
        thread.start()
        return self
    
    @check_login
    def select_day(self):
        # wait to be sure that actions are not too fast
        # time.sleep(1)

        self.click(WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div[class^='btn btn-soft-primary day-selector-navbutton datepicker-toggle']"))))
        days_to_skip = self.get('day') - datetime.now().day
        actions = ActionChains(self.driver)
        for _ in range(days_to_skip):
            actions.send_keys(Keys.ARROW_RIGHT)
        actions.send_keys(Keys.ENTER)
        actions.perform()
        return self
    
    @check_login
    def select_activity(self):
        # wait to be sure that actions are not too fast
        # time.sleep(1)

        self.click(WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH,'//button[text()=" Wis "]'))))
        # time.sleep(1)

        self.click(WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[id^='tag-filterbutton']"))))
        self.click(WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{self.get('activity')}')]"))))
        return self
        
    @check_login
    def attempt_booking(self, result_list : list):

        queued_hours_to_book = deque(self.get('hours'))
        print(f'Initial queue = {queued_hours_to_book}')

        is_booked = False
        booked_time = None

        while not is_booked and not self.to_kill:
            try:
                # Select day and activity
                self.go_to(URL_HOMEPAGE).select_day().select_activity()
                
                target_hour = queued_hours_to_book.popleft()
                correct_booking_slot = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, f"//strong[contains(text(), '{target_hour}')]")))
                is_booked, booked_time = self._book_slot(correct_booking_slot, target_hour)
                continue

            except Exception as e:
                print(f'Exception in function booking_from_telegram\n{e}')
                # Tried to pop from empty queue or non-existing hour slot
                print('All bookings failed, retrying...')
                # Filter out hours that have already passed
                queued_hours_to_book = deque(filter(lambda x: x > datetime.now().hour, self.get('hours')))
                continue
        
        result_list.append((is_booked, booked_time))

        print('Booked!')
        self.quit()
        return result_list

    @check_login
    def _book_slot(self, slot_to_book : WebElement, target_hour):
        try:
            button_to_reserve = slot_to_book.find_element(By.XPATH, './ancestor::div[1]/ancestor::div[1]/div[2]/div[2]/div/button')
            print(button_to_reserve.get_attribute("innerHTML"))
            self.driver.execute_script('arguments[0].click()', button_to_reserve)
            slots_booked = self.driver.find_elements(By.CSS_SELECTOR, "div[class^='card border mb-3']")
            if slots_booked:
                print('Slot already booked, retrying other timeslots...')
                return True, target_hour
            WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.XPATH, '/html/body/modal-container/div/div/ng-component/div[3]/div/div[2]/button'))).click()
            WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "h4[class^='text-success']")))
            print(f'Successfully booked at {target_hour} o\'clock!')
            return True, target_hour
        except Exception as e:
            print(f'Exception in function book\n{e}')
            print(f'Booking failed for hour {target_hour}, retrying other timeslots...')
            return False, None
        
    

if __name__ == "__main__":
    standalone_booking(sys.argv)
