import time
import logging
from threading import Event
import os
import json
import re

import alert
import core
import asyncio

from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher

import pocketpartners
import facebook
import fb_ads_supabase

from googlesheet import update_google_sheet


__appname__ = "FBPO Listener"
os.system("title [%s]" % __appname__)

core.chat_ids = core.load_chatids()

logger: logging.Logger = core.logger
alert.logger = logger

import sys
print("sys.platform: ", sys.platform)
if sys.platform == 'win32':
    # Configure StreamHandler to use utf-8 encoding
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.handlers = [console_handler] 


# Telegram Bot Initialization
bot = Bot(token=core.bot_token)
dp = Dispatcher()

def combine_spend_commission(po_commission: list, fb_spend: list) -> list:
    print(len(po_commission), len(fb_spend))
    po_lookup = {item['country_code']: item for item in po_commission}
    extended_fb_spend = []
    for fb_item in fb_spend:
        country_code = fb_item['country_code']
        extended_item = fb_item.copy()
        if country_code in po_lookup:
            po_item = po_lookup[country_code]
            extended_item['sum_commission'] = po_item['sum_commission']
        else:
            extended_item['sum_commission'] = 0
        extended_fb_spend.append(extended_item)

    combined = []

    for item in extended_fb_spend:
        spend = float(item['spend'])
        commission_value = float(item.get('sum_commission', 0))
        if spend == 0:
            print(f"Spend is 0 for {item['country']}")
            continue
        combined.append({
            'COUNTRY': item['country'],
            'SPEND BRL': float(f"{spend:.2f}"),
            'SPEND USD': None,
            'COMMISSION': float(f"{commission_value:.2f}"),
            'ROI$': None,
            'ROI%': None,
            'ROIX': None,
            'ADD/REMOVE': None
        })
    return combined

def create_telegram_message(remove_country: dict):
    file_path = 'remove_country.txt'
    message_file = 'remove_country_message.txt'
    # If file does not exist, save current remove_country and return
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(remove_country, f, ensure_ascii=False, indent=2)
        print('remove_country.txt did not exist. Saved current data and exiting.')

    # If file exists, load previous data
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            old_country = json.load(f)
        except Exception as e:
            print(f'Error loading remove_country.txt: {e}')
            old_country = {}

    old_country_set = set(row['COUNTRY'] for row in old_country)
    remove_country_set = set(row['COUNTRY'] for row in remove_country)

    message = []
    # Find added countries (present in remove_country but not in old_country)
    added_countries_names = remove_country_set - old_country_set
    added_countries = [row for row in remove_country if row['COUNTRY'] in added_countries_names]
    if added_countries:
        message.append("❌ REMOVED FROM CAMPAIGN\n")
        print('Added countries (full items):', added_countries)
        for country in added_countries:
            message.append(f"🏴 Country: {country['COUNTRY']}\n")
            message.append(f"💸 SPEND BRL: {country['SPEND BRL']}\n")
            message.append(f"💰 SPEND USD: {country['SPEND USD']}\n")
            message.append(f"💳 COMMISSION: {country['COMMISSION']}\n")
            message.append(f"💲 ROI$: {country['ROI$']}\n")
            message.append(f"🍟 ROI%: {country['ROI%']}\n")
            message.append(f"🥠 ROIX: {country['ROIX']}\n\n")
    else:
        print('No countries added.')

    # Find removed countries (present in old_country but not in remove_country)
    removed_countries_names = old_country_set - remove_country_set
    removed_countries = [row for row in old_country if row['COUNTRY'] in removed_countries_names]
    if removed_countries:
        message.append("✅ ADDED TO CAMPAIGN\n")
        print('Removed countries (full items):', removed_countries)
        for country in removed_countries:
            message.append(f"🏴 Country: {country['COUNTRY']}\n")
            message.append(f"💸 SPEND BRL: {country['SPEND BRL']}\n")
            message.append(f"💰 SPEND USD: {country['SPEND USD']}\n")
            message.append(f"💳 COMMISSION: {country['COMMISSION']}\n")
            message.append(f"💲 ROI$: {country['ROI$']}\n")
            message.append(f"🍟 ROI%: {country['ROI%']}\n")
            message.append(f"🥠 ROIX: {country['ROIX']}\n\n")
    else:
        print('No countries removed.')

    # Save the message to a file
    with open(message_file, 'w', encoding='utf-8') as f:
        f.writelines(message)

    # Overwrite file with current data
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(remove_country, f, ensure_ascii=False, indent=2)
    
    # Set return value based on conditions
    return 

async def main(isStarted = False):
    try:
        login_result = False
        while not login_result:
            login_result = await pocketpartners.perform_login()
            if not login_result:
                logger.warning("Login failed, retrying in 15 seconds...")
                await asyncio.sleep(15)

        max_retries = 10
        retry_count = 0
        commission_data = None
        fb_spend_data = None
        combine_data = None

        while commission_data is None and retry_count < max_retries:
            commission_data = await pocketpartners.get_pocketoption_data()
            if commission_data is None:
                retry_count += 1
                logger.warning(f"Attempt {retry_count}/{max_retries}: Failed to get pocketOption data, retrying...")
                await asyncio.sleep(20)  # Wait 20 seconds before retrying
        
        retry_count = 0
        while fb_spend_data is None and retry_count < max_retries:
            fb_spend_data = await facebook.fb_optimize()
            if fb_spend_data is None:
                retry_count += 1
                logger.warning(f"Attempt {retry_count}/{max_retries}: Failed to get country data, retrying...")
                await asyncio.sleep(20)  # Wait 20 seconds before retrying
        
        if commission_data is None or fb_spend_data is None:
            print("Commission or Country fatch data is failed")
            return
        
        combine_data = combine_spend_commission(commission_data, fb_spend_data)
        
        if combine_data is None:
            print("Combine data is failed")
            return
        
        await fb_ads_supabase.update_spend_commission_in_supabase(combine_data)

        countires_info = update_google_sheet(combine_data)
        included_countries = countires_info['ADD']
        excluded_countries = countires_info['REMOVE']

        create_telegram_message(excluded_countries)

        if isStarted == False:
            # await facebook.update_account_targeting_with_excluded_countries(excluded_countries)
            await facebook.update_account_targeting_with_included_countries(included_countries)
    except Exception as e:
        logger.exception(f"Error in main function: {e}")
        return

async def scheduler():
    await main(isStarted=True)
    # alert.send_country_message()
    while True:
        now = datetime.now(timezone(timedelta(hours=-3)))

        if now.hour == 19 and now.minute == 0:  
            state = True
            if now.weekday() in (0, 3):
                state = False

            await main(isStarted=state)
            alert.send_country_message()
            await asyncio.sleep(60)
        else:
            await asyncio.sleep(1)

if __name__ == '__main__':
    try:
        logger.info("Starting application")
        asyncio.run(scheduler())
    except Exception as e:
        logger.exception(f"Main loop error: {e}")
        time.sleep(60)
