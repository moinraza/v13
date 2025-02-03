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
from async_timeout import timeout
from app.tasks import candle_connect
from fastapi import BackgroundTasks

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

async def fetch_candles(asset, end_time, offset, period, retries=3):
    for _ in range(retries):
        try:
            return await client.get_candles(asset, end_time, offset, period, progressive=True)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout. Retrying {_ + 1}/{retries}...")
            await asyncio.sleep(2)  # Wait before retrying
    raise HTTPException(status_code=504, detail="Failed to fetch candles after multiple retries")

@app.get("/candles_new_mins", response_model=List[Dict])
async def get_candles_progressive(asset: str = "BRLUSD_otc", offset: int = 3600, period: int = 60):
    try:
        start_time = time.time()
        end_from_time = int(time.time())
        symbol_id = constants.codes_asset.get(asset)
        logger.info("Starting candles...")
        seen_times = set()
        candles = await fetch_candles(asset, end_from_time, offset, period)
        if not candles:
            return []
        list_candles = candles[::-1]  # Reverse for chronological order
        end_from_time = list_candles[-1]["time"]  # Update last timestamp
        # Process and enrich candles efficiently
        standardized_candles = [{
                "symbol_id": candle.get("symbol_id", symbol_id),
                "time": candle["time"],
                "open": candle["open"],
                "close": candle["close"],
                "high": candle["high"],
                "low": candle["low"],
                "ticks": candle["ticks"],
                "last_tick": candle.get("last_tick", candle["time"] + random.uniform(0, 59.999)),
                "asset": candle.get("asset", asset),
                "time_read": datetime.fromtimestamp(candle["time"], tz=timezone.utc)
                            .astimezone(timezone(timedelta(hours=6)))
                            .strftime('%Y-%m-%d %H:%M') + " (UTC: +06:00)"
            }
            for candle in list_candles
            if candle["time"] not in seen_times and all(
                k in candle for k in ("time", "open", "close", "high", "low", "ticks")
            )
        ]
        seen_times.update(candle["time"] for candle in standardized_candles)
        # Logging results
        total_time_spent = time.time() - start_time
        logger.info(f"Total candles fetched: {len(standardized_candles)} in {total_time_spent:.2f} seconds.")
        if standardized_candles:
            logger.info(f"Start Candle: {timestamp_to_datetime(standardized_candles[-1]['time'])}, "f"End Candle: {timestamp_to_datetime(standardized_candles[0]['time'])}")
        return standardized_candles
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/candles_new", status_code=200)
async def get_candles_progressive(days: int = 1, offset: int = 3600, asset: str = "BRLUSD_otc", period: int = 60):
    try:
        # Retry connection logic
        for _ in range(3):
            if await ensure_connection():
                break
            await asyncio.sleep(1)
        else:
            raise HTTPException(status_code=500, detail="Failed to establish stable connection after multiple attempts")
        logger.info("Connection is Successful.")
        symbol_id = constants.codes_asset.get(asset)
        if not symbol_id:
            raise HTTPException(status_code=400, detail=f"Invalid asset: {asset}")
        max_candles = ((days * 24) * 60 * 60 // period)
        logger.info(f"Max candles to fetch: {max_candles}")
        end_from_time = int(time.time())
        candles = await client.get_candles(asset, end_from_time, offset, period)
        list_candles = candles[::-1]
        data = {'max_candles':max_candles, 'asset':asset, 'list_candles':len(list_candles)}
        candle_connect.delay(data)
        return {"message": "Uploading your data! Wait few minutes"}
    except WebSocketConnectionClosedException:
        connection_state["is_connected"] = False
        logger.error("WebSocket connection closed unexpectedly")
        raise HTTPException(status_code=500, detail="WebSocket connection closed unexpectedly")
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/candles_new_v2", response_model=List[Dict])
async def get_candles_progressive(
    max_candles: int = 1, 
    asset: str = "BRLUSD_otc", 
    offset: int = 3600, 
    period: int = 60, 
    timeout_duration: float = 15  # Increased timeout for reliability
):
    try:
        start_time = time.time()
        # Ensure connection with retry logic
        for _ in range(3):
            if await ensure_connection():
                break
            await asyncio.sleep(1)
        else:
            raise HTTPException(status_code=500, detail="Failed to establish a stable connection.")
        logger.info("Connection established successfully.")
        # Get symbol_id
        symbol_id = constants.codes_asset.get(asset)
        if not symbol_id:
            raise HTTPException(status_code=400, detail=f"Invalid asset: {asset}")
        logger.info(f"Fetching up to {max_candles} candles.")
        end_from_time = int(time.time())
        seen_times = set()
        standardized_candles = []
        # Fetch candles with timeout
        try:
            async with timeout(timeout_duration):  
                candles = await client.get_candles(asset, end_from_time, offset, period)
        except asyncio.TimeoutError:
            logger.error("Timeout while fetching candles.")
            raise HTTPException(status_code=504, detail="Request timed out while fetching candles.")
        if not candles:
            return []
        list_candles = candles[::-1]  # Reverse for chronological order
        end_from_time = list_candles[-1]["time"]  # Update last timestamp
        # Process and enrich candles efficiently
        standardized_candles = [
            {
                "symbol_id": candle.get("symbol_id", symbol_id),
                "time": candle["time"],
                "open": candle["open"],
                "close": candle["close"],
                "high": candle["high"],
                "low": candle["low"],
                "ticks": candle["ticks"],
                "last_tick": candle.get("last_tick", candle["time"] + random.uniform(0, 59.999)),
                "asset": candle.get("asset", asset),
                "time_read": datetime.fromtimestamp(candle["time"], tz=timezone.utc)
                            .astimezone(timezone(timedelta(hours=6)))
                            .strftime('%Y-%m-%d %H:%M') + " (UTC: +06:00)"
            }
            for candle in list_candles
            if candle["time"] not in seen_times and all(
                k in candle for k in ("time", "open", "close", "high", "low", "ticks")
            )
        ]
        seen_times.update(candle["time"] for candle in standardized_candles)
        # Logging results
        total_time_spent = time.time() - start_time
        logger.info(f"Total candles fetched: {len(standardized_candles)} in {total_time_spent:.2f} seconds.")
        if standardized_candles:
            logger.info(f"Start Candle: {timestamp_to_datetime(standardized_candles[-1]['time'])}, "f"End Candle: {timestamp_to_datetime(standardized_candles[0]['time'])}")
        return standardized_candles

    except WebSocketConnectionClosedException:
        logger.error("WebSocket connection closed unexpectedly.")
        raise HTTPException(status_code=500, detail="WebSocket connection closed unexpectedly.")
    
    except asyncio.TimeoutError:
        logger.error("Overall timeout exceeded.")
        raise HTTPException(status_code=504, detail="Request timed out.")

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))