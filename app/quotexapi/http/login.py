import os
import re
import json
import asyncio
import logging
from pathlib import Path
from ..config import (
    config,
    config_path
)
from ..http.automail import get_pin
from ..http.resource import Resource
from ..http.qxbroker import Browser

logger = logging.getLogger(__name__)


class Login(Resource, Browser):
    """Class for Quotex login resource."""
    current_token = None
    current_cookies = None
    current_user_agent = None
    email = None
    password = None
    auto_2_fa = None
    email_pass = None

    def update_session(self):
        output_file = Path(
            os.path.join(
                self.api.resource_path,
                "session.json"
            )
        )
        if os.path.isfile(output_file):
            with open(os.path.join(self.api.resource_path, "session.json"), "r+") as file:
                json_data = json.loads(file.read())
                headers = json_data["headers"]
                headers["User-Agent"] = self.current_user_agent
                headers["Cookie"] = self.current_cookies
                json_data["token"] = self.current_token
                json_data["headers"] = headers
                file.seek(0)
                json.dump(
                    json_data,
                    file,
                    indent=4
                )
                file.truncate()

    def get_sign_page(self):
        self.url = f"{self.api.https_url}/{self.api.lang}"
        headers = {
            "referer": f"https%3A%2F%2Fwww.google.com%2F; "
                       f"lid=671195; _ga=GA1.1.498809927.1711282682; "
                       f"lang={self.api.lang};"
        }
        response = self._get(headers=headers)
        if not response.ok:
            return response

        self.current_user_agent = response.request.headers['User-Agent']
        cookies_dict = response.cookies.get_dict()
        cookies_str = '; '.join([f"{key}={value}" for key, value in cookies_dict.items()])
        self.current_cookies = cookies_str
        self.api.session_data['headers']['Cookie'] = cookies_str
        return response

    def get_token(self):
        self.url = f"{self.api.https_url}/{self.api.lang}/sign-in/modal/"
        headers = {
            "referer": self.api.https_url,
            "cookie": self.current_cookies
        }
        self._get(headers=headers)
        html = self.api.browser.get_soup()
        match = html.find(
            "input", {"name": "_token"}
        )
        token = None if not match else match.get("value")
        logger.debug(f'Get Token SSL RESOLVER: {token}')
        return token

    def success_login(self):
        if "trade" in self.api.browser.response.url:
            return True, "Login successful."
        html = self.api.browser.get_soup()
        match = html.find(
            "div", {"class": "hint--danger"}
        ) or html.find(
            "div", {"class": "input-control-cabinet__hint"}
        )
        message_in_match = match.text.strip() if match else ""
        return False, f"Login failed. {message_in_match}"

    async def auth(self, data):
        self.url = f"{self.api.https_url}/{self.api.lang}/sign-in/modal/"
        headers = {
            "referer": f"{self.api.https_url}/{self.api.lang}/sign-in",
            "cookie": self.current_cookies
        }
        response = self._post(
            data=data,
            headers=headers
        )
        await asyncio.sleep(1)
        required_keep_code = self.api.browser.get_soup().find("input", {"name": "keep_code"})
        if required_keep_code:
            logger.debug(f'Required keep code: {required_keep_code}')
            self.email_pass = config.get("settings", "email_pass", fallback=None)
            if self.auto_2_fa and not self.email_pass and "gmail.com" in self.email:
                self.email_pass = input(
                    'Enter the app password to authenticate your Gmail account via SMTP: \n'
                    'If you dont have an app password, access: \n'
                    'https://support.google.com/accounts/answer/185833?hl=en '
                )
                existing_data = config_path.read_text(encoding="utf-8")
                text_settings = (
                    f"{existing_data}\n"
                    f"email_pass={self.email_pass}\n"
                )
                config_path.write_text(text_settings)

            auth_body = self.api.browser.get_soup().find("main", {"class": "auth__body"})
            input_message = (
                f'{auth_body.find("p").text}: ' if auth_body.find("p")
                else "Insira o código PIN que acabamos de enviar para o seu e-mail: "
            )
            response = await self.awaiting_pin(data, input_message)
        headers = self.api.session_data.get('headers')
        cookies = self.api.browser.response.cookies.get_dict()
        cookies_dict = dict(re.findall(r'(\w+)=([^;]+)', headers.get('Cookie', "lang=pt")))
        cookies_dict.update(cookies)
        cookies_str = '; '.join([f"{key}={value}" for key, value in cookies_dict.items()])
        self.current_cookies = cookies_str
        self.api.session_data['headers']['Cookie'] = cookies_str
        settings = None
        script = self.api.browser.get_soup().find_all("script", {"type": "text/javascript"})
        for tag in script:
            if 'window.settings' in tag.string:
                settings = tag.get_text().strip().replace(";", "")
                break
        match = re.sub("window.settings = ", "", settings)
        token = json.loads(match).get("token")
        self.current_token = token
        self.api.session_data['token'] = token
        self.update_session()
        success = self.success_login()
        logger.debug(f'Login with SSL RESOLVER: {success}')

        return success

    async def awaiting_pin(self, data, input_message):
        pin_code = None
        data["keep_code"] = 1
        await asyncio.sleep(5)
        if self.auto_2_fa and self.email_pass:
            pin_code = await get_pin(self.email, self.email_pass)
        code = pin_code or int(input(input_message))
        logger.debug(f'Keep code: {code}')
        data["code"] = code
        await asyncio.sleep(1)
        self.url = f"{self.api.https_url}/{self.api.lang}/sign-in/modal/"
        headers = {
            "referer": f"{self.api.https_url}/{self.api.lang}/sign-in/modal",
            "cookie": self.current_cookies
        }
        return self._post(
            data=data,
            headers=headers
        )

    def get_profile(self, data=None):
        self.url = f"{self.api.https_url}/api/v1/cabinets/digest"
        headers = {
            "referer": f"{self.api.https_url}/{self.api.lang}/trade",
            "cookie": self.current_cookies
        }
        response = self._get(
            data=data,
            headers=headers
        )

        if response.ok:
            data = response.json()["data"]
            self.current_token = data.get("token")
            self.api.session_data['token'] = data.get("token")
            self.update_session()

        return response

    def _get(self, data=None, headers=None):
        return self.send_http_request(
            method="GET",
            data=data,
            headers=headers
        )

    def _post(self, data=None, headers=None):
        """Send get request for Quotex API login http resource.
        :returns: The instance of :class:`requests.Response`.
        """
        return self.send_http_request(
            method="POST",
            data=data,
            headers=headers
        )

    async def __call__(self, email, password, auto_2_fa):
        """Method to get Quotex API login http request.
        :param str email: The username of a Quotex server.
        :param str password: The password of a Quotex server.
        :param bool auto_2_fa: If ``True``, automatize 2-factor authentication.
        :returns: The instance of :class:`requests.Response`.
        """
        self.email = email
        self.password = password
        self.auto_2_fa = auto_2_fa
        status, message = False, None
        home = self.get_sign_page()
        if not home.ok:
            return await self.get_cookies_and_ssid()

        logger.debug(f'Access page with SSL RESOLVER: {home.reason}')
        token = self.get_token()
        if token:
            data = {
                "_token": token,
                "email": email,
                "password": password,
                "remember": 1,
            }
            status, message = await self.auth(data)
            if not status:
                print(message)
                exit(0)

        return status, message
