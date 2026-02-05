import os
from dotenv import load_dotenv
from supabase import create_client, Client

def get_client() -> Client:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in .env")
    return create_client(url, key)
#testing to seeif connection worked 
def main():
    supabase = get_client()

    response = supabase.table("geo_events_geoevent").select("*").limit(5).execute()

    # response.data is a list of dict rows
    print("Rows:")
    for row in response.data:
        print(row)

if __name__ == "__main__":
    main()