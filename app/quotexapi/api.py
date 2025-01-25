"""Module for Quotex websocket."""
import os
import time
import json
import ssl
import requests
import urllib3
import certifi
import logging
import atexit
import asyncio
import platform
import threading
from . import global_value
from .http.home import Home
from .http.login import Login
from .http.logout import Logout
from .http.profile import GetProfile
from .http.history import GetHistory
from .http.navigator import Browser
from .ws.channels.ssid import Ssid
from .ws.channels.buy import Buy
from .ws.channels.candles import GetCandles
from .ws.channels.sell_option import SellOption
from .ws.objects.timesync import TimeSync
from .ws.objects.candles import Candles
from .ws.objects.profile import Profile
from .ws.objects.listinfodata import ListInfoData
from .ws.client import WebsocketClient

urllib3.disable_warnings()
logger = logging.getLogger(__name__)

cert_path = certifi.where()
os.environ['SSL_CERT_FILE'] = cert_path
os.environ['WEBSOCKET_CLIENT_CA_BUNDLE'] = cert_path
cacert = os.environ.get('WEBSOCKET_CLIENT_CA_BUNDLE')

# Configuração do contexto SSL para usar TLS 1.3
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2  # Desativar versões TLS mais antigas
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_3  # Garantir o uso de TLS 1.3

ssl_context.load_verify_locations(certifi.where())


class QuotexAPI:
    """Class for communication with Quotex API."""
    socket_option_opened = {}
    buy_id = None
    pending_id = None
    trace_ws = False
    buy_expiration = None
    current_asset = None
    current_period = None
    buy_successful = None
    pending_successful = None
    account_balance = None
    account_type = None
    instruments = None
    training_balance_edit_request = None
    profit_in_operation = None
    profit_today = None
    sold_options_respond = None
    listinfodata = ListInfoData()
    timesync = TimeSync()
    candles = Candles()
    profile = Profile()

    def __init__(
            self,
            host,
            email,
            password,
            lang,
            session_data,
            auto_2_fa,
            proxies=None,
            auto_logout=True,
            user_data_dir=None,
            resource_path=None
    ):
        """
        :param str host: The hostname or ip address of a Quotex server.
        :param str email: The email of a Quotex server.
        :param str password: The password of a Quotex server.
        :param str lang: The lang of a Quotex platform.
        :param str session_data: The session data of a Quotex platform.
        :param bool auto_2_fa: If ``True``, use 2-factor authentication.
        :param proxies: The proxies of a Quotex server.
        :param user_data_dir: The path of a Browser cache.
        :param resource_path: The path of a Quotex files session.
        """
        self.host = host
        self.https_url = f"https://{host}"
        self.wss_url = f"wss://ws2.{host}/socket.io/?EIO=3&transport=websocket"
        self.wss_message = None
        self.websocket_thread = None
        self.websocket_client = None
        self.set_ssid = None
        self.email_pass = None
        self.email = email
        self.password = password
        self.session_data = session_data
        self.resource_path = resource_path
        self.proxies = proxies
        self.lang = lang
        self.auto_logout = auto_logout
        self.user_data_dir = user_data_dir
        self.auto_2_fa = auto_2_fa
        self._temp_status = ""
        self.settings_list = []
        self.signal_data = {}
        self.get_candle_data = {}
        self.historical_candles = {}
        self.candle_v2_data = {}
        self.realtime_price = {}
        self.real_time_candles = {}
        self.realtime_price_data = []
        self.realtime_sentiment = {}
        self.top_list_leader = {}
        self.browser = Browser()
        headers = session_data.get("headers", {})
        self.browser.set_headers(headers)
        self.user_agent = headers.get('User-Agent')

    @property
    def websocket(self):
        """Property to get websocket.

        :returns: The instance of :class:`WebSocket <websocket.WebSocket>`.
        """
        return self.websocket_client.wss

    def get_history_line(self, asset_id, index, timeframe, offset):
        payload = {
            "id": asset_id,
            "index": index,
            "time": timeframe,
            "offset": offset
        }
        data = f'42["history/load/line", {json.dumps(payload)}]'
        return self.send_websocket_request(data)

    def open_pending(self, amount, asset, direction, duration, open_time):
        payload = {
            "openType": 0,
            "asset": asset,
            "openTime": open_time,
            "timeframe": duration,
            "command": direction,
            "amount": amount
        }
        data = f'42["pending/create",{json.dumps(payload)}]'
        self.send_websocket_request(data)

    def instruments_follow(self, amount, asset, direction, duration, open_time):
        payload = {
            "amount": amount,
            "command": 0 if direction == "call" else 1,
            "currency": self.profile.currency_code,
            "min_payout": 0,
            "open_time": open_time,
            "open_type": 0,
            "symbol": asset,
            "ticket": self.pending_id,
            "timeframe": duration,
            "uid": self.profile.profile_id
        }
        data = f'42["instruments/follow",{json.dumps(payload)}]'
        self.send_websocket_request(data)

    def subscribe_leader(self):
        data = f'42["leader/subscribe"]'
        return self.send_websocket_request(data)

    def subscribe_realtime_candle(self, asset, period):
        self.realtime_price[asset] = []
        payload = {
            "asset": asset,
            "period": period
        }
        data = f'42["instruments/update", {json.dumps(payload)}]'
        return self.send_websocket_request(data)

    def chart_notification(self, asset):
        payload = {
            "asset": asset,
            "version": "1.0.0"
        }
        data = f'42["chart_notification/get", {json.dumps(payload)}]'
        return self.send_websocket_request(data)

    def follow_candle(self, asset):
        self.unfollow_candle(asset)
        data = f'42["depth/follow", {json.dumps(asset)}]'
        return self.send_websocket_request(data)

    def settings_apply(self, asset, duration, deal=5, percent_mode=False, percent_deal=1):
        payload = {
            "chartId": "graph",
            "settings": {
                "chartId": "graph",
                "chartType": 2,
                "currentExpirationTime": int(time.time()),
                "isFastOption": False,
                "isFastAmountOption": percent_mode,
                "isIndicatorsMinimized": False,
                "isIndicatorsShowing": True,
                "isShortBetElement": False,
                "chartPeriod": 4,
                "currentAsset": {
                    "symbol": asset
                },
                "dealValue": deal,
                "dealPercentValue": percent_deal,
                "isVisible": True,
                "timePeriod": duration,
                "gridOpacity": 8,
                "isAutoScrolling": 1,
                "isOneClickTrade": True,
                "upColor": "#0FAF59",
                "downColor": "#FF6251"
            }
        }
        data = f'42["settings/store",{json.dumps(payload)}]'
        self.send_websocket_request(data)

    def refresh_settings(self):
        auth_data = {
            "session": global_value.SSID,
            "isDemo": self.account_type,
            "tournamentId": 0
        }

        data = f'42["authorization",{json.dumps(auth_data)}]'
        self.send_websocket_request(data)

    def unfollow_candle(self, asset):
        data = f'42["depth/unfollow", {json.dumps(asset)}]'
        return self.send_websocket_request(data)

    def unsubscribe_realtime_candle(self, asset):
        data = f'42["subfor", {json.dumps(asset)}]'
        return self.send_websocket_request(data)

    def edit_training_balance(self, amount):
        data = f'42["demo/refill",{json.dumps(amount)}]'
        self.send_websocket_request(data)

    def signals_subscribe(self):
        data = f'42["signal/subscribe"]'
        self.send_websocket_request(data)

    def change_account(self, account_type):
        self.account_type = account_type
        payload = {
            "demo": self.account_type,
            "tournamentId": 0
        }
        data = f'42["account/change",{json.dumps(payload)}]'
        self.send_websocket_request(data)

    @property
    def homepage(self):
        """Property for get Quotex http homepage resource.

        :returns: The instance of :class:`Home
            <quotexapi.http.home.Home>`.
        """
        return Home(self)

    @property
    def logout(self):
        """Property for get Quotex http login resource.

        :returns: The instance of :class:`Logout
            <quotexapi.http.logout.Logout>`.
        """
        return Logout(self)

    @property
    def login(self):
        """Property for get Quotex http login resource.

        :returns: The instance of :class:`Login
            <quotexapi.http.login.Login>`.
        """
        return Login(self)

    @property
    def ssid(self):
        """Property for get Quotex websocket ssid channel.

        :returns: The instance of :class:`Ssid
            <Quotex.ws.channels.ssid.Ssid>`.
        """
        return Ssid(self)

    @property
    def buy(self):
        """Property for get Quotex websocket ssid channel.
        :returns: The instance of :class:`Buy
            <Quotex.ws.channels.buy.Buy>`.
        """
        return Buy(self)

    @property
    def sell_option(self):
        """Property for get Quotex websocket sell option channel.

        :returns: The instance of :class:`SellOption
            <quotexapi.ws.channels.candles.SellOption>`.
        """
        return SellOption(self)

    @property
    def get_candles(self):
        """Property for get Quotex websocket candles channel.

        :returns: The instance of :class:`GetCandles
            <quotexapi.ws.channels.candles.GetCandles>`.
        """
        return GetCandles(self)

    @property
    def get_profile(self):
        """Property for get Quotex http get profile.

        :returns: The instance of :class:`GetProfile
            <quotexapi.http.get_profile.GetProfile>`.
        """
        return GetProfile(self)

    @property
    def get_history(self):
        """Property for get Quotex http get history.

        :returns: The instance of :class:`GetHistory
            <quotexapi.http.history.GetHistory>`.
        """
        return GetHistory(self)

    def send_http_request_v1(self, resource, method, data=None, params=None, headers=None):
        """Send http request to Quotex server.

        :param resource: The instance of
        :class:`Resource <quotexapi.http.resource.Resource>`.
        :param str method: The http request method.
        :param dict data: (optional) The http request data.
        :param dict params: (optional) The http request params.
        :param dict headers: (optional) The http request headers.
        :returns: The instance of :class:`Response <requests.Response>`.
        """
        url = resource.url
        logger.debug(url)
        if headers.get("cookie"):
            self.browser.headers["Cookie"] = headers["cookie"]
        elif headers.get('referer'):
            self.browser.headers["Referer"] = headers["referer"]
        elif headers.get("content-type"):
            self.browser.headers["Content-Type"] = headers["content-type"]
        self.browser.headers["Connection"] = "keep-alive"
        self.browser.headers["Accept-Encoding"] = "gzip, deflate, br"
        self.browser.headers["Accept-Language"] = "pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3"
        self.browser.headers["Accept"] = headers.get(
            "accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        )
        self.browser.headers["Priority"] = 'u=0, i'
        self.browser.headers["Upgrade-Insecure-Requests"] = "1"
        self.browser.headers["Sec-CH-UA"] = '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"'
        self.browser.headers["Sec-Ch-Ua-Mobile"] = "?0"
        self.browser.headers["Sec-Ch-Ua-Platform"] = '"Linux"'
        self.browser.headers["Sec-Fetch-Site"] = "none"
        self.browser.headers["Sec-Fetch-User"] = "?1"
        self.browser.headers["Sec-Fetch-Dest"] = "document"
        self.browser.headers["Sec-Fetch-Mode"] = "navigate"
        self.browser.headers["Dnt"] = "1"
        self.browser.headers["TE"] = "trailers"
        with self.browser as s:
            response = s.send_request(
                method=method,
                url=url,
                data=data,
                params=params
            )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            return response

        return response

    async def get_user_profile(self):
        profile = await self.get_profile()
        data = profile.get("data", {})
        self.profile.nick_name = data.get("nickname")
        self.profile.profile_id = data.get("id")
        self.profile.demo_balance = data.get("demoBalance")
        self.profile.live_balance = data.get("liveBalance")
        self.profile.avatar = data.get("avatar")
        self.profile.currency_code = data.get("currencyCode")
        self.profile.country = data.get("country")
        self.profile.country_name = data.get("countryName")
        self.profile.currency_symbol = data.get("currencySymbol")
        self.profile.offset = data.get("timeOffset")
        return self.profile

    async def get_trader_history(self, account_type, page_number):
        history = await self.get_history(account_type, page_number)
        return history.get("data", {})

    def send_websocket_request(self, data, no_force_send=True):
        """Send websocket request to Quotex server.
        :param str data: The websocket request data.
        :param bool no_force_send: Default None.
        """
        while (global_value.ssl_Mutual_exclusion
               or global_value.ssl_Mutual_exclusion_write) and no_force_send:
            pass
        global_value.ssl_Mutual_exclusion_write = True
        if global_value.check_websocket_if_connect == 1:
            self.websocket.send(data)
        logger.debug(data)
        global_value.ssl_Mutual_exclusion_write = False

    async def authenticate(self):
        print("Connecting User Account ...")
        logger.debug("Login Account User...")
        status, message = await self.login(
            self.email,
            self.password,
            self.auto_2_fa
        )
        if status:
            global_value.SSID = self.session_data.get("token")
        logger.debug(message)
        return status

    async def start_websocket(self):
        global_value.check_websocket_if_connect = None
        global_value.check_websocket_if_error = False
        global_value.websocket_error_reason = None
        self.websocket_client = WebsocketClient(self)
        payload = {
            "ping_interval": 24,
            "ping_timeout": 20,
            "ping_payload": "2",
            "origin": self.https_url,
            "host": f"ws2.{self.host}",
            "sslopt": {
                "check_hostname": False,
                "cert_reqs": ssl.CERT_NONE,
                "ca_certs": cacert,
                "context": ssl_context
            },
            "reconnect": 5
        }
        if platform.system() == "Linux":
            payload["sslopt"]["ssl_version"] = ssl.PROTOCOL_TLS

        self.websocket_thread = threading.Thread(
            target=self.websocket.run_forever,
            kwargs=payload
        )
        self.websocket_thread.daemon = True
        self.websocket_thread.start()

        while True:
            if global_value.check_websocket_if_error:
                return False, global_value.websocket_error_reason
            elif global_value.check_websocket_if_connect == 0:
                logger.debug("Websocket connection closed.")
                return False, "Websocket connection closed."
            elif global_value.check_websocket_if_connect == 1:
                logger.debug("Websocket connected successfully!!!")
                return True, "Websocket connected successfully!!!"

            await asyncio.sleep(0.1)

    async def send_ssid(self, timeout=5):
        if not global_value.SSID:
            await self.authenticate()

        self.ssid(global_value.SSID)

        start_time = time.time()
        while not self.wss_message:
            if time.time() - start_time > timeout:
                return False
            await asyncio.sleep(0.1)

        if global_value.check_rejected_connection == 1:
            logger.info("Closing websocket connection...")
            logger.debug("Websocket Token rejected.")
            return False

        return True

    def logout_wrapper(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.logout())

    async def connect(self, is_demo, debug_ws=False, attempts=10):
        """Method for connection to Quotex API."""
        if attempts == 0:
            return False, "Closing websocket connection..."

        self.account_type = is_demo
        self.trace_ws = debug_ws
        global_value.ssl_Mutual_exclusion = False
        global_value.ssl_Mutual_exclusion_write = False

        if global_value.check_websocket_if_connect:
            logger.info("Closing websocket connection...")
            self.close()
        if self.auto_logout:
            atexit.register(self.logout_wrapper)

        check_websocket, websocket_reason = await self.start_websocket()
        if not check_websocket:
            return check_websocket, websocket_reason

        check_ssid = await self.send_ssid()
        if not check_ssid:
            await self.authenticate()
            await self.send_ssid()

        return check_websocket, websocket_reason

    def close(self):
        if self.websocket_client:
            self.websocket.close()
            # self.websocket_thread.join()

        return True

    def websocket_alive(self):
        return self.websocket_thread.is_alive()
