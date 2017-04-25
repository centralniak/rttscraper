import datetime

import requests


LOCATIONS = [
    'COLTONJ',
]


def main():
    for location in LOCATIONS:
        url = 'http://www.realtimetrains.co.uk/search/advanced/{location}/' \
              '{today.year}/{today.month:02d}/{today.day:02d}/0000-2359?stp=WVS&show=all&order=wtt'.format(
            location=location, today=datetime.date.today(),
        )
        response = requests.get(url)
        print(response)


if __name__ == '__main__':
    main()
