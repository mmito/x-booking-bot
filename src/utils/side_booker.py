import selenium.webdriver as webdriver
from webdriver_manager.chrome import ChromeDriverManager


if __name__ == "__main__":
    driver2 = webdriver.Remote(command_executor='http://127.0.0.1:51992') 
    driver2.session_id = 'd70fc7dd8afee5546df6b40f50faf12e'

    driver2.get('https://x.tudelft.nl/dashboard')

    while True:
        pass

    driver2.quit()