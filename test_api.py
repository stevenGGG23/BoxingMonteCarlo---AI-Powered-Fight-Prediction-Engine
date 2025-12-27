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
        print(f"Fighter: {player['strPlayer']}")
        print(f"Record: {player['intWin']}-{player['intLoss']}-{player['intDraw']}")
else:
    print(f"❌ Error: {response.status_code}")