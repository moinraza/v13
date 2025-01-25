import time
import logging
import asyncio
from . import expiration
from . import global_value
from .api import QuotexAPI
from .utils.services import truncate
from .utils.processor import (
    calculate_candles,
    process_candles_v2,
    merge_candles
)
from .config import (
    load_session,
    resource_path,
    update_session,
    user_data_dir
)
from typing import (
    Optional,
    Union
)

logger = logging.getLogger(__name__)


class Quotex:

    def __init__(
            self,
            email,
            password,
            lang="pt",
            user_agent="Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0",
            host="qxbroker.com",
            auto_logout=False,
            auto_2_fa=False,
            root_path=".",
            data_dir=user_data_dir,
            asset_default="EURUSD",
            period_default=60
    ):
        """
        Initialize Quotex instance.

        Args:
            email (str): User's email for Quotex.
            password (str): User's password for Quotex.
            lang (str, optional): Language preference (default is "pt").
            user_agent (str, optional): User agent string for HTTP requests (default is a Firefox user agent).
            host (str, optional): Host URL for Quotex API (default is "qxbroker.com").
            email_pass (str, optional): Email password (default is None).
            auto_logout (bool, optional): Whether to automatically logout (default is False).
            :param (bool) auto_2_fa: If ``True``, use 2-factor authentication.
            root_path (str, optional): Root directory path (default is ".").
            data_dir (str, optional): User data directory path (default is user_data_dir).
            asset_default (str, optional): Default trading asset (default is "EURUSD").
            period_default (int, optional): Default period for trading (default is 60).
        """
        self.email = email
        self.password = password
        self.lang = lang
        self.host = host
        self.auto_logout = auto_logout
        self.asset_default = asset_default
        self.period_default = period_default
        self.suspend = 0.5
        self.account_is_demo = 1
        self.api = None
        self.duration = None
        self.codes_asset = {}
        self.websocket_client = None
        self.websocket_thread = None
        self.debug_ws_enable = False
        self.user_data_dir = data_dir
        self.auto_2_fa = auto_2_fa
        self.resource_path = resource_path(root_path)
        session = load_session(user_agent)
        self.session_data = session

    @property
    def websocket(self):
        """Property to get the WebSocket instance.

        Returns:
            WebSocket: The instance of WebSocket.
        """

        return self.websocket_client.wss

    @staticmethod
    async def check_connect():
        """Check if there is an accepted connection.

        Returns:
            bool: True if connection is accepted, False otherwise.
        """
        await asyncio.sleep(2)
        if global_value.check_accepted_connection == 1:
            return True

        return False

    def set_session(self, user_agent: str, cookies: str = None, ssid: str = None):
        """
        Set session data.

        Args:
            user_agent (str): User agent string.
            cookies (str, optional): Cookie data (default is None).
            ssid (str, optional): Session ID (default is None).
        """
        session = {
            "headers": {
                "User-Agent": user_agent,
                "Cookie": cookies,
            },
            "token": ssid
        }
        self.session_data = update_session(session)

    async def get_instruments(self):
        """
        Retrieve instruments data asynchronously.

        Returns:
            list: List of available instruments.
        """
        while self.api.instruments is None:
            await asyncio.sleep(0.2)

        return self.api.instruments or []

    def get_all_asset_name(self):
        """
        Get names of all available assets.

        Returns:
            list: List of asset names.
        """
        if self.api.instruments:
            return [[i[1], i[2].replace("\n", "")] for i in self.api.instruments]

    async def get_available_asset(self, asset_name: str, force_open: bool = False):
        """
        Get available assets asynchronously.

        Args:
            asset_name (str): Asset name.
            force_open (bool, optional): Whether to force open the asset (default is False).

        Returns:
            tuple: Asset name and its availability status.
        """
        asset_open = await self.check_asset_open(asset_name)
        if force_open and (not asset_open or not asset_open[2]):
            condition_otc = "otc" not in asset_name
            refactor_asset = asset_name.replace("_otc", "")
            asset_name = f"{asset_name}_otc" if condition_otc else refactor_asset
            asset_open = await self.check_asset_open(asset_name)

        return asset_name, asset_open

    async def check_asset_open(self, asset_name: str):
        """
        Check if the asset is open for trading asynchronously.

        Args:
            asset_name (str): Asset name.

        Returns:
            tuple: Information about the asset if open.
        """
        instruments = await self.get_instruments()
        for i in instruments:
            if asset_name == i[1]:
                return i[0], i[2].replace("\n", ""), i[14]

    async def get_all_assets(self):
        instruments = await self.get_instruments()
        for i in instruments:
            if i[0] != "":
                self.codes_asset[i[1]] = i[0]

        return self.codes_asset

    async def get_candles(
            self, asset: str,
            end_from_time: Optional[float] = None,
            offset: int = 0,
            period: int = 60,
            progressive: bool = False
    ):
        """
        Get candles data asynchronously for a specified asset.

        Args:
            asset (str): Asset name.
            end_from_time (float, optional): End time for fetching candles (default is current time).
            offset (int, optional): Offset for fetching candles (default is 0).
            period (int, optional): Period for fetching candles (default is 60).
            progressive (bool, optional): Whether to fetch candles (default is False).

        Returns:
            list: List of candles data.
        """
        if end_from_time is None:
            end_from_time = time.time()
        index = expiration.get_timestamp()
        self.api.candles.candles_data = None
        await self.start_candles_stream(asset, period)
        self.api.settings_apply(asset, period)
        self.api.get_candles(asset, index, end_from_time, offset, period)
        while True:
            while self.api.candles.candles_data is None:
                await asyncio.sleep(0.2)
            if self.api.candles.candles_data is not None:
                break

        candles = self.prepare_candles(asset, period)
        if progressive:
            return self.api.historical_candles.get("data", {})

        return candles

    async def get_history_line(self, asset: str, end_from_time: Optional[float] = None, offset: int = 60):
        """
        Get history candles data asynchronously for a specified asset.

        Args:
            asset (str): Asset name.
            end_from_time (float, optional): End time for fetching candles (default is current time).
            offset (int, optional): Offset for fetching candles (default is 60).

        Returns:
            list: List of candles data history by timeframe.
        """
        if end_from_time is None:
            end_from_time = time.time()
        index = expiration.get_timestamp()
        # self.api.current_asset = asset
        self.api.historical_candles = None
        await self.start_candles_stream(asset)
        self.api.get_history_line(self.codes_asset[asset], index, end_from_time, offset)
        while True:
            while self.api.historical_candles is None:
                await asyncio.sleep(0.2)
            if self.api.historical_candles is not None:
                break

        return self.api.historical_candles

    async def get_candles_v2(self, asset: str, period: int):
        """
        Get candles data version 2 asynchronously for a specified asset.

        Args:
            asset (str): Asset name.
            period (int): Period for fetching candles.

        Returns:
            list: List of candles data.
        """
        self.api.candle_v2_data[asset] = None
        await self.start_candles_stream(asset, period)
        self.api.settings_apply(asset, period)
        while self.api.candle_v2_data[asset] is None:
            await asyncio.sleep(0.2)
        candles = self.prepare_candles(asset, period)

        return candles

    def prepare_candles(self, asset: str, period: int):
        """
        Prepare candles data for a specified asset.

        Args:
            asset (str): Asset name.
            period (int): Period for fetching candles.

        Returns:
            list: List of prepared candles data.
        """
        candles_data = calculate_candles(self.api.candles.candles_data, period)
        candles_v2_data = process_candles_v2(self.api.candle_v2_data, asset, candles_data)
        new_candles = merge_candles(candles_v2_data)

        return new_candles

    async def connect(self):
        """
        Connect to Quotex API asynchronously.

        Returns:
            tuple: Connection status and reason.
        """
        self.api = QuotexAPI(
            self.host,
            self.email,
            self.password,
            self.lang,
            self.session_data,
            self.auto_2_fa,
            auto_logout=self.auto_logout,
            user_data_dir=self.user_data_dir,
            resource_path=self.resource_path
        )
        await self.close()
        trace_ws = self.debug_ws_enable
        global_value.SSID = self.session_data.get("token")
        if not self.session_data.get("token"):
            await self.api.authenticate()
        self.api.current_asset = self.asset_default
        self.api.current_period = self.period_default
        check, reason = await self.api.connect(
            self.account_is_demo, debug_ws=trace_ws
        )
        if not await self.check_connect():
            logger.debug("Reconnecting on websocket")
            return await self.connect()

        return check, reason

    async def reconnect(self):
        await self.api.authenticate()

    def set_account_mode(self, balance_mode: str = "PRACTICE"):
        """
        Set active account mode.

        Args:
            balance_mode (str, optional): Balance mode (default is "PRACTICE").
        """
        if balance_mode.upper() == "REAL":
            self.account_is_demo = 0
        elif balance_mode.upper() == "PRACTICE":
            self.account_is_demo = 1
        else:
            logger.error("ERROR: Invalid mode")
            exit(0)

    def change_account(self, balance_mode: str):
        """Change the active account between `real` or `practice`.

        Args:
            balance_mode (str): The mode to set the account to; either "REAL" or "PRACTICE".
        """
        self.account_is_demo = 0 if balance_mode.upper() == "REAL" else 1
        self.api.change_account(self.account_is_demo)

    async def edit_practice_balance(self, amount: float = None):
        """Edit the practice balance to the specified amount.

        Args:
            amount (float, optional): The amount to set the practice balance to. If None, it does not change.

        Returns:
            The response from the API after editing the balance.
        """
        self.api.training_balance_edit_request = None
        self.api.edit_training_balance(amount)
        while self.api.training_balance_edit_request is None:
            await asyncio.sleep(0.2)

        return self.api.training_balance_edit_request

    async def get_balance(self):
        """Retrieve the current balance of the account.

        Returns:
            float: The current balance, adjusted by any profit from operations.
        """
        if not self.api.account_balance:
            while True:
                await asyncio.sleep(0.2)
        balance = self.api.account_balance.get("liveBalance")
        if self.api.account_type > 0:
            balance = self.api.account_balance.get("demoBalance")

        return float(f"{truncate(balance + self.get_profit(), 2):.2f}")

    async def get_profile(self):
        """Fetch the user profile information.

        Returns:
            The user profile data from the API.
        """
        return await self.api.get_user_profile()

    async def get_history(self):
        """Get the trader's history based on account type.

        Returns:
            The trading history from the API.
        """
        account_type = "demo" if self.account_is_demo else "live"
        return await self.api.get_trader_history(account_type, page_number=1)

    async def buy(self, amount: float, asset: str, direction: str, duration: int):
        """Buy a binary option.

        Args:
            amount (float): The amount to invest.
            asset (str): The asset to buy.
            direction (str): The direction of the option (e.g., "call" or "put").
            duration (int): The duration in seconds for the option.

        Returns:
            tuple: A tuple containing the status of the buy operation and whether it was successful.
        """
        if isinstance(amount, float) and amount.is_integer():
            amount = int(amount)
        request_id = expiration.get_timestamp()
        self.api.buy_id = None
        await self.start_candles_stream(asset, duration)
        self.api.buy(amount, asset, direction, duration, request_id)
        count = 0.2
        while self.api.buy_id is None:
            count += 0.2
            if count > duration:
                status_buy = False
                break
            await asyncio.sleep(0.2)
            if global_value.check_websocket_if_error:
                return False, global_value.websocket_error_reason
        else:
            status_buy = True
        return status_buy, self.api.buy_successful

    async def open_pending(self, amount: float, asset: str, direction: str, duration: int, open_time: str = None):
        """
        Initiates a pending trade order for a specified financial asset.

        This asynchronous method schedules a trade order that will execute under certain conditions,
        specifying the investment amount, asset, trade direction, and duration.

        Args:
            amount (float): The amount to invest in the pending order.
            asset (str): The symbol of the financial asset to trade (e.g., 'EURUSD').
            direction (str): The trade direction, either 'buy' or 'sell'.
            duration (int): The duration of the trade in seconds.
            open_time (str): The time when the trade was opened.

        Returns:
            dict: A dictionary containing details of the pending order, including its status and identifier.

        Raises:
            ValueError: If any of the provided parameters are invalid or out of acceptable ranges.
            ConnectionError: If there is a failure in communicating with the trading server.

        Example:
        ```python
        result = await trader.open_pending(100.0, 'EURUSD', 'buy', 60)
        print(result)
        ```
        """
        self.api.pending_id = None
        user_settings = await self.get_profile()
        offset_zone = user_settings.offset
        open_time = expiration.get_next_timeframe(
            int(self.api.timesync.server_timestamp),
            offset_zone,
            duration,
            open_time
        )
        self.api.open_pending(amount, asset, direction, duration, open_time)
        count = 0.2
        while self.api.pending_id is None:
            count += 0.2
            if count > duration:
                status_buy = False
                break
            await asyncio.sleep(0.2)
            if global_value.check_websocket_if_error:
                return False, global_value.websocket_error_reason
        else:
            status_buy = True
            self.api.instruments_follow(amount, asset, direction, duration, open_time)

        return status_buy, self.api.pending_successful

    async def sell_option(self, options_ids: Union[list, int]):
        """Sell a specified asset on Quotex.

        Args:
            options_ids (Union[list, int]): The ID(s) of the option(s) to sell.

        Returns:
            The response from the API after selling the option.
        """
        self.api.sell_option(options_ids)
        self.api.sold_options_respond = None
        while self.api.sold_options_respond is None:
            await asyncio.sleep(0.2)
        return self.api.sold_options_respond

    def get_payment(self):
        """Get payment details from the Quotex server.

        Returns:
            dict: A dictionary containing payment information for each asset.
        """
        assets_data = {}
        for i in self.api.instruments:
            assets_data[i[2].replace("\n", "")] = {
                "turbo_payment": i[18],
                "payment": i[5],
                "profit": {
                    "1M": i[-9],
                    "5M": i[-8]
                },
                "open": i[14]
            }
        return assets_data

    def get_payout_by_asset(self, asset_name: str, timeframe: str = "1"):
        """Get payout details from the Quotex server.

        Returns:
            int: A payout information for specific asset.
        """
        assets_data = {}
        for i in self.api.instruments:
            if asset_name == i[1]:
                assets_data[i[1].replace("\n", "")] = {
                    "turbo_payment": i[18],
                    "payment": i[5],
                    "profit": {
                        "1M": i[-9],
                        "5M": i[-8]
                    },
                    "open": i[14]
                }
                break

        data = assets_data.get(asset_name)
        if timeframe == "all":
            return data.get("profit")

        return data.get("profit").get(f"{timeframe}M")

    async def get_leader_ranking(self):
        """Fetch the leader ranking data.

        Returns:
            The leader ranking information from the API.
        """
        self.api.subscribe_leader()
        while not self.api.top_list_leader:
            await asyncio.sleep(0.2)
        return self.api.top_list_leader

    async def get_profit_today(self):
        """Retrieve today's profit.

        Returns:
            The profit made today as per the API response.
        """
        self.api.subscribe_leader()
        while self.api.profit_today is None:
            await asyncio.sleep(0.2)
        return self.api.profit_today

    async def start_remaining_time(self):
        """Start a countdown timer until the candle expiration.

        Prints the remaining time in seconds.
        """
        now_stamp = expiration.timestamp_to_datetime(expiration.get_timestamp())
        expiration_stamp = expiration.timestamp_to_datetime(self.api.timesync.server_timestamp)
        remaining_time = int((expiration_stamp - now_stamp).total_seconds())
        while remaining_time >= 0:
            remaining_time -= 1
            print(f"\rRestando {remaining_time if remaining_time > 0 else 0} segundos ...", end="")
            await asyncio.sleep(1)

    async def check_win(self, id_number: int):
        """Check if the trade is a win based on its ID.

        Args:
            id_number (int): The ID of the trade to check.

        Returns:
            bool: True if the trade is a win, False otherwise.
        """
        task = asyncio.create_task(
            self.start_remaining_time()
        )
        while True:
            data_dict = self.api.listinfodata.get(id_number)
            if data_dict and data_dict.get("game_state") == 1:
                break
            await asyncio.sleep(0.2)
        task.cancel()
        self.api.listinfodata.delete(id_number)
        return data_dict["win"]

    async def get_server_time(self):
        """Retrieve the server's current date and time.

        Returns:
            tuple: A tuple containing the server date and time.
        """
        profile_data = await self.api.get_user_profile()
        server_date, server_time = expiration.get_increment_timestamp(profile_data.offset)
        return server_date, server_time

    async def start_candles_stream(self, asset: str = "EURUSD", period: int = 0):
        """Start streaming candle data for a specified asset.

        Args:
            asset (str): The asset to stream data for.
            period (int, optional): The period for the candles. Defaults to 0.
        """
        self.api.current_asset = asset
        self.api.subscribe_realtime_candle(asset, period)
        self.api.chart_notification(asset)
        self.api.follow_candle(asset)

    async def store_settings_apply(self, asset, period=0, deal=5, percent_mode=False, percent_deal=1):
        """
        Applies trading settings for a specific asset and retrieves the updated investment settings.

        This function sets up trading parameters for the specified asset, including the period,
        deal amount, and percentage mode if applicable. It then waits for the updated investment
        settings to be available and returns them.

        Args:
            asset (str): The asset for which to apply the settings.
            period (int, optional): The trading period in seconds. Defaults to 0.
            deal (float, optional): The fixed amount for each deal. Defaults to 5.
            percent_mode (bool, optional): Whether to enable percentage-based deals. Defaults to False.
            percent_deal (float, optional): The percentage value for percentage-based deals. Defaults to 1.

        Returns:
            dict: The updated investment settings for the specified asset.

        Raises:
            ValueError: If the investment settings cannot be retrieved after multiple attempts.

        Notes:
            - This function continuously refreshes the settings until they are available.
            - A sleep interval is used to prevent excessive API calls.
        """
        self.api.current_asset = asset
        self.api.settings_apply(
            asset,
            period,
            deal=deal,
            percent_mode=percent_mode,
            percent_deal=percent_deal
        )
        await asyncio.sleep(1)
        while True:
            self.api.refresh_settings()
            if self.api.settings_list:
                investments_settings = self.api.settings_list
                break
            await asyncio.sleep(0.2)

        return investments_settings

    def stop_candles_stream(self, asset: str):
        """Stop streaming candle data for a specified asset.

        Args:
            asset (str): The asset to stop streaming data for.
        """
        self.api.unsubscribe_realtime_candle(asset)
        self.api.unfollow_candle(asset)

    def start_signals_data(self):
        """Start receiving signal data from the API."""
        self.api.signals_subscribe()

    async def get_realtime_candles(self, asset: str, period: int = 0):
        """Retrieve real-time candle data for a specified asset.

        Args:
            asset (str): The asset to get candle data for.
            period (int, optional): The period for the candles. Defaults to 0.

        Returns:
            dict: A dictionary of real-time candle data.
        """

        while True:
            if self.api.candle_v2_data.get(asset):
                candles = self.prepare_candles(asset, period)
                for candle in candles:
                    self.api.real_time_candles[candle["time"]] = candle
                return self.api.real_time_candles
            await asyncio.sleep(0.2)

    async def get_realtime_price_data(self):
        """Retrieve real-time price data for a specified asset.

        Returns:
            dict: A dictionary of real-time price data.
        """
        while True:
            if self.api.realtime_price_data:
                return self.api.realtime_price_data
            await asyncio.sleep(0.2)

    async def start_realtime_price(self, asset: str, period: int = 0):
        """Start streaming real-time price data for a specified asset.

        Args:
            asset (str): The asset to stream price data for.
            period (int, optional): The period for the price data. Defaults to 0.

        Returns:
            dict: The real-time price data.
        """
        await self.start_candles_stream(asset, period)
        while True:
            if self.api.realtime_price.get(asset):
                return self.api.realtime_price
            await asyncio.sleep(0.2)

    async def get_realtime_price(self, asset: str):
        """Get the real-time price for a specified asset.

        Args:
            asset (str): The asset to get the price for.

        Returns:
            dict: The real-time price data.
        """
        return self.api.realtime_price.get(asset, {})

    async def start_realtime_sentiment(self, asset: str, period: int = 0):
        """Start receiving real-time sentiment data for a specified asset.

        Args:
            asset (str): The asset to stream sentiment data for.
            period (int, optional): The period for the sentiment data. Defaults to 0.

        Returns:
            dict: The real-time sentiment data.
        """
        await self.start_candles_stream(asset, period)
        while True:
            if self.api.realtime_sentiment.get(asset):
                return self.api.realtime_sentiment[asset]
            await asyncio.sleep(0.2)

    async def get_realtime_sentiment(self, asset: str):
        """Retrieve the real-time sentiment data for a specified asset.

        Args:
            asset (str): The asset for which to retrieve sentiment data.

        Returns:
            dict: A dictionary containing the real-time sentiment data for the asset.
        """
        return self.api.realtime_sentiment.get(asset, {})

    async def get_investments_settings(self):
        """Get the settings data for the investments from the API.

        Returns:
            list: A list containing the settings data for the investments.
        """
        await self.start_candles_stream()
        # self.api.refresh_settings()
        await asyncio.sleep(1)
        while True:
            self.api.refresh_settings()
            if self.api.settings_list:
                return self.api.settings_list
            await asyncio.sleep(1)

    def get_signal_data(self):
        """Get the current signal data from the API.

        Returns:
            dict: A dictionary containing the current signal data.
        """
        return self.api.signal_data

    def get_profit(self):
        """Retrieve the current profit from ongoing operations.

        Returns:
            float: The profit from operations; returns 0 if no profit is recorded.
        """
        return self.api.profit_in_operation or 0

    async def get_result(self, operation_id: str):
        """Check if the trade is a win based on its ID.

        Args:
            operation_id (str): The ID of the trade to check.
        Returns:
            str: win if the trade is a win, loss otherwise.
            float: The profit from operations; returns 0 if no profit is recorded.
        """
        data_history = await self.get_history()
        for item in data_history:
            if item.get("ticket") == operation_id:
                profit = float(item.get("profitAmount", 0))
                status = "win" if profit > 0 else "loss"
                return status, item

        return None, "OperationID Not Found."

    async def close(self):
        """Close the connection to the Quotex API.

        If auto logout is enabled, it will also log out the user.

        Returns:
            Any: The result of the API close operation.
        """
        if self.auto_logout:
            await self.api.logout()
        return self.api.close()
