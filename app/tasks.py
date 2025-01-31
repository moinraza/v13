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
import requests, json, itertools, os




@celery_app.task
def candle_connect(data):
    max_candles = data.get('max_candles')
    asset = data.get('asset')
    all_responses = [] 
    for _ in range(0, max_candles):
        headers = {'Content-Type': 'application/json',}
        response = requests.get(f'http://31.57.228.200/candles_new_mins?asset={asset}', headers=headers)
        if response.status_code == 200:
            res = response.json()
            all_responses.append(res)  # Append response to list
        else:
            print(f"Failed to fetch data for asset {asset}")
        time.sleep(2)
    # Store the collected JSON data in a file
    all_responses = list(itertools.chain(*all_responses))
    total_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # Format time for filename
    file_path = f"app/asset/{asset}_{total_time}.txt"
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    # Write data to file as plain text (without json.dump)
    with open(file_path, "w") as file:
        file.write(str(all_responses))# Pretty format the JSON data
    print("JSON data has been saved to under asses folder")

    