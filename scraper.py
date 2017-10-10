import argparse
import datetime
import fnmatch
import json
import os
import sys

from bs4 import BeautifulSoup
from jinja2 import Template
import requests


COMMONS = {
    'HEADCODES': [
        '7???',
        '8???',
        '9???',
        '0???',
        '?Q??',
        '?X??',
        '?Z??',

        '6N11',
        '4E23',
        '4L84',
        '4S89',
        '6J37',
    ],
    'STATIONS': [
        'Carnforth Steamtown',
        'Craigentinny',
        'Network Rail',
        'London Victoria',
        'L.I.P.',
        'Litchurch Lane',
        'Royal Mail',
        'Tesco',
        'York N.R.M.',
    ],
    'TIMETABLES': [
        'STP',
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
    'ARCQGF': COMMONS,  # Arcow Quarry
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
        'TIMETABLES': COMMONS['TIMETABLES'],
        'TOCS': COMMONS['TOCS'][:-1],
    },
    # 'GLH': COMMONS,  # Glasshoughton (for Prince of Wales SB in Pontefract)
    # 'GSCGNWJ': COMMONS,  # Gascoine Wood Jn
    # 'HAMBLNJ': COMMONS,  # Hambleton North Jn
    # 'HAMBLWJ': COMMONS,  # Hambleton West Jn
    'HGT': COMMONS,  # Harrogate
    # 'MILFDY': {  # Milford Jn
    #     'HEADCODES': COMMONS['HEADCODES'],
    #     'STATIONS': COMMONS['STATIONS'],
    #     'TIMETABLES': COMMONS['TIMETABLES'],
    #     'TOCS': COMMONS['TOCS'][:-1],
    # },
    'LDS': {  # Leeds
        'HEADCODES': COMMONS['HEADCODES'],
        'STATIONS': COMMONS['STATIONS'],
        'TIMETABLES': COMMONS['TIMETABLES'],
        'TOCS': COMMONS['TOCS'][:-1],
    },
    'MIK': COMMONS,  # Micklefield (for Garforth)
    'MLT': COMMONS,  # Malton
    'NTR': COMMONS,  # Northallerton (for Wensleydale Railway)
    'RIBLHVQ': COMMONS,  # Ribblehead Virtual Quarry
    'SHD': COMMONS,  # Shildon (for Shildon NRM),
    'SKPTSNJ': COMMONS,  # Skipton Down Shipley Slow (for Rylston Quarry)
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
    if train_params['headcode'] == 'BUS':
        return False
    if train_params['timetable'] in determinants.get('TIMETABLES', []):
        return True
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

    assert config.get('email_from')
    assert config.get('email_to')
    assert config.get('mailgun_domain')
    assert config.get('mailgun_apikey')

    interesting = {}

    for location in args.locations or LOCATIONS:
        determinants = LOCATIONS.get(location, COMMONS)

        interesting[location] = []

        url = 'http://www.realtimetrains.co.uk/search/advanced/{location}/' \
              '{today.year}/{today.month:02d}/{today.day:02d}/0000-2359?stp=WVS&show=all&order=wtt'.format(
            location=location, today=date,
        )
        response = requests.get(url, timeout=5)

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
                    'timetable': column_values[0],
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
                response = requests.get(url, timeout=5)
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
    requests.post(
        'https://api.mailgun.net/v3/{}/messages'.format(config['mailgun_domain']),
        auth=('api', config['mailgun_apikey']),
        data={
            'from': config['email_from'],
            'to': config['email_to'],
            'subject': 'rttscraper digest for {today.year}/{today.month:02d}/{today.day:02d} {locations}'.format(
                today=date, locations=', '.join(sorted(interesting.keys()))),
            'html': html,
        },
        files={
            'attachment': ('rttscraper.html', html, 'text/html'),
        }
    )


if __name__ == '__main__':
    main()
