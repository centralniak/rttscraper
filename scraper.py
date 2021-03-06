import argparse
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
        '7???',
        '8???',
        '0???',
        '?Q??',
        '?X??',
        '?Z??',
    ],
    'STATIONS': [
        'Carnforth Steamtown',
        'Network Rail',
        'Royal Mail',
        'Tesco',
        'York N.R.M.',
    ],
    'TOCS': [
        'CS',
        'GC',
        'HT',
        'LN',
        'LR',
        'NY',
        'SP',
        'WR',
        'ZZ',
    ]
}


# http://www.railwaycodes.org.uk/crs/CRS0.shtm
LOCATIONS = {
    'COLTONJ': {  # Colton Jn
        'HEADCODES': COMMONS['HEADCODES'],
        'STATIONS': [
            'Daventry Drs',
            'Doncaster West Yard',
            'Jarrow Shell',
            'Leicester',
            'Micklefield',
            'Northallerton',
            'Parcels',
            'Shields T.M.D.',
            'Sinfin',
        ] + COMMONS['STATIONS'],
        'TOCS': COMMONS['TOCS'][:-1],
    },
    'GLH': COMMONS,  # Glasshoughton (for Prince of Wales SB in Pontefract)
    'GSCGNWJ': COMMONS,  # Gascoine Wood Jn
    'HAMBLNJ': COMMONS,  # Hambleton North Jn
    'HAMBLWJ': COMMONS,  # Hambleton West Jn
    'MALTBTH': COMMONS,  # Barton Hill
    'MILFDY': COMMONS,  # Milford Jn
    'LDS': {  # Leeds
        'HEADCODES': COMMONS['HEADCODES'],
        'STATIONS': COMMONS['STATIONS'],
        'TOCS': COMMONS['TOCS'][:-1],
    },
    'MIK': COMMONS,  # Micklefield
    'SHD': COMMONS,  # Shildon (for Shildon NRM),
    'YORKNRM': {  # York NRM
        'STATIONS': [
            'Starts here',
            'Terminates here',
        ] + COMMONS['STATIONS'],
    },
}


def log(message):
    sys.stderr.write(message)


def is_interesting(train_params, determinants):
    if train_params['actual'] == 'Cancel':
        return False
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
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-c, --config', dest='config', help='path of the config file')
    arg_parser.add_argument('-d, --days', default=0, type=int, dest='days',
                            help='days from today to generate report for, e.g. +1 is tomorrow')
    arg_parser.add_argument('locations', default=[], type=str, nargs='*',
                            help='list of locations to generate a report for')
    args = arg_parser.parse_args()

    config = json.load(open(args.config))
    timedelta = datetime.timedelta(days=args.days)
    date = datetime.date.today() + timedelta

    interesting = {}

    for location in args.locations or LOCATIONS:
        determinants = LOCATIONS.get(location, COMMONS)

        interesting[location] = []

        url = 'http://www.realtimetrains.co.uk/search/advanced/{location}/' \
              '{today.year}/{today.month:02d}/{today.day:02d}/0000-2359?stp=WVS&show=all&order=wtt'.format(
            location=location, today=date,
        )
        response = requests.get(url)

        soup = BeautifulSoup(response.text, 'html.parser')
        trains = soup.find_all('tr')

        log('Found {count} trains for {location}\n'.format(count=len(trains), location=location))

        for train in trains:
            columns = train.find_all('td')
            if not columns:
                continue

            try:
                column_values = [c.get_text() for c in columns]
                train_params = {
                    'arrival': column_values[1],
                    'origin': column_values[3] or '',
                    'headcode': column_values[5],
                    'toc': column_values[6],
                    'destination': column_values[7] or '',
                    'departure': column_values[8],
                    'actual': column_values[9],
                    'link': train.find('a').get('href'),
                }
            except Exception as exc:
                log('Unable to parse {} - {}'.format(columns, exc))

            if is_interesting(train_params, determinants):
                url = 'http://www.realtimetrains.co.uk/{link}'.format(link=train_params['link'])
                response = requests.get(url)
                soup = BeautifulSoup(response.text, 'html.parser')
                service_details = [
                    s.get_text() for s in
                    soup.select('.detailed-schedule-info')[0].find_all('ul')[1].find_all('li')
                ]
                train_params['service_details'] = service_details
                interesting[location].append(train_params)

    template_location = os.path.join(os.path.dirname(__file__), 'template.html')
    template_code = open(template_location).read()
    html = Template(template_code).render(locations=interesting)
    postmark = PostmarkClient(server_token=config['postmark_api_token'])
    email = postmark.emails.Email(
        From=config['email_from'],
        To=config['email_to'],
        Subject='rttscraper digest for {today.year}/{today.month:02d}/{today.day:02d} {locations}'.format(
            today=date, locations=', '.join(interesting.keys())),
        HtmlBody=html
    )
    email.attach_binary(content=bytes(html, 'utf-8'), filename='rttscraper.html')
    email.send()


if __name__ == '__main__':
    main()
