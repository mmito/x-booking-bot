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

# from seleniumwire import webdriver

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

def standalone_booking(input_to_parse):
        booker = Booker()

        booker.set_username(input("Please enter your username: "))
        booker.set_password(getpass.getpass(prompt="Please enter your password: "))

        booker.login()

        WebDriverWait(booker.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[id^='tag-filterbutton']"))).click()
        
        menu_titles = WebDriverWait(booker.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "ul[aria-labelledby^='tag-filterbutton']"))) \
            .find_elements(By.CSS_SELECTOR, "h5")
        menu_sections = WebDriverWait(booker.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "ul[aria-labelledby^='tag-filterbutton']"))) \
            .find_elements(By.CSS_SELECTOR, "ul[class^='list-group mb-3 list-group-flush']")
        
        activities = {}

        for title, section in zip(menu_titles, menu_sections):
            activities[title.text[:-2]] = [element.get_attribute('innerHTML') for element in section.find_elements(By.CSS_SELECTOR, "label[class^='form-check-label']")]

        # dump the activities dict as a json file
        with open('activities.json', 'w', newline='') as outputdata:
            json.dump(activities, outputdata)
        
        # with open('menutest.html', 'w', newline='') as outputdata:
        #     json.dump(elements, outputdata)


        # ############################################################################
        # req = {}
        #
        # for index, request in enumerate(self.driver.requests):
        #     # if request.response:
        #         req[f'{index}_request_url'] = request.url
        #         req[f'{index}_request_headers'] = dict(request.headers)
        #         # req['response_status_code'] = request.response.status_code
        #
        # with open('cookietest.json', 'w', newline='') as outputdata:
        #     json.dump(req, outputdata)
        #
        # ############################################################################


        
        # now Google is opened, the browser is fully functional; print the two properties
        # command_executor._url (it's "private", not for a direct usage), and session_id
        # 
        # print(f'driver.command_executor._url: {booker.driver.command_executor._url}')
        # print(f'driver.session_id: {booker.driver.session_id}')


        # check_bookings = booker.check_bookings()       

        # print(check_bookings) 

        # hours_to_book, day_to_book = parse_input(input_to_parse)
        # booker.select_day(day_to_book)           # Defaults to today
        # booker.select_activity()                 # Defaults to Fitness (28)
        # booker.attempt_booking(hours_to_book)

        booker.quit()

class Booker:
    driver = None
    username = None
    password = None
    is_logged_in = False
    activity = None
    current_node = None
    booked_slots = None
    day_to_book = None
    slots_to_book = None
    kill = False

    def __init__(self, username=None, password=None, is_logged_in=False, activity=None, current_node=None, day_to_book=None, slots_to_book=None, booked_slots=None):
        self.username = username
        self.password = password
        self.is_logged_in = is_logged_in
        self.activity = activity
        self.current_node = current_node
        self.day_to_book = day_to_book
        self.slots_to_book = slots_to_book
        self.booked_slots = booked_slots
        self.driver = self.start_browser()

    def set_kill(self, kill):
        self.kill = kill

    def set_username(self, username):
        self.username = username

    def set_password(self, password):
        self.password = password

    def set_credentials(self, username, password):
        self.username = username
        self.password = password

    def clear_credentials(self):
        self.username = None
        self.password = None
        self.is_logged_in = False

    def get_login_status(self):
        return self.is_logged_in

    def start_browser(self):
        chrome_options = Options()
        if HEADLESS: chrome_options.add_argument("--headless=new")
        if NO_LOG: chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.driver.get("https://x.tudelft.nl/pages/login")

        WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-test-id^='oidc-login-button']"))).click()
        WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "h3[id^='idp__titleremaining1']"))).click()
        return self.driver

    def login(self):
        WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id^='username']"))).send_keys(self.username)
        WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id^='password']"))).send_keys(self.password)
        WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[id^='submit_button']"))).click()
        try:
            WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div[class^='btn btn-soft-primary day-selector-navbutton datepicker-toggle']")))

            self.is_logged_in = True
            self.select_day()
            self.select_activity()
        except Exception as e:
            # print(f'Exception in function login\n{e}')
            # print('Login failed, retry.')
            self.is_logged_in = False

    def select_day(self, day=datetime.now().day):
        if not self.is_logged_in:
            return False, None

        self.day_to_book = day

    def get_selected_day(self): 
        return self.day_to_book

    def select_hours(self, hours_to_book):
        if not self.is_logged_in:
            return False, None
        
        self.slots_to_book = hours_to_book

    def get_slots_to_book(self):
        return self.slots_to_book


    def select_activity(self, activity='Fitness'):
        if not self.is_logged_in:
            return False, None
        
        self.activity = activity

    def get_selected_activity(self):
        return self.activity
        
    def get_booked_slots(self):
        return self.booked_slots
    
    def go_to_homepage(self):
        if not self.is_logged_in:
            return False, None
        
        self.driver.get("https://x.tudelft.nl/products/bookable-product-schedule")

    def attempt_booking(self):
        if not self.is_logged_in:
            return False, None
        
        queued_hours_to_book = deque(self.slots_to_book)
        print(f'Initial queue = {queued_hours_to_book}')

        # Select day
        self.driver.get("https://x.tudelft.nl/products/bookable-product-schedule")
        WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div[class^='btn btn-soft-primary day-selector-navbutton datepicker-toggle']"))).click()
        steps = self.day_to_book - datetime.now().day
        actions = ActionChains(self.driver)
        for _ in range(steps):
            actions.send_keys(Keys.ARROW_RIGHT)
        actions.send_keys(Keys.ENTER)
        actions.perform()

        # Select activity
        # WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.XPATH,'//button[text()=" Wis "]'))).click()
        time.sleep(1)
        WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[id^='tag-filterbutton']"))).click()
        found_activity = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{self.activity}')]")))
        self.driver.execute_script("arguments[0].click();", found_activity)

        is_booked = False
        booked_time = None
        while (not is_booked) and (not self.kill):
            try:
                target_hour = queued_hours_to_book.popleft()
                correct_booking_slot = WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.XPATH, f"//strong[contains(text(), '{target_hour}')]")))
                # print(correct_booking_slot.get_attribute("innerHTML"))
                is_booked, booked_time = self.book_slot(correct_booking_slot, target_hour)
                continue

            # NEEDS A LOT OF REFACTORING
            except Exception as e:
                print(f'Exception in function booking_from_telegram\n{e}')
                # Tried to pop from empty queue or non-existing hour slot
                print('All bookings failed, retrying...')
                # Filter out hours that have already passed
                current_hour = datetime.now().hour
                queued_hours_to_book = deque(filter(lambda x: x > current_hour, self.slots_to_book))
                # print(f'Current queue = {queue_from_hours_to_check}')
                # Refresh page
                # self.driver.refresh()
                time.sleep(1)
                self.driver.get("https://x.tudelft.nl/products/bookable-product-schedule")
                time.sleep(1)

                # # Select day
                # time.sleep(1)
                # WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div[class^='btn btn-soft-primary day-selector-navbutton datepicker-toggle']"))).click()
                # steps = self.day_to_book - datetime.now().day
                # actions = ActionChains(self.driver)
                # for _ in range(steps):
                #     actions.send_keys(Keys.ARROW_RIGHT)
                # actions.send_keys(Keys.ENTER)
                # actions.perform()

                # # Select activity
                # # time.sleep(1)
                # # WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.XPATH,'//button[text()=" Wis "]'))).click()
                # time.sleep(1)
                # WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[id^='tag-filterbutton']"))).click()
                # time.sleep(1)
                # found_activity = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{self.activity}')]")))
                # self.driver.execute_script("arguments[0].click();", found_activity)

                continue
        
        self.set_kill(False)
        return is_booked, booked_time

    def book_slot(self, slot_to_book : WebElement, target_hour):
        try:
            button_to_reserve = slot_to_book.find_element(By.XPATH, './ancestor::div[1]/ancestor::div[1]/div[2]/div[2]/div/button')
            print(button_to_reserve.get_attribute("innerHTML"))
            # print(button_to_reserve.get_attribute("innerHTML"))
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

    def check_bookings(self):
        # navigate to the page: https://x.tudelft.nl/dashboard
        # check if there are any bookings
        # if there are, return their retrieved times
        # if there aren't, return None
        
        self.driver.get("https://x.tudelft.nl/dashboard")

        slots_booked = []
        no_bookings = False

        while not (slots_booked or no_bookings):
            try:
                slots_booked = self.driver.find_elements(By.CSS_SELECTOR, "div[class^='card border mb-3']")
                no_bookings = bool(self.driver.find_elements(By.CSS_SELECTOR, "div[class^='no-upcoming-bookings-figure text-center']"))
            except Exception as e:
                # print(f'Exception in function check_bookings\n{e}')
                continue

        if no_bookings:
            return None
        
        bookings = []
        ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,)

        while len(bookings) < len(slots_booked):
            try:
                activity_regex = f"//*[@id=\"{len(bookings) + 1}\"]/div[2]/div/h2"
                date_regex = f"//*[@id=\"{len(bookings) + 1}\"]/div[3]/div/p[1]/strong"
                activity = WebDriverWait(self.driver, 20, ignored_exceptions=ignored_exceptions).until(EC.presence_of_element_located((By.XPATH, activity_regex))).text
                date = WebDriverWait(self.driver, 20, ignored_exceptions=ignored_exceptions).until(EC.presence_of_element_located((By.XPATH, date_regex))).text
                bookings.append([activity, date])
            except Exception as e:
                # print(f'Exception in function check_bookings\n{e}')
                continue
        
        self.booked_slots = bookings
        return bookings
    
    def quit(self):
        self.driver.quit()

if __name__ == "__main__":
    standalone_booking(sys.argv)
