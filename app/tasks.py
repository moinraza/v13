from app.celery import celery_app
from fastapi import FastAPI, Request, HTTPException
import time, asyncio
import logging
from datetime import datetime, timezone, timedelta
from app.quotexapi.config import email, password
from app.quotexapi.stable_api import Quotex
from app.quotexapi.utils.processor import process_candles
from threading import Lock
from typing import List, Dict
from app.quotexapi.expiration import timestamp_to_datetime


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
        check_connect, reason = await asyncio.run(client.connect())
        print(check_connect)
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
            asyncio.sleep(connection_state["cooldown_period"])
            connection_state["retry_count"] = 0
        logger.error(f"Connection attempt failed: {str(e)}")
        return False


@celery_app.task
async def test_connect():
    retry_attempts = 0
    while retry_attempts < 3:
        if await ensure_connection():
            break
        retry_attempts += 1
        asyncio.sleep(1)
    else:
        raise HTTPException(status_code=500, detail="Failed to establish stable connection")

    datetime_server, time_server =  await asyncio.run(client.get_server_time())
    result = {
        "connected": True,
        "datetime_server": datetime_server,
        "time_server": time_server
    }

    return result
  