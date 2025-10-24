# ...existing code...
from supabase import create_client, Client
import os
from datetime import datetime
import core
import facebook
from datetime import datetime, timedelta, timezone
from collections import defaultdict

supabase: Client = create_client(core.supabase_url, core.supabase_service_role_key)

async def upsert_spend_per_country_supabase(data: list[dict]):
    """Updates spend in Supabase table based on country."""
    if not data:
        print("No data provided to update.")
        return
    
    table_name = "facebook_ads_spend_per_country"
    
    # Filter and aggregate in one pass
    spend_by_country_date = defaultdict(lambda: defaultdict(float))
    
    for d in data:
        if len(d['country']) == 2:
            spend_by_country_date[d['country']][d['date']] += d['spend']
    
    # Convert to list for upsert
    result = [
        {'country_code': country, 'date': date, 'spend_brl': total_spend}
        for country, dates in spend_by_country_date.items()
        for date, total_spend in dates.items()
    ]
    
    if not result:
        print("No valid records to insert.")
        return
    
    print(f"Prepared {len(result)} aggregated records for upsert into {table_name}.")
    try:
        response = supabase.table(table_name).upsert(
            result,
            on_conflict='country_code,date'  # Specify the unique constraint columns
        ).execute()
        print(f"Successfully upserted {len(result)} records into {table_name}.")
    except Exception as e:
        print(f"Error upserting data into {table_name}: {str(e)}")

async def update_spend_commission_in_supabase(data: list[dict]):
    """Updates spend and commission in Supabase table based on country."""
    if not data:
        print("No data provided to update.")
        return
    
    table_name = "facebook_ads_spend_commission"
    
    b1_float = 5.45
    # Prepare data
    updates_dict = {}
    for row in data:
        country_name = row.get('COUNTRY')
        commission = float(row.get('COMMISSION') or 0)
        spend_brl = float(row.get('SPEND BRL') or 0)
        roi = row['COMMISSION'] / row['SPEND BRL'] * b1_float * 100
        if row['SPEND BRL'] / b1_float < 100:
            status = 'ADD'
        else:
            status = 'ADD' if roi > 150 else 'REMOVE'
        updates_dict[country_name] = {
            'country': country_name,
            'spend_brl': spend_brl,
            'commission': commission,
            'status': status,
            'created_at': datetime.now().isoformat()
        }
    
    try:
        # Get all existing records
        existing = supabase.table(table_name).select('id, country').execute()
        existing_codes = {row['country']: row['id'] for row in existing.data}
        
        # Separate into updates and inserts
        batch_insert = []
        batch_update = []
        
        for country_code, record in updates_dict.items():
            if country_code in existing_codes:
                batch_update.append({
                    'id': existing_codes[country_code],
                    **record
                })
            else:
                batch_insert.append(record)
        
        # Execute batches
        if batch_insert:
            supabase.table(table_name).insert(batch_insert).execute()
            print(f"Inserted {len(batch_insert)} new records")
        
        if batch_update:
            supabase.table(table_name).upsert(batch_update).execute()
            print(f"Updated {len(batch_update)} existing records")
            
    except Exception as e:
        print(f"Error batch processing {table_name}: {str(e)}")
