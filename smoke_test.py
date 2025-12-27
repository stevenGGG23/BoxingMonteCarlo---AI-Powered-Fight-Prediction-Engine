from main import BoxingAPI

def run():
    api = BoxingAPI(api_key=None)
    names = [
        'Shakur Stevenson',
        'Gervonta Davis',
        'Unknown Fighter XYZ'
    ]

    for n in names:
        print('\n===== Checking:', n)
        stats = api.get_fighter_stats(n)
        print('Stats:', stats)
        print('Search debug:', api.last_search_debug.get(n))

if __name__ == '__main__':
    run()
