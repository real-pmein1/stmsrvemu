import os
import xml.etree.ElementTree as ET
import datetime
from collections import defaultdict

STATS_DIR = os.path.join('stats')
os.makedirs(STATS_DIR, exist_ok=True)

# gameplay stats {date: {game: set(user_ids)}}
_gameplay_users = defaultdict(lambda: defaultdict(set))
# content server load {date: {server: {'starts': int, 'finishes': int}}}
_content_load = defaultdict(lambda: defaultdict(lambda: {'starts': 0, 'finishes': 0}))

SURVEY_FILE = os.path.join(STATS_DIR, 'survey_totals.xml')
_survey_totals = defaultdict(lambda: defaultdict(int))


def _today():
    return datetime.date.today().isoformat()


def record_gameplay(game, user_id, day=None):
    day = day or _today()
    _gameplay_users[day][game].add(user_id)
    _dump_gameplay(day)


def _dump_gameplay(day):
    root = ET.Element('games')
    for game, users in _gameplay_users[day].items():
        g = ET.SubElement(root, 'game', name=game)
        g.text = str(len(users))
    path = os.path.join(STATS_DIR, f'gameplay_{day}.xml')
    ET.ElementTree(root).write(path, encoding='utf-8')


def record_content_load(server, event, day=None):
    day = day or _today()
    data = _content_load[day][server]
    if event == 'start':
        data['starts'] += 1
    elif event == 'end':
        data['finishes'] += 1
    _dump_content(day)


def _dump_content(day):
    root = ET.Element('content_servers')
    try:
        from servers.managers import contentlistmanager
        all_servers = [entry[0] for entry in contentlistmanager.manager.contentserver_list]
    except Exception:
        all_servers = []

    for server in all_servers:
        _content_load[day].setdefault(server, {'starts': 0, 'finishes': 0})

    for server, data in _content_load[day].items():
        cs = ET.SubElement(root, 'server', name=server)
        cs.set('starts', str(data['starts']))
        cs.set('finishes', str(data['finishes']))

    path = os.path.join(STATS_DIR, f'content_{day}.xml')
    ET.ElementTree(root).write(path, encoding='utf-8')


def load_survey_totals():
    if os.path.exists(SURVEY_FILE):
        tree = ET.parse(SURVEY_FILE)
        for field in tree.getroot().findall('field'):
            name = field.get('name')
            vals = {}
            for val in field.findall('value'):
                vals[val.get('option')] = int(val.text)
            _survey_totals[name] = vals


load_survey_totals()


def record_survey(results):
    for key, value in results.items():
        if key == 'DecryptionOK':
            continue
        val = str(value)
        _survey_totals[key][val] = _survey_totals[key].get(val, 0) + 1
    _dump_survey_totals()


def _dump_survey_totals():
    root = ET.Element('survey_totals')
    for key, values in _survey_totals.items():
        field = ET.SubElement(root, 'field', name=key)
        for val, count in values.items():
            elem = ET.SubElement(field, 'value', option=val)
            elem.text = str(count)
    ET.ElementTree(root).write(SURVEY_FILE, encoding='utf-8')
