import datetime

from bs4 import BeautifulSoup
import requests


LOCATIONS = [
    'COLTONJ',
]


def log(message):
    print(message)


def main():
    for location in LOCATIONS:
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
            arrival = column_values[1]
            origin = column_values[3]
            headcode = column_values[5]
            toc = column_values[6]
            destination = column_values[7]
            departure = column_values[8]


            print('arr', arrival)
            print('ori', origin)
            print('headcode', headcode)
            print('toc', toc)
            print('dest', destination)
            print('dep', departure)


            raise NotImplementedError


if __name__ == '__main__':
    main()
