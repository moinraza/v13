# quotexapi

Quotex API

https://github.com/user-attachments/assets/acaa0cbb-80c2-450c-9c8f-83fdbfedf0fa

### Observação Importante

Por algum motivo a cloudflare acaba identificando o acesso automatizado a api da quotex e nos
aplica um block, o que impede o sucesso ao autenticar na plataforma por meio do uso de usuário
e senha, recomendo o uso de python 3.8 ou superior para obter sucesso com essa api.
Para usuários windows é necessário instalar openssl mais recente possível, que pode ser obtido
aqui [Openssl-Windows](https://slproweb.com/products/Win32OpenSSL.html) .
Para usuários linux também é recomendada versões mais recentes possíveis do openssl, bastando
apenas executarem ```sudo apt install openssl```.

### Install

```shell
git clone https://github.com/cleitonleonel/quotexapi.git
cd quotexapi
pip install poetry
poetry install
```

### Import

```python
from quotexapi.stable_api import Quotex
```

### Login by email and password

if connect sucess return True,None

if connect fail return False,None

```python
from quotexapi.stable_api import Quotex

client = Quotex(
    email="user@gmail.com",
    password="pwd"
)
client.debug_ws_enable = False

# PRACTICE mode is default / REAL mode is optional
# client.set_account_mode("REAL")

check_connect, message = client.connect()
print(check_connect, message)
```

### All Functions

```python
import sys
import time
import json
import random
import asyncio
import logging
import numpy as np
from quotexapi.config import (
    email,
    password
)
from quotexapi.utils.processor import (
    process_candles,
    get_color
)
from quotexapi.expiration import timestamp_to_datetime
from quotexapi.stable_api import Quotex

client = Quotex(
    email=email,
    password=password
)
client.debug_ws_enable = False


# PRACTICE mode is default / REAL mode is optional
# client.set_account_mode("REAL")


def get_all_options():
    """Return a string containing the list of available options.

    Returns:
        str: A formatted string listing the available options.
    """
    return """Available options:
    - test_connection
    - get_profile
    - get_history
    - get_balance
    - get_profit_today
    - get_ranking
    - get_signal_data
    - get_payment
    - get_candles
    - get_candles_v2
    - get_candles_all_asset
    - get_candles_progressive
    - get_realtime_candles
    - get_realtime_sentiment
    - get_realtime_price
    - get_realtime_price_data
    - get_price_tracking_and_candles
    - get_investments_settings
    - store_settings_apply
    - assets_open
    - buy_simple
    - buy_and_check_win
    - buy_multiple
    - buy_pending
    - balance_refill
    - help
    """


client = Quotex(
    email=email,
    password=password,
    lang="pt"
)


async def test_connection():
    """
    Test the connection to the Quotex server and print the server time.

    This function establishes a connection to the Quotex server, checks the
    connection status, retrieves the server date and time, and then closes
    the connection.
    """
    await client.connect()
    is_connected = await client.check_connect()
    client.change_account("REAL")
    datetime_server, time_server = await client.get_server_time()
    print(
        f"Connected: {is_connected}\n"
        f"Date server: {datetime_server}\n"
        f"Time stamp server: {time_server}"
    )
    print("Exiting...")

    await client.close()


async def get_balance():
    """
    Retrieve and print the current account balance.

    This function connects to the Quotex server, retrieves the current balance,
    and prints it to the console. The connection is closed after the operation.
    """
    check_connect, reason = await client.connect()
    print(f"Connected: {check_connect}\n{reason}")
    if check_connect:
        # client.change_account("REAL")
        print("Current balance: ", await client.get_balance())

    print("Exiting...")

    await client.close()


async def get_profile():
    """
    Retrieve and display the user profile information.

    This function connects to the Quotex server, retrieves the user profile,
    and prints relevant information such as nickname, balances, profile ID,
    avatar, and country name. The connection is closed after the operation.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        profile = await client.get_profile()
        description = (
            f"\nUser: {profile.nick_name}\n"
            f"Demo Balance: {profile.demo_balance}\n"
            f"Real Balance: {profile.live_balance}\n"
            f"ID: {profile.profile_id}\n"
            f"Avatar: {profile.avatar}\n"
            f"Country: {profile.country_name}\n"
            f"Timezone: {profile.offset}"
        )
        print(description)

    print("Exiting...")

    await client.close()


async def get_history():
    """
    Retrieve and print the trading history.

    This function connects to the Quotex server, retrieves the trading history,
    and prints each entry to the console. The connection is closed after the operation.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        # client.change_account("REAL")
        history_data = await client.get_history()
        for history in history_data:
            print(history)

    print("Exiting...")

    await client.close()


async def balance_refill():
    """
    Refill the practice account balance.

    This function connects to the Quotex server and adds a specified amount
    to the practice account balance. The connection is closed after the operation.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        # client.change_account("REAL")
        result = await client.edit_practice_balance(5000)
        print(result)

    await client.close()


async def get_profit_today():
    """
    Retrieve and print today's profit.

    This function connects to the Quotex server, retrieves the profit for today,
    and prints it to the console. The connection is closed after the operation.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        # client.change_account("REAL")
        profit_today = await client.get_profit_today()
        print(f"Profit Today: $ {profit_today.get('profit'):.2f}")

    print("Exiting...")

    await client.close()


async def get_ranking():
    """
    Retrieve and display the leader ranking.

    This function connects to the Quotex server, retrieves the leader ranking,
    and prints the top leaders' information, including nickname, ID, country, and profit.
    The connection is closed after the operation.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        # client.change_account("REAL")
        ranking = await client.get_leader_ranking()
        print(f"\nTop Leaders Ranking:\n")
        for leader in ranking.get('list'):
            print(
                f"{'#' * 20}\n"
                f"NickName: {leader[4]}\n"
                f"ID: {leader[0]}\n"
                f"Country: {leader[1]}\n"
                f"Profit: {leader[2]}\n"
            )

    print("Exiting...")

    await client.close()


async def buy_simple():
    """
    Place a simple buy order for an asset.

    This function connects to the Quotex server, checks if the specified asset
    is open, and places a buy order with defined parameters. The current balance
    is printed after the operation, and the connection is closed.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        # client.change_account("REAL")
        amount = 50
        asset = "AUDCAD"  # "EURUSD_otc"
        direction = "call"
        duration = 60  # in seconds
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        print(asset_name, asset_data)
        if asset_data[2]:
            print("OK: Asset is open.")
            status, buy_info = await client.buy(amount, asset_name, direction, duration)
            print(status, buy_info)
        else:
            print("ERROR: Asset is closed.")
        print("Current balance: ", await client.get_balance())

    print("Exiting...")

    await client.close()


async def get_result():
    """
    Waits for the result

    This function connects to the Quotex server, waits for the result,
    and checks if the trade was won or lost. The profit or loss is
    printed accordingly and the connection is closed.
    """

    check_connect, reason = await client.connect()
    if check_connect:
        status, operation_info  = await client.get_result('52e04b13-c67c-4cd1-9b68-e1d1f5e968ea')
        print(status, operation_info)

    print("Exiting...")

    await client.close()


async def buy_and_check_win():
    """
    Place a buy order and check if it was won.

    This function connects to the Quotex server, places a buy order for a specified asset,
    waits for the result, and checks if the trade was won or lost. The profit or loss is
    printed accordingly. The current balance is displayed after the operation, and the
    connection is closed.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        # client.change_account("REAL")
        print("Current balance: ", await client.get_balance())
        amount = 50
        asset = "EURUSD_otc"  # "EURUSD_otc"
        direction = "call"
        duration = 60  # in seconds
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        print(asset_name, asset_data)
        if asset_data[2]:
            print("OK: Asset is open.")
            status, buy_info = await client.buy(amount, asset_name, direction, duration)
            print(status, buy_info)
            if status:
                print("Waiting for result...")
                if await client.check_win(buy_info["id"]):
                    print(f"\nWin!!! \nWe won, buddy!!!\nProfit: R$ {client.get_profit()}")
                else:
                    print(f"\nLoss!!! \nWe lost, buddy!!!\nLoss: R$ {client.get_profit()}")
            else:
                print("Operation failed!!!")
        else:
            print("ERROR: Asset is closed.")
        print("Current balance: ", await client.get_balance())

    print("Exiting...")

    await client.close()


async def buy_multiple(orders=10):
    """
    Executes multiple buy orders for randomly selected assets from a predefined list.

    Parameters:
        orders (int): The number of buy orders to execute. Default is 10.

    This function connects to the client, randomly selects an asset from the
    order list, and attempts to buy it. It checks if the asset is open and
    prints the status of each buy order, as well as the current balance.
    It waits for 2 seconds between each order.
    """
    order_list = [
        {"amount": 5, "asset": "EURUSD", "direction": "call", "duration": 60},
        {"amount": 10, "asset": "AUDCAD_otc", "direction": "put", "duration": 60},
        {"amount": 15, "asset": "AUDJPY_otc", "direction": "call", "duration": 60},
        {"amount": 20, "asset": "AUDUSD", "direction": "put", "duration": 60},
        {"amount": 25, "asset": "CADJPY_otc", "direction": "call", "duration": 60},
        {"amount": 30, "asset": "EURCHF_otc", "direction": "put", "duration": 60},
        {"amount": 35, "asset": "EURGBP_otc", "direction": "call", "duration": 60},
        {"amount": 40, "asset": "EURJPY", "direction": "put", "duration": 60},
        {"amount": 45, "asset": "GBPAUD_otc", "direction": "call", "duration": 60},
        {"amount": 50, "asset": "GBPJPY_otc", "direction": "put", "duration": 60},
    ]
    check_connect, reason = await client.connect()
    for i in range(0, orders):
        print("\n/", 80 * "=", "/", end="\n")
        print(f"OPENING ORDER: {i + 1}")
        order = random.choice(order_list)
        print(order)
        if check_connect:
            # client.change_account("REAL")
            asset_name, asset_data = await client.get_available_asset(order["asset"])
            if asset_data[2]:
                print("OK: Asset is open.")
                order["asset"] = asset_name
                status, buy_info = await client.buy(**order)
                print(status, buy_info)
            else:
                print("ERROR: Asset is closed.")
            print("Current balance: ", await client.get_balance())
            await asyncio.sleep(2)
    print("\n/", 80 * "=", "/", end="\n")

    print("Exiting...")

    await client.close()


async def buy_pending():
    """
    Executes a pending buy order for a trading asset after verifying the connection and asset availability.

    This method connects to the trading client, checks if a specific asset is open for trading,
    and attempts to execute a pending buy order with predefined parameters.
    If the asset is closed, an error message is displayed. After the order attempt,
    the current account balance is retrieved and displayed.

    Workflow:
    1. Verifies the connection with the trading client.
    2. Retrieves availability information for the specified asset.
    3. Attempts to execute a pending buy order if the asset is open.
    4. Displays the current account balance.
    5. Closes the connection to the trading client.

    Fixed Parameters:
        - Amount: 50
        - Asset: "AUDCAD"
        - Direction: "call"
        - Duration: 60 seconds

    Prints:
        - Connection status message.
        - Asset information (name and availability data).
        - Result of the pending buy order attempt.
        - Current account balance.

    Raises:
        Exception: If an error occurs during the connection or buy operation.

    Returns:
        None
    """
    check_connect, message = await client.connect()
    if check_connect:
        # client.change_account("REAL")
        amount = 50
        asset = "AUDCAD"  # "EURUSD_otc"
        direction = "call"
        duration = 60  # in seconds

        # Format d/m h:m
        open_time = "16/12 15:51"  # If None, then this will be set to the equivalent of one minute in duration

        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        print(asset_name, asset_data)
        if asset_data[2]:
            print("OK: Asset is open.")
            status, buy_info = await client.open_pending(amount, asset_name, direction, duration, open_time)
            print(status, buy_info)
        else:
            print("ERROR: Asset is closed.")
        print("Current balance: ", await client.get_balance())

        print("Exiting...")

    await client.close()


async def trade_and_monitor():
    """
    Place a buy order and check if it was won.

    This function connects to the Quotex server, places a buy order for a specified asset,
    waits for the result, and checks if the trade was won or lost. The profit or loss is
    printed accordingly and the connection is closed.
    """
    check_connect, message = await client.connect()
    if check_connect:
        amount = 50
        asset = "AUDCAD"
        direction = "call"
        duration = 60  # in seconds

        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        print(asset_name, asset_data)

        if asset_data[2]:
            print("OK: Asset is open.")
            status, buy_info = await client.buy(amount, asset_name, direction, duration)
            if status:
                open_price = buy_info.get('openPrice')
                close_timestamp = buy_info.get('closeTimestamp')
                print("Open Price:", open_price)

                await asyncio.sleep(duration)

                await client.start_realtime_price(asset, 60)

                prices = await client.get_realtime_price(asset_name)

                if prices:
                    current_price = prices[-1]['price']
                    current_timestamp = prices[-1]['time']
                    print(f"Current Time: {int(current_timestamp)}, Close Time: {close_timestamp}")
                    print(f"Current Price: {current_price}, Open Price: {open_price}")

                    if (direction == "call" and current_price > open_price) or (
                            direction == "put" and current_price < open_price):
                        print("Result: WIN")
                        return 'Win'
                    elif (direction == "call" and current_price <= open_price) or (
                            direction == "put" and current_price >= open_price):
                        print("Result: LOSS")
                        return 'Loss'
                    else:
                        print("Result: DOJI")
                        return 'Doji'
                else:
                    print("Not a price direction.")
            else:
                print("Operation failed!!!")
        else:
            print("ERRO: Asset is closed.")

    else:
        print("Unable to connect to client.")

    print("Exiting...")

    await client.close()


async def sell_option():
    """
    Sells a predefined option on a specified asset.

    This function connects to the client, checks if the specified asset
    is open, and if so, executes a buy order followed by selling the option
    associated with that buy order. It prints the status of the transaction
    and the current balance.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        # client.change_account("REAL")
        amount = 30
        asset = "EURUSD_otc"  # "EURUSD_otc"
        direction = "put"
        duration = 1000  # in seconds
        asset_name, asset_data = await client.get_available_asset(asset)
        if asset_data[2]:
            print("OK: Asset is open.")
            status, buy_info = await client.buy(amount, asset_name, direction, duration)
            print(status, buy_info)
            await client.sell_option(buy_info["id"])
        else:
            print("ERROR: Asset is closed.")
        print("Current balance: ", await client.get_balance())

    print("Exiting...")

    await client.close()


async def assets_open():
    """
    Checks and prints the status of all available assets.

    This function connects to the client and iterates over all asset names,
    checking if each asset is open or closed. It prints the name and status
    of each asset.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        print("Check Asset Open")
        for i in client.get_all_asset_name():
            print(i[1])
            print(i[1], await client.check_asset_open(i[0]))

    print("Exiting...")

    await client.close()


async def get_payment():
    """
    Retrieves and prints payment information for all assets.

    This function connects to the client, fetches payment data for each
    asset, and prints the profit status along with whether the asset is
    opened or closed.
    """
    check_connect, message = await client.connect()
    if check_connect:
        all_data = client.get_payment()
        for asset_name in all_data:
            asset_data = all_data[asset_name]
            profit = f'\nProfit 1+ : {asset_data["profit"]["1M"]} | Profit 5+ : {asset_data["profit"]["5M"]}'
            status = " ==> Opened" if asset_data["open"] else " ==> Closed"
            print(asset_name, asset_data["payment"], status, profit)
            print("-" * 38)

    print("Exiting...")

    await client.close()


async def get_payout():
    """
    Retrieves and prints payout information for specific asset.

    This function connects to the client, fetches payout for specific
    asset, and prints the profit status along with whether the asset is
    opened or closed.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        asset_data = await client.check_asset_open("EURUSD_otc")
        print(asset_data)

    print("Saindo...")

    await client.close()


async def get_payout_by_asset():
    """
    Retrieves and prints payout information for specific asset.

    This function connects to the client, fetches payout for specific
    asset by timeframe and prints the profit status along with whether the asset is.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        asset_data = client.get_payout_by_asset("AUDCAD_otc")
        print(asset_data)

    print("Exiting...")

    await client.close()


async def get_candles():
    """
    Fetches and prints the candle data for a specified asset.

    This function connects to the client, retrieves candles for the asset
    "EURUSD_otc" over a defined period, and determines the color of each
    candle based on its data. It prints the colors of the candles or a
    message if no candles are available.
    """
    check_connect, message = await client.connect()
    if check_connect:
        candles_color = []
        asset = "EURUSD_otc"
        offset = 3600  # in seconds
        period = 5  # in seconds [5, 10, 15, 30, 60, 120, 180, 240, 300, 600, 900, 1800, 3600, 14400, 86400]
        end_from_time = time.time()
        candles = await client.get_candles(asset, end_from_time, offset, period)

        if len(candles) > 0:

            if not candles[0].get("open"):
                candles = process_candles(candles, period)

            # print(asset, candles)

            for candle in candles:
                color = get_color(candle)
                candles_color.append(color)

            print(candles)
            # print(candles_color if len(candles_color) > 0 else "")
        else:
            print("No candles.")

    print("Exiting...")

    await client.close()


async def get_candles_progressive():
    """
    Fetches and prints the progressive candle data for a specified asset.

    This function connects to the client and retrieves candles for the
    asset "EURUSD_otc" in a progressive manner, collecting data over
    two iterations. It prints the colors of the candles and the
    list of candle data retrieved.
    """
    start_time = time.time()
    check_connect, reason = await client.connect()
    if check_connect:
        print("Connection is Successful.")
        asset = "AUDCAD"
        offset = 3600  # in seconds
        period = 60  # in seconds [5, 10, 15, 30, 60, 120, 180, 240, 300, 600, 900, 1800, 3600, 14400, 86400]
        days = 1
        candles_color = []
        max_candles = (((days * 24) * (60 * 60)) // period)
        print(max_candles)
        end_from_time = int(time.time())
        print("Starting candles...")
        candles = await client.get_candles(asset, end_from_time, offset, period)
        list_candles = candles[::-1]
        seen_times = set()
        if list_candles:
            end_from_time = list_candles[-1]["time"]
            while len(list_candles) < max_candles:
                candles = await client.get_candles(asset, end_from_time, offset, period, progressive=True)
                if candles:
                    end_from_time = candles[0]["time"]
                    if end_from_time not in seen_times:
                        if not candles[0].get("open"):
                            candles = process_candles(candles, period)

                        candles = candles[::-1]
                        for candle in candles:
                            if not candle in list_candles:
                                list_candles.append(candle)

                            if len(list_candles) >= max_candles:
                                break

                        seen_times.add(end_from_time)

                        print(f'Start: {candles[-1]["time"]} End: {candles[0]["time"]}')
                        epoch_candle = timestamp_to_datetime(end_from_time)
                        print(epoch_candle)

        list_candles = list_candles[::-1]
        total_candles = len(list_candles)
        end_time = int(time.time() - start_time)
        print(f"\nCandles Total: {total_candles}")
        # print(list_candles)

        for candle in list_candles:
            color = get_color(candle)
            candles_color.append(color)

        print(candles_color if len(candles_color) > 0 else "")
        first_candle = list_candles[-1]["time"]
        last_candle = list_candles[0]["time"]
        print(
             f"Start Candle: {timestamp_to_datetime(first_candle)} \n"
             f"End Candle: {timestamp_to_datetime(last_candle)} "
        )
        print(f"Lasted {end_time} seconds")

    print("Exiting...")

    await client.close()


async def get_candles_v2():
    """
    Fetches and prints the latest candle data for a specified asset using v2 API.

    This function connects to the client and retrieves candle data for
    the asset "EURUSD" using the version 2 of the candle API. It prints
    the candle data and their corresponding colors.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        asset = "EURUSD_otc"
        candles = await client.get_candles_v2(asset, 60)
        candles_color = []
        # print(candles)
        for candle in candles[1:]:
            color = get_color(candle)
            candles_color.append(color)
        print(candles_color)

    print("Exiting...")

    await client.close()


async def get_candles_all_asset():
    """
    Continuously fetches and prints candle data for all asset.

    This function connects to the client, checks if the asset
    is open, and if so, enters a loop to retrieve and print candle data.
    It waits for a specified interval between requests.
    """
    check_connect, message = await client.connect()
    if check_connect:
        offset = 3600  # in seconds
        period = 60    # in seconds
        codes_asset = await client.get_all_assets()
        for asset in codes_asset.keys():
            print(asset)
            asset_name, asset_data = await client.get_available_asset(asset)
            if asset_data[2]:
                print(asset_name, asset_data)
                print(f"Check Asset {asset_name} Open")
                end_from_time = time.time()
                candles = await client.get_candles(asset, end_from_time, offset, period)
                print(candles)
            await asyncio.sleep(0.2)

    print("Exiting...")

    await client.close()


async def get_realtime_candles():
    """
    Continuously fetches and prints real-time candle data for a specified asset.

    This function connects to the client, checks if the asset "EURUSD"
    is open, and if so, enters a loop to retrieve and print real-time
    candle data. It waits for a specified interval between requests.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        period = 5  # in seconds [60, 120, 180, 240, 300, 600, 900, 1800, 3600, 14400, 86400]
        asset = "EURUSD"
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        if asset_data[2]:
            print("Check Asset Open")
            await client.start_candles_stream(asset_name, period)
            while True:
                candles = await client.get_realtime_candles(asset_name, period)
                # print(candles)
                inputs = {
                    'open': np.array([]),
                    'high': np.array([]),
                    'low': np.array([]),
                    'close': np.array([])
                }
                for timestamp in candles:
                    inputs["open"] = np.append(inputs["open"], candles[timestamp]["open"])
                    inputs["high"] = np.append(inputs["open"], candles[timestamp]["high"])
                    inputs["low"] = np.append(inputs["open"], candles[timestamp]["low"])
                    inputs["close"] = np.append(inputs["open"], candles[timestamp]["close"])

                print(inputs)
                await asyncio.sleep(0.5)
        else:
            print("Asset is closed.")

    print("Exiting...")

    await client.close()


async def get_realtime_price_data():
    """
    Continuously fetches and prints real-time price data for a specified asset.

    This function connects to the client, checks if the asset "EURUSD"
    is open, and if so, enters a loop to retrieve and print real-time
    price data. It waits for a specified interval between requests.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        period = 60  # in seconds [60, 120, 180, 240, 300, 600, 900, 1800, 3600, 14400, 86400]
        asset = "EURUSD"
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        if asset_data[2]:
            print("Check Asset Open")
            await client.start_realtime_price(asset_name, period)
            while True:
                price_data = await client.get_realtime_price_data()
                print(price_data)
                await asyncio.sleep(0.2)
        else:
            print("Asset is closed.")

    print("Exiting...")

    await client.close()


async def get_realtime_sentiment():
    """
    Continuously fetches and prints real-time sentiment data for a specified asset.

    This function connects to the client, checks if the asset "EURJPY_otc"
    is open, and if so, starts a loop to retrieve and print real-time
    sentiment data for the asset, displaying buy and sell sentiment values.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        asset = "EURUSD_otc"
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        if asset_data[2]:
            print("Check Asset Open")
            await client.start_realtime_sentiment(asset_name, 60)
            while True:
                candle_sentiment = await client.get_realtime_sentiment(asset_name)
                print(
                    f"Asset: {asset_name} "
                    f"Sell: {candle_sentiment['sentiment']['sell']} "
                    f"Buy: {candle_sentiment['sentiment']['buy']}",
                    end="\r"
                )
                await asyncio.sleep(0.5)
        else:
            print("Asset is closed.")

    print("Exiting...")

    await client.close()


async def get_realtime_price():
    """
    Continuously fetches and prints real-time price data for a specified asset.

    This function connects to the client, checks if the asset "EURJPY_otc"
    is open, and if so, enters a loop to fetch and print the latest price
    data for the asset at regular intervals.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        asset = "EURJPY_otc"
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        if asset_data[2]:
            print("Check Asset Open")
            await client.start_realtime_price(asset_name, 60)
            while True:
                candle_price = await client.get_realtime_price(asset_name)
                print(
                    f"Asset: {asset_name} "
                    f"Time: {candle_price[-1]['time']} "
                    f"Price: {candle_price[-1]['price']}",
                    end="\r"
                )
                await asyncio.sleep(0.5)
        else:
            print("Asset is closed.")

    print("Exiting...")

    await client.close()


async def get_price_tracking_and_candles():
    """
    Tracks real-time price updates for a specific asset and retrieves candlestick data.

    This function connects to the client, verifies if the specified asset is available
    and open for trading, and starts tracking real-time price updates. It retrieves
    candlestick data at regular intervals based on the specified period.

    Raises:
        ConnectionError: If the client fails to connect.
        ValueError: If the asset data is invalid or unavailable.

    Returns:
        None
    """
    check_connect, message = await client.connect()
    if check_connect:
        asset = "CHFJPY_otc"
        offset = 3600  # in seconds
        period = 60  # in seconds [5, 10, 15, 30, 60, 120, 180, 240, 300, 600, 900, 1800, 3600, 14400, 86400]
        end_from_time = time.time()
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        if asset_data[2]:
            print("OK: Asset is open.")
            await client.start_realtime_price(asset, 60)
            while True:
                prices = await client.get_realtime_price(asset)

                if not prices:
                    continue

                """print(
                    f"Asset: {asset} "
                    f"Time: {prices[-1]['time']} "
                    f"Price: {prices[-1]['price']}",
                    end="\r"
                )"""

                print("Searching for prices...", end="\r")
                if int(prices[-1]['time']) % period == 0:
                    candles = await client.get_candles(asset, end_from_time, offset, period)
                    candles_data = candles
                    if len(candles_data) > 0:

                        if not candles_data[0].get("open"):
                            candles = process_candles(candles_data, period)
                            candles_data = candles

                        print(candles_data[-3:])

                        await asyncio.sleep(1)

                await asyncio.sleep(0.1)
        else:
            print("Asset is closed.")


async def get_investments_settings():
    """
    Get the settings data for the investments from the API.

    This function connects to the client, get the settings data for the investments.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        print("Check Asset Open")
        investments = await client.get_investments_settings()
        print(investments[0]['settings'])

    print("Exiting...")


async def store_settings_apply():
    """
    Connects to the client, checks the availability and status of a specific asset,
    and applies store settings if the asset is open.

    This function performs the following steps:
    1. Connects to the client asynchronously.
    2. Checks if a specific asset ('EURUSD_otc') is available and open.
    3. If the asset is open, applies trading settings such as deal amount, period, and percent mode.
    4. Outputs relevant information including asset data and applied settings.

    Settings applied:
        - Asset: 'EURUSD_otc'
        - Period: 60 seconds
        - Deal amount: 50
        - Percent mode: Enabled
        - Percent deal: 20%

    Prints:
        - Asset name and data if successfully retrieved.
        - Applied investment settings if the asset is open.
        - A message indicating whether the asset is closed.
        - "Exiting..." upon completion.

    Raises:
        Exception: If the connection or asset retrieval fails.

    """
    check_connect, reason = await client.connect()
    if check_connect:
        asset = "BRLUSD"
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        print(asset_name, asset_data)
        if asset_data[2]:
            print("Check Asset Open")
            investments = await client.store_settings_apply(
                asset_name,
                period=60,
                deal=100,
                percent_mode=False,
                percent_deal=1
            )
            print(investments[0]['settings'])
        else:
            print("Asset is closed.")

    print("Exiting...")


async def get_signal_data():
    """
    Continuously fetches and prints signal data.

    This function connects to the client, starts the signal data collection,
    and enters a loop to retrieve and print the latest signal data in a
    formatted JSON structure.
    """
    check_connect, reason = await client.connect()
    if check_connect:
        client.start_signals_data()
        while True:
            signals = client.get_signal_data()
            if signals:
                print(json.dumps(signals, indent=4))
            await asyncio.sleep(1)

    print("Exiting...")

    await client.close()


async def main():
    """
    Main entry point for executing trading operations based on command-line arguments.

    This function processes command-line arguments to determine which operation
    to execute, setting up logging if needed, and calling the appropriate
    async function based on the specified option.
    """
    args = sys.argv
    if len(args) == 1:
        print(f"Uso: {'./main' if getattr(sys, 'frozen', False) else 'python main.py'} <opção>")
        sys.exit(1)
    elif len(args) == 3 and args[2] == "debug":
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(message)s'
        )

    async def execute(argument):
        match argument:
            case "test_connection":
                return await test_connection()
            case "get_profile":
                return await get_profile()
            case "get_history":
                return await get_history()
            case "get_balance":
                return await get_balance()
            case "get_profit_today":
                return await get_profit_today()
            case "get_ranking":
                return await get_ranking()
            case "get_signal_data":
                return await get_signal_data()
            case "get_candles":
                return await get_candles()
            case "assets_open":
                return await assets_open()
            case "get_payment":
                return await get_payment()
            case "get_payout":
                return await get_payout()
            case "get_candles_v2":
                return await get_candles_v2()
            case "get_candles_all_asset":
                return await get_candles_all_asset()
            case "get_candles_progressive":
                return await get_candles_progressive()
            case "get_realtime_candles":
                return await get_realtime_candles()
            case "get_realtime_sentiment":
                return await get_realtime_sentiment()
            case "get_realtime_price_data":
                return await get_realtime_price_data()
            case "get_realtime_price":
                return await get_realtime_price()
            case "get_price_tracking_and_candles":
                return await get_price_tracking_and_candles()
            case "get_investments_settings":
                return await get_investments_settings()
            case "store_settings_apply":
                return await store_settings_apply()
            case "buy_simple":
                return await buy_simple()
            case "get_result":
                return await get_result()
            case "buy_and_check_win":
                return await buy_and_check_win()
            case "buy_multiple":
                return await buy_multiple()
            case "buy_pending":
                return await buy_pending()
            case "balance_refill":
                return await balance_refill()
            case "help":
                return print(get_all_options())
            case _:
                return print("Invalid option. Use 'help' to get the list of options.")

    option = sys.argv[1]
    await execute(option)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Shutting down the program.")
    finally:
        loop.close()

```
