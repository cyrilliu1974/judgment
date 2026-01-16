
import datetime
from judicial_api import JudicialYuanAPI

def test_date_handling():
    # Initialize with dummy credentials
    api = JudicialYuanAPI("dummy_user", "dummy_pwd")
    
    # Create a datetime.date object
    date_obj = datetime.date(2023, 10, 25)
    
    print(f"Testing with date object: {date_obj} (type: {type(date_obj)})")
    
    try:
        # This is expected to fail with AttributeError: 'datetime.date' object has no attribute 'replace'
        # The verify logic in judicial_api.py calls .replace() effectively assuming it's a string
        # We'll pass other dummy arguments
        api.get_judgment_content("TPS", "112", "test", "1", date_obj, "1")
        print("Scenerio executed (Verify checking might fail later due to network, but we care about the crash before that)")
    except AttributeError as e:
        print(f"Caught expected error: {e}")
    except Exception as e:
        print(f"Caught unexpected error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_date_handling()
