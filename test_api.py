import requests

# Test the free API with key 123
url = "https://www.thesportsdb.com/api/v1/json/123/searchplayers.php"
params = {"p": "Canelo Alvarez"}

response = requests.get(url, params=params)

if response.status_code == 200:
    data = response.json()
    print("✅ API Working!")
    if data.get('player'):
        player = data['player'][0]
        name = player.get('strPlayer', 'Unknown')
        wins = player.get('intWin', 'N/A')
        losses = player.get('intLoss', 'N/A')
        draws = player.get('intDraw', 'N/A')
        print(f"Fighter: {name}")
        print(f"Record: {wins}-{losses}-{draws}")
        # Print available keys for debugging if numeric fields missing
        if wins == 'N/A' or losses == 'N/A':
            print("⚠ Some record fields missing from API response. Available keys:")
            for k in sorted(player.keys()):
                print(f"  - {k}: {player[k]}")
else:
    print(f"❌ Error: {response.status_code}")