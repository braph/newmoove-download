#!/usr/bin/python3

''' Command line access to newmoove.com '''

import sys, os, re, traceback
import json
import logging
import argparse
import requests
import subprocess
import contextlib

from string import Template
from lxml import html
from urllib.parse import urlparse, parse_qs, urlunparse

# === command line parser ===
argp = argparse.ArgumentParser(description=__doc__)

def add_auth_options(parser):
    parser.add_argument('--email',
        help='Set email for authentication',
        required=True)
    parser.add_argument('--password',
        help='Set password for authentication',
        required=True)

subparsers = argp.add_subparsers(dest='cmd')

list_workouts = subparsers.add_parser('list_workouts',
    help='List all available workout categories')
add_auth_options(list_workouts)

download_course = subparsers.add_parser('download_course',
    help='Download single course')
download_course.add_argument('course', nargs='+',
    help='URL of course to download')
add_auth_options(download_course)

download_workout = subparsers.add_parser('download_workout',
    help='Download all courses of workout category')
download_workout.add_argument('workout',
    help='Comma separated list of workouts to download. Set to \'all\' to download all workout categories')
download_workout.add_argument('--root',
    help='Set root directory', default='.')
add_auth_options(download_workout)

generate_html = subparsers.add_parser('generate_html',
    help='Generate html for downloaded workouts')
generate_html.add_argument('--root',
    help='Set root directory', default='.')

group = argp.add_argument_group('advanced')
group.add_argument('--useragent',
    help='Set useragent for http requests',
    default='Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.118 Safari/537.36')
# ===========================


logging.basicConfig(format=sys.argv[0] + ' %(asctime)s %(levelname).1s %(funcName)-15s %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class NewMoove:
    main_url = 'https://www.newmoove.com'
    login_url = 'https://www.newmoove.com/cas/login?service=https://www.newmoove.com:443/system/login/dispatcher.jsp%3FrequestedResource=/cms/courseSearch.html'
    workout_url = 'https://www.newmoove.com/workouts'

    def __init__(self):
        # reqests.Session handles the cookies for us
        self.session = requests.Session()
        self.session.headers = {}


    def useragent(self, useragent):
        self.session.headers['User-Agent'] = useragent


    def newmoove_url(self, url):
        if not url.startswith(self.main_url):
            return self.main_url + '/' + url.lstrip('/')
        else:
            return url


    # perform login
    def login(self, email, password):
        r = self.session.get(self.login_url)
        tree = html.fromstring(r.text)
        data = {}

        # copy values from input fields into data dictionary
        for input_tag in tree.xpath('//input'):
            data[input_tag.name] = input_tag.value

        # overwrite username and password with authentication data
        data['username'] = email
        data['password'] = password

        self.session.post(self.login_url, data=data)


    # list available workout categories (yoga, pilates, dance...)
    def list_workout_categories(self):
        r = self.session.get(self.workout_url)
        tree = html.fromstring(r.text)

        workouts = []

        for href in tree.xpath('//a[contains(@class, "mr-category-item")]/@href'):
            workouts.append(href.replace('workouts', '').replace('/', ''))

        return workouts


    # list available courses for a workout category
    def list_workout_courses(self, url):
        r = self.session.get(url)
        tree = html.fromstring(r.text)

        result = []

        for level in ('beginner', 'advanced', 'expert'):
            section = tree.xpath('//div[@class = "%s"]' % level)[0]
            courses = section.find_class('ok-content-col-8-4')

            for course in courses:
                #url = course.find_class('ok-training-pathasid')[0].text
                #url = url.replace('/sites/default', '')
                url = course.xpath('.//h3/a/@href')[0]
                title = course.xpath('.//h3')[0].text_content()
                desc = course.find_class('ok-generic-box-middle-text')[0].text_content()

                result.append({
                    'url': self.newmoove_url(url),
                    'title': title.strip(),
                    'description': desc.strip(),
                    'level': level
                })

        return result


    def get_course_infos(self, url):
        logger.debug('getting infos for %s', url)

        r = self.session.get(url)
        tree = html.fromstring(r.text)
        infos = {}

        # title
        try:
            infos['title'] = tree.xpath('//h2/text()')[0]
        except Exception as e:
            infos['title'] = 'N/A'
            logger.warning('Could not extract title: %s', e)

        # cleared title
        infos['title_clear'] = os.path.basename(url)

        # description
        try:
            infos['description'] = tree.xpath('//p[@itemprop="description"]')[0].text.strip()
        except Exception as e:
            infos['description'] = 'unknown'
            logger.warning('Could not extract description: %s', e)

        # misc infos
        try:
            infos['duration'] = tree.xpath('//img[@src="/res/img/icons/Icon_Uhr.png"]/@title')[0].strip()
        except Exception as e:
            infos['duration'] = '0'
            logger.warning('Could not extract duration: %s', e)

        try:
            infos['calories'] = tree.xpath('//img[@src="/res/img/icons/Icon_Apfel.png"]/@title')[0].strip()
        except Exception as e:
            infos['calories'] = '0'
            logger.warning('Could not extract calories: %s', e)

        try:
            infos['level'] = tree.xpath('//img[@src="/res/img/icons/Icon_Schwierigkeit.png"]/@title')[0].strip()
        except Exception as e:
            infos['level'] = 'unknown'
            logger.warning('Could not extract level: %s', e)

        try:
            infos['body_area'] = tree.xpath('//img[@src="/res/img/icons/Icon_Manderl.png"]/@title')[0].strip()
        except Exception as e:
            infos['body_area'] = 'unknown'
            logger.warning('Could not extract body_area: %s', e)

        try:
            infos['material'] = tree.xpath('//img[@src="/res/img/icons/Icon_Material.png"]/@title')[0].strip()
        except Exception as e:
            infos['material'] = 'unknown'
            logger.warning('Could not extract material: %s', e)

        try:
            infos['bonus_points'] = tree.xpath('//img[@src="/res/img/icons/icon_plus_gruen.png"]/@title')[0].strip()
        except Exception as e:
            infos['bonus_points'] = '0'
            logger.warning('Could not extract bonus_points: %s', e)


        # descriptions for each episodes
        infos['episode_descriptions'] = tree.xpath('//p[contains(@class, "as-kursdetail-folgentext")]/text()')

        # search for javascript parts including the "episodeArray=[...]" part
        js = tree.xpath('//script[@type="text/javascript" and contains(text(), "episodeArray")]/text()')[0]
        js = js.replace('\n', ' ') # remove newlines for regex match
        episodeArray = re.findall('episodeArray[^\]]+\]', js)[0]
        episodeArray = re.sub('episodeArray\s=', '', episodeArray)
        episodeArray = episodeArray.replace('[', '').replace(']', '').replace(' ', '').replace("'", '')
        episodeArray = episodeArray.strip(',').split(',')

        # watch links
        link = tree.find_class('as-kursstarten')[0].get('onclick')
        link = re.sub('^openInLightBox\(\'', '', link)
        link = re.sub('\'.*', '', link)

        parsed_link = urlparse(link)
        parsed_link_lst = list(parsed_link)
        query_parameters = parse_qs(parsed_link.query)
        # flatten query_parameters
        query_parameters = { key: value[0] for key, value in query_parameters.items() }

        infos['episode_urls'] = []
        for episode_url in episodeArray:
            query_parameters['episodeLink'] = episode_url

            joined_query = '&'.join([ key + '=' + value for key, value in query_parameters.items() ])
            parsed_link_lst[4] = joined_query

            infos['episode_urls'].append(self.newmoove_url(urlunparse(parsed_link_lst)))

        return infos


    def get_video_download_url(self, url):
        logger.debug('Retrieving download url for %s', url)

        r = self.session.get(url)
        tree = html.fromstring(r.text)
        data = {}

        for input_tag in tree.xpath('//input'):
            data[input_tag.name] = input_tag.value

        # extracting 'background' parameter
        try:
            js = tree.xpath('//script[@type="text/javascript" and contains(text(), "/cms/img")]/text()')[0]
            data['background'] = re.findall("/cms[^']+", js)[0]
        except:
            logger.debug('Could not get background parameter')

        r = self.session.post(self.newmoove_url('/cms/LightBox.html'), data)
        #with open('/tmp/test.html', 'w') as f:
        #    f.write(r.text)
        tree = html.fromstring(r.text)
        return tree.xpath('//source/@src')[0]


@contextlib.contextmanager
def remember_cwd(new_dir=None):
    curdir = os.getcwd()
    try:
        if new_dir:
            os.chdir(new_dir)
        yield
    finally:
        os.chdir(curdir)


# downloads current course into current directory
def download_course(newmoove_obj, url):
    infos = newmoove_obj.get_course_infos(url)
    os.makedirs(infos['title_clear'], exist_ok=True)
    with remember_cwd(infos['title_clear']):
        # write down info file
        with open('info.json', 'w') as info_file_fh: 
            json.dump(infos, info_file_fh, indent=3)

        index = 0
        for url in infos['episode_urls']:
            try:
                index += 1
                video_file = '%0.2d.%s.mp4' % (index, infos['title_clear'])

                if os.path.exists(video_file):
                    logger.info('Skipping download of %s', video_file)
                else:
                    video_url = newmoove_obj.get_video_download_url(url)
                    video_file_part = '%s.part' % video_file
                    if not subprocess.call(['wget', video_url, '-c', '-O', video_file_part]):
                        os.rename(video_file_part, video_file)
            except Exception as e:
                logger.warning('Failed to download episode "%s": %s', url, traceback.format_exc())


def download_workout(newmoove_obj, root_directory, workout_categories):
    root_directory = os.path.abspath(root_directory)
    
    try:
        os.makedirs(root_directory, exist_ok=True)
    except Exception as e:
        raise Exception("Failed to create root directory '%s': %s" % (root_directory, str(e)))
    
    for workout_category in workout_categories:
        with remember_cwd():
            os.chdir(root_directory)
            os.makedirs(workout_category, exist_ok=True)
            os.chdir(workout_category)

            workout_url = '%s/%s/' % (newmoove_obj.workout_url, workout_category)

            for course_info in newmoove_obj.list_workout_courses(workout_url):
                download_course(newmoove_obj, course_info['url'])


def generate_course_html(course_directory, course_info):
    course_template = Template('''
    <html>
        <head>
            <title>Newmoove - $title</title>
        </head>

        <body>
            <a href="..">Zurück</a>

            <h1>$title</h1>
            <p>$description</p>
            <table>
                <tr>
                    <td>Dauer: </td>
                    <td>$duration</td>
                </tr>
                <tr>
                    <td>Kalorien: </td>
                    <td>$calories</td>
                </tr>
                <tr>
                    <td>Level: </td>
                    <td>$level</td>
                </tr>
                <tr>
                    <td>Körperbereich: </td>
                    <td>$body_area</td>
                </tr>
                <tr>
                    <td>Material: </td>
                    <td>$material</td>
                </tr>
                <tr>
                    <td>Bonuspunkte: </td>
                    <td>$bonus_points</td>
                </tr>
            </table>

            $videos
        </body>
    </html>
    ''')

    videos_template = Template('''
    <video width="320" height="240" controls>
        <source src="$file" type="video/mp4">
        Your browser does not support the video tag.
    </video>

    <p> $description </p>
    ''')

    with remember_cwd(course_directory):
        videos = ''
        index = 0
        for description in course_info['episode_descriptions']:
            index += 1
            video_file = '%0.2d.%s.mp4' % (index, course_info['title_clear'])
            videos += videos_template.substitute(file=video_file, description=description)

        generated = course_template.substitute(**course_info, videos=videos)
        with open('index.html', 'w') as index_html_fh:
            index_html_fh.write(generated)


def generate_workouts_html(workouts_directory):
    template = Template('''
    <html>
        <head>
            <title> Newmoove - $title </title>
        </head>

        <body>
            <a href="..">Zurück</a>
            $body
        </body>
    <html>
    ''')

    course_template = Template('''
    <table>
        <tr>
            <td>Titel: </td>
            <td><a href="$title_clear">$title</a></td>
        </tr>
        <tr>
            <td>Beschreibung: </td>
            <td>$description</td>
        </tr>
        <tr>
            <td>Dauer: </td>
            <td>$duration</td>
        </tr>
        <tr>
            <td>Kalorien: </td>
            <td>$calories</td>
        </tr>
        <tr>
            <td>Level: </td>
            <td>$level</td>
        </tr>
        <tr>
            <td>Körperbereich: </td>
            <td>$body_area</td>
        </tr>
        <tr>
            <td>Material: </td>
            <td>$material</td>
        </tr>
        <!--
        <tr>
            <td>Bonuspunkte: </td>
            <td>$bonus_points</td>
        </tr>
        -->
    </table>

    <br />
    ''')

    with remember_cwd(workouts_directory):
        course_infos = []

        for d in filter(os.path.isdir, os.listdir('.')):
            with open(os.path.join(d, 'info.json'), 'r') as course_info_fh:
                course_infos.append( json.load(course_info_fh) )

            generate_course_html(d, course_infos[-1])


        body = ''

        for level in ('Einsteiger', 'Fortgeschrittene', 'Experten'):
            body += '<h1>%s</h1>' % level

            for course_info in filter(lambda x: x['level'] == level, course_infos):
                body += course_template.substitute(**course_info)

        generated = template.substitute(title=workouts_directory, body=body)
        with open('index.html', 'w') as index_html_fh:
            index_html_fh.write(generated)


def generate_html(root_directory):
    template = Template('''
    <html>
        <head>
            <title>$title</title>
        </head>
        <body>
            <h1>$title</h1>
            <ul>$links</ul>
        </body>
    </html>''')

    os.chdir(root_directory)

    links = ''

    for d in filter(os.path.isdir, os.listdir('.')):
        with remember_cwd(d):
            num_courses = len(list(filter(os.path.isdir, os.listdir('.'))))
        links += '<li><a href="%s">%s</a> (%d Kurse)</li>' % (d, d, num_courses)
        generate_workouts_html(d)

    generated = template.substitute(title='Newmoove Workouts', links=links)
    with open('index.html', 'w') as index_html_fh:
        index_html_fh.write(generated)


# === program entry ===
try:
    options = argp.parse_args()

    if options.cmd is None:
        raise Exception('please provide a subcommand (see --help)')

    elif options.cmd == 'generate_html':
        generate_html(options.root)

    else:
        nm = NewMoove()
        nm.useragent(options.useragent)
        nm.login(options.email, options.password)

        if options.cmd == 'list_workouts':
            for workout in nm.list_workout_categories():
                print(workout)
        elif options.cmd == 'download_workout':
            available_workouts = nm.list_workout_categories()

            if options.workout == 'all':
                workouts = available_workouts
            else:
                workouts = options.workout.split(',')

                for workout in workouts:
                    if not workout in available_workouts:
                        raise Exception("Unknown workout category: '%s'" % workout)

            download_workout(nm, options.root, workouts)
        elif options.cmd == 'download_course':
            for course in options.course:
                download_course(nm, course)

except Exception as e:
    print(e)
    sys.exit(1)

