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
    list_candles = data.get('list_candles')
    total_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # Format time for filename
    file_path = f"app/asset/{asset}_{total_time}.txt"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    i= 0
    while list_candles < max_candles:
        i = i+1
        list_candles = list_candles+1
        print(i, list_candles)
        headers = {'Content-Type': 'application/json',}
        response = requests.get(f'http://web:8000/candles_new_mins?asset={asset}', headers=headers)
        if response.status_code == 200:
            res = response.json()
            # Append new data to file instead of overwriting
            with open(file_path, "a") as file:  
                file.write(str(res) + "\n")  # Append response as a new line
            print(f"Appended data for {asset} to file.")
        else:
            print(f"Failed to fetch data for asset {asset}")
        time.sleep(1)  # Pause before next request
    print("JSON data has been saved to under asses folder")

    