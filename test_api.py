"""
API Connection Test Script
Tests TheSportsDB API connection and displays fighter data
"""

import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_api_connection():
    """Test TheSportsDB API connection"""
    
    # Get API key from environment
    api_key = os.getenv('THESPORTSDB_API_KEY')
    
    if not api_key or api_key == 'your_api_key_here':
        print("❌ Error: No valid API key found!")
        print("💡 Set THESPORTSDB_API_KEY in your .env file")
        return False
    
    print("🔍 Testing TheSportsDB API connection...")
    print(f"API Key: {api_key[:10]}..." if len(api_key) > 10 else "API Key: [hidden]")
    
    # Test premium v2 endpoint
    url = "https://www.thesportsdb.com/api/v2/json/all/searchplayers.php"
    headers = {
        "X-API-KEY": f"{api_key}",
        "Content-Type": "application/json"
    }
    params = {"p": "Canelo Alvarez"}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ API Connection Successful!")
            
            if data.get('player'):
                player = data['player'][0]
                print(f"\n📊 Sample Fighter Data:")
                print(f"  Name: {player.get('strPlayer')}")
                print(f"  Sport: {player.get('strSport')}")
                print(f"  Nationality: {player.get('strNationality')}")
                print(f"  Wins: {player.get('intWin')}")
                print(f"  Losses: {player.get('intLoss')}")
                print(f"  Draws: {player.get('intDraw')}")
                print(f"  Height: {player.get('strHeight')}")
                print(f"  Weight: {player.get('strWeight')}")
                return True
            else:
                print("\n⚠️ No fighter data returned")
                return False
                
        elif response.status_code == 403:
            print("\n❌ Error: 403 Forbidden - Invalid API Key")
            print("💡 Check your API key in .env file")
            return False
        else:
            print(f"\n❌ Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Connection Error: {e}")
        return False

if __name__ == "__main__":
    print("="*50)
    print("TheSportsDB API Connection Test")
    print("="*50)
    test_api_connection()
    print("="*50)