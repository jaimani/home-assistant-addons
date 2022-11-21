"""ConEdison or Orange and Rockland Utility Smart Energy Meter"""
from time import sleep
import logging
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError
import os
import glob
import json
import pyotp


class MeterError(Exception):
    pass


class Meter(object):
    """A smart energy meter of ConEdison or Orange and Rockland Utility.

    Attributes:
        email: A string representing the email address of the account
        password: A string representing the password of the account
        mfa_type: Meter.MFA_TYPE_SECURITY_QUESTION or Meter.MFA_TYPE_TOTP
        mfa_secret: A string representing the multiple factor authorization secret
        account_uuid: A string representing the account uuid
        meter_number: A string representing the meter number
        site: Optional. Either `coned` (default, for ConEdison) or `oru` (for Orange and Rockland Utility)
        loop: Optional. Specific event loop if needed. Defaults to creating the event loop.
        account_number: Optional. For people who have multiple meters on a single account.
    """

    MFA_TYPE_SECURITY_QUESTION = 'SECURITY_QUESTION'
    MFA_TYPE_TOTP = 'TOTP'
    SITE_CONED = 'coned'
    DATA_SITE_CONED = 'cned'
    SITE_ORU = 'oru'
    DATA_SITE_ORU = 'oru'

    def __init__(self, email, password, mfa_type, mfa_secret, account_uuid, meter_number, account_number=None, site='coned', loop=None, browser_path=None):
        self._LOGGER = logging.getLogger(__name__)

        """Return a meter object whose meter id is *meter_number*"""
        self.email = email
        if self.email is None:
            raise MeterError("Error initializing meter data - email is missing")
        # _LOGGER.debug("email = %s", self.email.replace(self.email[:10], '*'))

        self.password = password
        if self.password is None:
            raise MeterError("Error initializing meter data - password is missing")
        # _LOGGER.debug("password = %s", self.password.replace(self.password[:9], '*'))

        self.mfa_type = mfa_type
        if self.mfa_type is None:
            raise MeterError("Error initializing meter data - mfa_type is missing")
        self._LOGGER.debug("mfa_type = %s", self.mfa_type)
        if self.mfa_type not in [Meter.MFA_TYPE_SECURITY_QUESTION, Meter.MFA_TYPE_TOTP]:
            raise MeterError("Error initializing meter data - unsupported mfa_type %s", self.mfa_type)

        self.mfa_secret = mfa_secret
        if self.mfa_secret is None:
            raise MeterError("Error initializing meter data - mfa_secret is missing")
        # _LOGGER.debug("mfa_secret = %s", self.mfa_secret.replace(self.mfa_secret[:8], '*'))

        self.account_uuid = account_uuid
        if self.account_uuid is None:
            raise MeterError("Error initializing meter data - account_uuid is missing")
        # _LOGGER.debug("account_uuid = %s", self.account_uuid.replace(self.account_uuid[:20], '*'))

        self.meter_number = meter_number.lstrip("0")
        if self.meter_number is None:
            raise MeterError("Error initializing meter data - meter_number is missing")
        # _LOGGER.debug("meter_number = %s", self.meter_number.replace(self.meter_number[:5], '*'))

        self.account_number = account_number

        self.site = site
        if site == Meter.SITE_CONED:
            self.data_site = Meter.DATA_SITE_CONED
        elif site == Meter.SITE_ORU:
            self.data_site = Meter.DATA_SITE_ORU
        self._LOGGER.debug("site = %s", self.site)
        if self.site not in [Meter.SITE_CONED, Meter.SITE_ORU]:
            raise MeterError("Error initializing meter data - unsupported site %s", self.site)

        self.loop = loop
        self._LOGGER.debug("loop = %s", self.loop)

    def all_reads(self):
        """Return all available meter read values and unit of measurement"""
        try:
            raw_data = self.browse()

            if raw_data is None:
                self._LOGGER.debug("failed retrieving the usage data, trying again... in 5 minutes")
                sleep(300)
                self.browse()
            # parse the return reads and extract the most recent one
            # (i.e. last not None)
            jsonResponse = json.loads(raw_data)

            availableReads = []
            if 'error' in jsonResponse:
                self._LOGGER.info("got JSON error back = %s", jsonResponse['error']['details'])
                raise MeterError(jsonResponse['error']['details'])
            for read in jsonResponse['reads']:
                if read['value'] is not None:
                    availableReads.append(read)

            parsed_reads = []
            for read in availableReads:
                this_parsed_read = {}
                this_parsed_read['start_time'] = read['startTime']
                this_parsed_read['end_time'] = read['endTime']
                this_parsed_read['value'] = read['value']
                this_parsed_read['unit_of_measurement'] = jsonResponse['unit']
                parsed_reads.append(this_parsed_read)
                self._LOGGER.info("got read = %s %s %s %s", this_parsed_read['start_time'], this_parsed_read['end_time'],
                    this_parsed_read['value'], this_parsed_read['unit_of_measurement'])
            return parsed_reads
        except:
            raise MeterError("Error requesting meter data")

    def last_read(self):
        """Return the last meter read value and unit of measurement"""
        all_available_reads = self.all_reads()
        last_read = all_available_reads[-1]
        return last_read['start_time'], last_read['end_time'], last_read['value'], last_read['unit_of_measurement']

    def browse(self):
        screenshotFiles = glob.glob('meter*.png')
        for filePath in screenshotFiles:
            try:
                os.remove(filePath)
            except:
                self._LOGGER.debug("Error while deleting file : ", filePath)

        with sync_playwright() as playwright:
            # browser = playwright.chromium.launch(headless=False)
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()
            page.goto('https://www.' + self.site + '.com/en/login')
            page.get_by_label("Email Address").fill(self.email)
            page.get_by_label("Password").fill(self.password)
            page.screenshot(path="meter1-1.png")
            self._LOGGER.debug('meter1-1')
            page.get_by_role("button", name="Log In").click()
            page.screenshot(path="meter1-2.png")
            self._LOGGER.debug('meter1-2')
            mfa_code = self.mfa_secret
            if self.mfa_type == self.MFA_TYPE_TOTP:
                mfa_code = pyotp.TOTP(self.mfa_secret).now()
            page.get_by_label("Enter Code").fill(mfa_code)
            page.screenshot(path="meter2-1.png")
            self._LOGGER.debug('meter2-1')
            page.get_by_label("Enter Code").press("Enter")

            # look for API response which contains last 24h of meter data
            with page.expect_response(lambda response: 'cws-real-time-ami-v1' in response.request.url and 'usage' in response.request.url) as response_info:
                page.get_by_role("link", name="VIEW ENERGY USE").click()
                try:
                    page.wait_for_url("https://www.' + self.site + '.com/en/accounts-billing/my-account/energy-use")
                except PlaywrightTimeoutError:
                    print('timeout loading energy use')
                    self._LOGGER.error('timeout waiting for response')

                #try to ensure that the chart loads, which will guarantee we have the API response
                # expect(page.get_by_text("li:has-text('Weather (°F)')")).to_be_visible()
                try:
                    selector = f'li:has-text("Weather (°F)")")'
                    pre = page.wait_for_selector(selector)
                    pre.click()
                    print("waiting successful!")
                except PlaywrightTimeoutError:
                    self._LOGGER.info('timeout waiting for chart to load')
                # page.wait_for_load_state('domcontentloaded')
                # page.locator("li:has-text(\"Electricity Use\")").click()
                page.screenshot(path="meter3-1.png")
                self._LOGGER.debug('meter3-1')
            raw_data = response_info.value.text()
            self._LOGGER.debug(f"raw_data = {raw_data}")
            context.close()
            browser.close()
            return raw_data

# def intercept_response(response):
#     global raw_data
#     if 'cws-real-time-ami-v1' in response.request.url and 'usage' in response.request.url:
#         print(f"  response.url: {response.url}")
#         print(f"  response.status: {response.status}")
#         print(response.text())
#         raw_data = response.text()