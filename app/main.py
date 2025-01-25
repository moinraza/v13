from fastapi import FastAPI, Request, HTTPException
import time
import logging
from datetime import datetime, timezone, timedelta
from app.quotexapi.config import email, password
from app.quotexapi.stable_api import Quotex
from app.quotexapi.utils.processor import process_candles
from threading import Lock
import asyncio
from typing import List, Dict
from websocket._exceptions import WebSocketConnectionClosedException
from app.quotexapi.expiration import timestamp_to_datetime
import random
from app import constants

app = FastAPI()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Quotex client
client = Quotex(
    email=email,
    password=password,
    lang="pt"
)

# Cache setup
assets_cache = {
    "data": [],
    "last_updated": float(0)
}
cache_lock = Lock()
CACHE_TTL = 300  # Cache Time-To-Live in seconds

def is_cache_valid():
    if assets_cache["data"] and assets_cache["last_updated"]:
        return (time.time() - assets_cache["last_updated"]) < CACHE_TTL
    return False

# Connection management
connection_state = {
    "is_connected": False,
    "last_connected": 0,
    "retry_count": 0,
    "max_retries": 3,
    "cooldown_period": 60  # seconds
}

async def ensure_connection():
    """Ensures a valid connection with retry logic"""
    if connection_state["is_connected"] and (time.time() - connection_state["last_connected"]) < 300:
        return True

    try:
        check_connect, reason = await client.connect()
        if not check_connect:
            raise Exception(f"Connection failed: {reason}")
        connection_state["is_connected"] = True
        connection_state["last_connected"] = time.time()
        connection_state["retry_count"] = 0
        logger.info("Connection is Successful.")
        return True
    except Exception as e:
        connection_state["is_connected"] = False
        connection_state["retry_count"] += 1
        if connection_state["retry_count"] > connection_state["max_retries"]:
            logger.error(f"Max retries exceeded. Cooling down for {connection_state['cooldown_period']} seconds.")
            await asyncio.sleep(connection_state["cooldown_period"])
            connection_state["retry_count"] = 0
        logger.error(f"Connection attempt failed: {str(e)}")
        return False

@app.get("/")
async def index(request: Request):
    return {
        "index": f"{request.url}",
        "candles": f"{request.url}candles_new?asset=EURUSD&offset=3600&period=60",
    }

@app.get("/test_connection")
async def test_connection():
    try:
        retry_attempts = 0
        while retry_attempts < 3:
            if await ensure_connection():
                break
            retry_attempts += 1
            await asyncio.sleep(1)
        else:
            raise HTTPException(status_code=500, detail="Failed to establish stable connection")

        datetime_server, time_server = await client.get_server_time()
        result = {
            "connected": True,
            "datetime_server": datetime_server,
            "time_server": time_server
        }

        return result

    except Exception as e:
        logger.error(f"Error in test_connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/assets_open")
async def get_assets_open():
    try:
        with cache_lock:
            if is_cache_valid():
                logger.info("Using cache for assets_open.")
                return assets_cache["data"]

        retry_attempts = 0
        while retry_attempts < 3:
            if await ensure_connection():
                break
            retry_attempts += 1
            await asyncio.sleep(1)
        else:
            raise HTTPException(status_code=500, detail="Failed to establish stable connection")

        assets = []
        for i in client.get_all_asset_name():
            asset_name = i[1]
            asset_open = await client.check_asset_open(i[0])
            assets.append({
                "symbol_id": asset_open[0], 
                "pair": asset_open[1], 
                "is_open": asset_open[2]
            })

        with cache_lock:
            assets_cache["data"] = assets
            assets_cache["last_updated"] = time.time()

        return assets

    except WebSocketConnectionClosedException:
        connection_state["is_connected"] = False
        logger.error("WebSocket connection closed unexpectedly")
        raise HTTPException(status_code=500, detail="WebSocket connection closed unexpectedly")
    except Exception as e:
        logger.error(f"Error in assets_open: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/candles_new", response_model=List[Dict])
async def get_candles_progressive(
    request: Request, 
    days: int = 1, 
    asset: str = "BRLUSD_otc", 
    offset: int = 3600, 
    period: int = 60,
    timeout: float = 15  # Timeout in seconds
):
    try:
        start_time = time.time()

        retry_attempts = 0
        while retry_attempts < 3:
            if await ensure_connection():
                break
            retry_attempts += 1
            await asyncio.sleep(1)
        else:
            raise HTTPException(status_code=500, detail="Failed to establish stable connection after multiple attempts")

        logger.info("Connection is Successful.")

        symbol_id = constants.codes_asset.get(asset)
        if not symbol_id:
            raise HTTPException(status_code=400, detail=f"Invalid asset: {asset}")

        max_candles = (((days * 24) * (60 * 60)) // period)
        logger.info(f"Max candles to fetch: {max_candles}")

        end_from_time = int(time.time())
        logger.info("Starting candles...")

        candles = await client.get_candles(asset, end_from_time, offset, period)
        list_candles = candles[::-1]
        seen_times = set()

        # Initialize last_update_time with current time
        last_update_time = time.time()

        if list_candles:
            end_from_time = list_candles[-1]["time"]
            
            while len(list_candles) < max_candles:
                current_time = time.time()
                time_since_last_update = current_time - last_update_time
                logger.debug(f"Current time: {current_time}, Last update time: {last_update_time}, Time since last update: {time_since_last_update:.3f} seconds")
                
                if time_since_last_update > timeout:  # Timeout set to 0.1 seconds
                    logger.info("No new candles received within the timeout period. Stopping fetch.")
                    break

                if not await ensure_connection():
                    raise HTTPException(status_code=500, detail="Lost connection while fetching candles")
                    
                candles = await client.get_candles(asset, end_from_time, offset, period, progressive=True)
                
                # Log received candles for debugging
                logger.debug(f"Received candles: {candles}")
                
                if candles:
                    end_from_time = candles[0]["time"]
                    if end_from_time not in seen_times:
                        if not candles[0].get("open"):
                            candles = process_candles(candles, period)

                        candles = candles[::-1]
                        new_candle_added = False

                        for candle in candles:
                            # Validate candle data structure
                            if not all(k in candle for k in ("time", "open", "close", "high", "low", "ticks")):
                                logger.warning(f"Invalid candle data received: {candle}")
                                continue

                            timestamp = candle['time']
                            
                            if 'symbol_id' not in candle:
                                candle['symbol_id'] = symbol_id
                            
                            if 'asset' not in candle:
                                candle['asset'] = asset
                            
                            if 'last_tick' not in candle:
                                random_seconds = random.uniform(0, 59.999)
                                candle['last_tick'] = timestamp + random_seconds

                            if candle not in list_candles:
                                list_candles.append(candle)
                                new_candle_added = True
                                logger.debug(f"Added new candle: {candle}")

                            if len(list_candles) >= max_candles:
                                break

                        if new_candle_added:
                            last_update_time = time.time()  # Reset timeout since new data was added
                            logger.debug(f"New candle added. Updated last_update_time to {last_update_time}")

                        seen_times.add(end_from_time)

                        logger.info(f'Start: {candles[-1]["time"]} End: {candles[0]["time"]}')
                        epoch_candle = timestamp_to_datetime(end_from_time)
                        logger.info(f'Epoch Candle Time: {epoch_candle}')

                await asyncio.sleep(0.05)  # Small delay to prevent high CPU usage

        list_candles = list_candles[::-1]

        standardized_candles = []
        for candle in list_candles:
            standardized_candle = {
                'symbol_id': candle.get('symbol_id', symbol_id),
                'time': candle['time'],
                'open': candle['open'],
                'close': candle['close'],
                'high': candle['high'],
                'low': candle['low'],
                'ticks': candle['ticks'],
                'last_tick': candle.get('last_tick', candle['time'] + random.uniform(0, 59.999)),
                'asset': candle.get('asset', asset),
                'time_read': datetime.fromtimestamp(candle['time'], tz=timezone.utc).astimezone(timezone(timedelta(hours=6))).strftime('%Y-%m-%d %H:%M') + " (UTC: +06:00)"
            }
            standardized_candles.append(standardized_candle)

        total_candles = len(standardized_candles)
        total_time_spent = time.time() - start_time

        logger.info(f"\nCandles Total: {total_candles}")
        logger.info(f"Total time spent: {total_time_spent:.2f} seconds")

        if standardized_candles:
            first_candle = standardized_candles[-1]["time"]
            last_candle = standardized_candles[0]["time"]
            logger.info(
                f"Start Candle: {timestamp_to_datetime(first_candle)} \n"
                f"End Candle: {timestamp_to_datetime(last_candle)} "
            )

        return standardized_candles

    except WebSocketConnectionClosedException:
        connection_state["is_connected"] = False
        logger.error("WebSocket connection closed unexpectedly")
        raise HTTPException(status_code=500, detail="WebSocket connection closed unexpectedly")
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/candles_new_v2", response_model=List[Dict])
async def get_candles_progressive(request: Request, 
    max_candles: int = 1, 
    asset: str = "BRLUSD_otc", 
    offset: int = 3600, 
    period: int = 60,
    timeout: float = 0.1  # Timeout in seconds
):
    try:
        start_time = time.time()

        # Implement retry logic with ensure_connection
        retry_attempts = 0
        while retry_attempts < 3:
            if await ensure_connection():
                break
            retry_attempts += 1
            await asyncio.sleep(1)
        else:
            raise HTTPException(status_code=500, detail="Failed to establish stable connection after multiple attempts")

        logger.info("Connection is Successful.")

        # Get symbol_id from codes_asset dictionary
        symbol_id = constants.codes_asset.get(asset)
        if not symbol_id:
            raise HTTPException(status_code=400, detail=f"Invalid asset: {asset}")

        logger.info(f"Max candles to fetch: {max_candles}")

        end_from_time = int(time.time())
        logger.info("Starting candles...")

        # Initial candle fetch
        candles = await client.get_candles(asset, end_from_time, offset, period)
        list_candles = candles[::-1] if candles else []
        seen_times = set()

        # Initialize last_update_time with current time
        last_update_time = time.time()

        if list_candles:
            end_from_time = list_candles[-1]["time"]

            while len(list_candles) < max_candles:
                current_time = time.time()
                time_since_last_update = current_time - last_update_time
                logger.debug(f"Current time: {current_time}, Last update time: {last_update_time}, Time since last update: {time_since_last_update:.3f} seconds")

                if time_since_last_update > timeout:  # Timeout check
                    logger.info("No new candles received within the timeout period. Stopping fetch.")
                    break

                if not await ensure_connection():
                    raise HTTPException(status_code=500, detail="Lost connection while fetching candles")

                # Fetch progressive candles
                candles = await client.get_candles(asset, end_from_time, offset, period, progressive=True)

                # Log received candles for debugging
                logger.debug(f"Received candles: {candles}")

                if candles:
                    end_from_time = candles[0]["time"]
                    if end_from_time not in seen_times:
                        if not candles[0].get("open"):
                            candles = process_candles(candles, period)

                        candles = candles[::-1]
                        new_candle_added = False

                        for candle in candles:
                            # Validate candle data structure
                            if not all(k in candle for k in ("time", "open", "close", "high", "low", "ticks")):
                                logger.warning(f"Invalid candle data received: {candle}")
                                continue

                            timestamp = candle['time']

                            # Add missing symbol_id
                            if 'symbol_id' not in candle:
                                candle['symbol_id'] = symbol_id

                            # Add missing asset
                            if 'asset' not in candle:
                                candle['asset'] = asset

                            # Add missing last_tick
                            if 'last_tick' not in candle:
                                random_seconds = random.uniform(0, 59.999)
                                candle['last_tick'] = timestamp + random_seconds

                            if candle not in list_candles:
                                list_candles.append(candle)
                                new_candle_added = True
                                logger.debug(f"Added new candle: {candle}")

                            if len(list_candles) >= max_candles:
                                break

                        if new_candle_added:
                            last_update_time = time.time()  # Reset timeout since new data was added
                            logger.debug(f"New candle added. Updated last_update_time to {last_update_time}")

                        seen_times.add(end_from_time)

                        logger.info(f'Start: {candles[-1]["time"]} End: {candles[0]["time"]}')
                        epoch_candle = timestamp_to_datetime(end_from_time)
                        logger.info(f'Epoch Candle Time: {epoch_candle}')

                await asyncio.sleep(0.05)  # Small delay to prevent high CPU usage

        list_candles = list_candles[::-1]

        # Final pass to ensure all candles have the standard format
        standardized_candles = []
        for candle in list_candles:
            standardized_candle = {
                'symbol_id': candle.get('symbol_id', symbol_id),
                'time': candle['time'],
                'open': candle['open'],
                'close': candle['close'],
                'high': candle['high'],
                'low': candle['low'],
                'ticks': candle['ticks'],
                'last_tick': candle.get('last_tick', candle['time'] + random.uniform(0, 59.999)),
                'asset': candle.get('asset', asset),
                'time_read': datetime.fromtimestamp(candle['time'], tz=timezone.utc).astimezone(timezone(timedelta(hours=6))).strftime('%Y-%m-%d %H:%M') + " (UTC: +06:00)"
            }
            standardized_candles.append(standardized_candle)

        total_candles = len(standardized_candles)
        total_time_spent = time.time() - start_time

        logger.info(f"\nCandles Total: {total_candles}")
        logger.info(f"Total time spent: {total_time_spent:.2f} seconds")

        if standardized_candles:
            first_candle = standardized_candles[-1]["time"]
            last_candle = standardized_candles[0]["time"]
            logger.info(
                f"Start Candle: {timestamp_to_datetime(first_candle)} \n"
                f"End Candle: {timestamp_to_datetime(last_candle)} "
            )

        return standardized_candles

    except WebSocketConnectionClosedException:
        connection_state["is_connected"] = False
        logger.error("WebSocket connection closed unexpectedly")
        raise HTTPException(status_code=500, detail="WebSocket connection closed unexpectedly")
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
