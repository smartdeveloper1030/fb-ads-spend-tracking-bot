from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.user import User
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import core
import pycountry
import requests
import json
import asyncio
import time
from googlesheet import update_google_sheet3
import sqlite3
from facebook_business.adobjects.adsinsights import AdsInsights
import pycountry
import fb_ads_supabase


keyword1 = "MAGDY"
keyword2 = "DEYOO"

class FbAdsPerformance:
    def __init__(self):
        FacebookAdsApi.init(core.fb_app_id, core.fb_app_secret, core.fb_access_token)

    def fetch_campaign_performance(self, since_date, until_date):
        ad_account = AdAccount(f'act_{self.ad_account_id}')
        params = {
            'time_range': {'since': since_date, 'until': until_date},
            'fields': [
                AdsInsights.Field.campaign_name,
                AdsInsights.Field.impressions,
                AdsInsights.Field.clicks,
                AdsInsights.Field.spend,
                AdsInsights.Field.ctr,
                AdsInsights.Field.cpc,
                AdsInsights.Field.cpm,
                AdsInsights.Field.conversions,
                AdsInsights.Field.cost_per_conversion,
            ],
            'level': 'campaign',
        }
        insights = ad_account.get_insights(params=params)
        return insights