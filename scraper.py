import datetime
import fnmatch
import json
import os
import sys

from bs4 import BeautifulSoup
from jinja2 import Template
from postmarker.core import PostmarkClient
import requests


COMMONS = {
    'HEADCODES': [
        '3???',
        '7???',
        '8???',
        '9???',
        '0???',
        '?Q??',
        '?X??',
        '?Z??',
    ],
    'STATIONS': [
        'Carnforth Steamtown',
    ]
}


# http://www.railwaycodes.org.uk/crs/CRS0.shtm
LOCATIONS = {
    'COLTONJ': {  # Colton Jn
        'HEADCODES': COMMONS['HEADCODES'],
        'STATIONS': [
            'Doncaster West Yard',
            'Royal Mail',
            'Shields T.M.D.',
            'York Thrall Europa',
        ] + COMMONS['STATIONS']
    },
    'CRNFSTM': {  # Carnforth Steamtown
        'STATIONS': [
            'Starts here',
            'Terminates here',
        ] + COMMONS['STATIONS'],
    },
    'MALTBTH': {  # Barton Hill
        'HEADCODES': COMMONS['HEADCODES'],
        'STATIONS': COMMONS['STATIONS'],
        'TOCS': ['ZZ']
    }
}


def log(message):
    sys.stderr.write(message)


def is_interesting(train_params, determinants):
    for station in determinants.get('STATIONS', []):
        if station in train_params['origin'] or station in train_params['destination']:
            return True
    for toc in determinants.get('TOCS', []):
        if toc == train_params['toc']:
            return True
    for headcode in determinants.get('HEADCODES', []):
        if fnmatch.fnmatch(train_params['headcode'], headcode):
            return True


def main():
    config = json.load(open(sys.argv[1]))

    interesting = {}

    for location, determinants in LOCATIONS.items():
        interesting[location] = []

        url = 'http://www.realtimetrains.co.uk/search/advanced/{location}/' \
              '{today.year}/{today.month:02d}/{today.day:02d}/0000-2359?stp=WVS&show=all&order=wtt'.format(
            location=location, today=datetime.date.today(),
        )
        response = requests.get(url)

        soup = BeautifulSoup(response.text, 'html.parser')
        trains = soup.find_all('tr')

        log('Found {count} trains for {location}\n'.format(count=len(trains), location=location))

        for train in trains:
            columns = train.find_all('td')
            if not columns:
                continue

            column_values = [c.string for c in columns]
            train_params = {
                'arrival': column_values[1],
                'origin': column_values[3] or '',
                'headcode': column_values[5],
                'toc': column_values[6],
                'destination': column_values[7] or '',
                'departure': column_values[8],
            }

            if is_interesting(train_params, determinants):
                interesting[location].append(train_params)

    template_location = os.path.join(os.path.dirname(__file__), 'template.html')
    template_code = open(template_location).read()
    html = Template(template_code).render(locations=interesting)
    postmark = PostmarkClient(server_token=config['postmark_api_token'])
    postmark.emails.send(
        From=config['email_from'],
        To=config['email_to'],
        Subject=config['email_subject'],
        HtmlBody=html
    )


if __name__ == '__main__':
    main()
