import datetime

from bs4 import BeautifulSoup
import requests


# http://www.railwaycodes.org.uk/crs/CRS0.shtm
LOCATIONS = [
    'COLTONJ',
]

INTERESTING_STATIONS = [
    'Doncaster West Yard',
    'Holbeck Loco Sidings',
    'Royal Mail',
    'Shields T.M.D.',
    'York Thrall Europa',
]


def log(message):
    print(message)


def is_interesting(train_params):
    for station in INTERESTING_STATIONS:
        if station in train_params['origin'] or station in train_params['destination']:
            return True


def main():
    interesting = {}

    for location in LOCATIONS:
        interesting[location] = []

        url = 'http://www.realtimetrains.co.uk/search/advanced/{location}/' \
              '{today.year}/{today.month:02d}/{today.day:02d}/0000-2359?stp=WVS&show=all&order=wtt'.format(
            location=location, today=datetime.date.today(),
        )
        response = requests.get(url)

        soup = BeautifulSoup(response.text, 'html.parser')
        trains = soup.find_all('tr')

        log('Found {count} trains for {location}'.format(count=len(trains), location=location))

        for train in trains:
            columns = train.find_all('td')
            if not columns:
                continue

            column_values = [c.string for c in columns]
            train_params = {
                'arrival': column_values[1],
                'origin': column_values[3],
                'headcode': column_values[5],
                'toc': column_values[6],
                'destination': column_values[7],
                'departure': column_values[8],
            }

            if is_interesting(train_params):
                interesting[location].append(train_params)

    import pprint
    pprint.pprint(interesting)


if __name__ == '__main__':
    main()
