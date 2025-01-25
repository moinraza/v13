import os
import requests
import json
from datetime import datetime, timedelta, timezone
import zipfile
# import winsound
from colorama import init, Fore

# Initialize colorama
init(autoreset=True)

codes_asset = {
    # "AUDCAD_otc": 67,
    # "AUDCHF_otc": 68,
    # "AUDJPY_otc": 69,
    # "AUDNZD_otc": 70,
    # "AUDUSD_otc": 71,
    # "AXJAUD": 315,
    # "AXP_otc": 291,
    # "BA_otc": 292,
    # "BRLUSD_otc": 332,
    # "BTCUSD_otc": 352,
    # "CADCHF_otc": 72,
    # "CADJPY_otc": 73,
    # "CHFJPY_otc": 74,
    # "CHIA50": 328,
    # "DJIUSD": 317,
    # "DOGUSD_otc": 353,
    # "EURAUD_otc": 75,
    # "EURCAD_otc": 76,
    # "EURCHF_otc": 77,
    # "EURGBP_otc": 78,
    # "EURJPY_otc": 79,
    # "EURNZD_otc": 80,
    # "EURSGD_otc": 303,
    # "EURUSD_otc": 66,
    # "F40EUR": 318,
    # "FB_otc": 187,
    # "FTSGBP": 319,
    # "GBPAUD_otc": 81,
    # "GBPCAD_otc": 82,
    # "GBPCHF_otc": 83,
    # "GBPJPY_otc": 84,
    # "GBPNZD_otc": 85,
    # "GBPUSD_otc": 86,
    # "HSIHKD": 320,
    # "IBXEUR": 321,
    # "INTC_otc": 190,
    # "IT4EUR": 326,
    # "JNJ_otc": 296,
    # "JPXJPY": 327,
    # "MCD_otc": 175,
    # "MSFT_otc": 176,
    # "NDXUSD": 322,
    # "NZDCAD_otc": 87,
    # "NZDCHF_otc": 88,
    # "NZDJPY_otc": 89,
    # "PEPUSD_otc": 354,
    # "PFE_otc": 297,
    # "STXEUR": 325,
    # "UKBrent_otc": 164,
    # "USCrude_otc": 165,
    "USDARS_otc": 345,
    "USDBDT_otc": 334,
    "USDCAD_otc": 91,                 
    "USDCHF_otc": 92,
    "USDCOP_otc": 347,
    # "USDDZD_otc": 349,
    # "USDEGP_otc": 338,
    # "USDIDR_otc": 342,
    # "USDINR_otc": 202,
    # "USDJPY_otc": 93,
    # "USDMXN_otc": 343,
    # "USDNGN_otc": 340,
    # "USDPHP_otc": 351,
    # "USDPKR_otc": 336,
    # "USDTRY_otc": 201,
    # "USDZAR_otc": 157,
    # "XAGUSD_otc": 167,
    # "XAUUSD_otc": 169
}

assets_url = "http://127.0.0.1:8000/assets_open"

def debug_message(message):
    print(Fore.MAGENTA + f"[DEBUG] {message}")

# Get user input for number of days and size
while True:
    try:
        num_days = int(input("Enter the number of days (minimum 1): "))
        if num_days < 1:
            raise ValueError("Number of days must be at least 1.")
        break
    except ValueError as e:
        print(Fore.RED + str(e))

while True:
    try:
        num_days1 = int(input("Enter the number of days (minimum 1): "))
        if num_days1 < 1:
            raise ValueError("Number of days must be at least 1.")
        break
    except ValueError as e:
        print(Fore.RED + str(e))

debug_message(f"Number of days: {num_days}, {num_days1}")

print(Fore.CYAN + f"Requesting open assets from: {assets_url}")
debug_message("Sending request to fetch open assets")

try:
    assets_response = requests.get(assets_url, timeout=1800)
    assets_response.raise_for_status()
    assets_data = assets_response.json()
    print(Fore.GREEN + "Successfully fetched open assets data.")
except requests.exceptions.RequestException as e:
    print(Fore.RED + json.dumps({"error": "Failed to fetch asset data from the API"}))
    exit()

debug_message("Successfully fetched open assets data")

utc_plus_6 = timezone(timedelta(hours=6))
current_date_utc6 = datetime.now(utc_plus_6).date()
debug_message(f"Current date in UTC+6: {current_date_utc6}")

past_days = [current_date_utc6 - timedelta(days=i) for i in range(1, num_days + 1)]
dates_str = [date.strftime('%Y-%m-%d') for date in past_days]
dates_folder_str = [date.strftime('%d-%m-%Y') for date in past_days]
debug_message(f"Past days: {dates_str}")

main_folder_name = f"Data ({dates_folder_str[0]})"
main_folder_path = os.path.join(os.getcwd(), main_folder_name)
os.makedirs(main_folder_path, exist_ok=True)
debug_message(f"Main folder path: {main_folder_path}")

for asset in assets_data:
    if asset['is_open']:
        symbol_id = asset['symbol_id']
        pair = next((key for key, value in codes_asset.items() if value == symbol_id), None)
        
        if pair:
            api_url = f"http://127.0.0.1:8000/candles_new?asset={pair}&days={num_days1}"
            print(Fore.CYAN + f"Requesting candle data for: {pair} from: {api_url}")

            try:
                response = requests.get(api_url, timeout=1800)
                response.raise_for_status()
                data = response.json()
                print(Fore.GREEN + f"Successfully fetched candle data for {pair}.")
            except requests.exceptions.RequestException as e:
                print(Fore.RED + json.dumps({"error": f"Failed to fetch data for {pair} from the API"}))
                continue

            folder_path = os.path.join(main_folder_path, pair)
            os.makedirs(folder_path, exist_ok=True)
            debug_message(f"Created folder path: {folder_path}")

            entries = [entry for entry in data if isinstance(entry, dict) and entry.get('asset') == pair]
            if not entries:
                print(Fore.YELLOW + f"No entries found for {pair}, skipping save.")
                continue

            for prev_date_str in dates_str:
                filtered_entries = [entry for entry in entries if entry['time_read'].startswith(prev_date_str)]

                if not filtered_entries:
                    print(Fore.YELLOW + f"No entries found for {pair} on {prev_date_str}, skipping save.")
                    continue

                print(Fore.CYAN + f"Processing {len(filtered_entries)} entries for {pair} on date {prev_date_str}.")

                file_path = os.path.join(folder_path, f"{prev_date_str}.json")
                debug_message(f"File path for saving data: {file_path}")

                existing_data = []
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        try:
                            existing_data = json.load(f)
                            print(Fore.CYAN + f"Loaded existing data for {pair} from {file_path}.")
                        except json.JSONDecodeError:
                            existing_data = []
                            print(Fore.YELLOW + f"No existing data found for {pair} in {file_path}, starting fresh.")

                existing_data.extend(filtered_entries)
                unique_data = {entry['time']: entry for entry in existing_data}
                updated_data = list(unique_data.values())

                try:
                    with open(file_path, 'w') as f:
                        json.dump(updated_data, f, indent=4)
                    print(Fore.GREEN + f"Data saved for asset pair: {pair} for previous date {prev_date_str}")
                except Exception as e:
                    print(Fore.RED + f"Failed to save data for {pair} on {prev_date_str}: {e}")

for date_str in dates_str:
    total_symbol_count = 0
    for pair, symbol_id in codes_asset.items():
        folder_path = os.path.join(main_folder_path, pair)
        file_path = os.path.join(folder_path, f"{date_str}.json")

        if os.path.exists(file_path):
            print(Fore.CYAN + f"Checking file: {file_path}")
            with open(file_path, 'r') as f:
                try:
                    data = json.load(f)
                    symbol_count = len(data)
                    total_symbol_count += symbol_count
                    
                    if symbol_count < 1440:
                        debug_message(f"Symbol count for {pair} on {date_str} is less than 47: {symbol_count}")
                        for _ in range(2):
                            pass
                except json.JSONDecodeError:
                    print(Fore.RED + f"Error reading JSON file: {file_path}")
    
    print(Fore.GREEN + f"Total symbol count for {date_str}: {total_symbol_count}")

zip_file_name = f"Data ({dates_folder_str[0]}).zip"
zip_file_path = os.path.join(os.getcwd(), zip_file_name)

print(Fore.CYAN + f"Creating zip file: {zip_file_name}")
debug_message(f"Creating zip file: {zip_file_name}")

with zipfile.ZipFile(zip_file_path, 'w') as zipf:
    for pair_folder in os.listdir(main_folder_path):
        folder_path = os.path.join(main_folder_path, pair_folder)
        if os.path.isdir(folder_path):
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    print(Fore.CYAN + f"Adding file to zip: {file_path}")
                    debug_message(f"Adding file to zip: {file_path}")
                    zipf.write(file_path, os.path.relpath(file_path, main_folder_path))

print(Fore.GREEN + f"Zipped folder saved as: {zip_file_name}")
debug_message(f"Zipped folder saved as: {zip_file_name}")