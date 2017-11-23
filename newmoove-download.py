#!/usr/bin/env python3

''' Command line access to newmoove.com '''

import sys, os, re, traceback
import json
import logging
import argparse
import subprocess

import newmoove
import html_generation
from utils import remember_cwd

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


def download_course(newmoove_obj, url):
    '''
    Downloads the videos of a course. A directory named by the url title is created.
    Inside this directory an info.json file and the video files (named by the url title,
    prefixed with numbers) are stored.

    Example directory listing after function call:

     sh-$ ls -R1
         ./yogalates-core-training:
             01.yogalates-core-training.mp4
             02.yogalates-core-training.mp4
             info.json
    '''
    infos = newmoove_obj.get_course_infos(url)
    os.makedirs(infos['url_title'], exist_ok=True)
    with remember_cwd(infos['url_title']):
        with open('info.json', 'w') as fh:
            json.dump(infos, fh, indent=3)

        index = 0
        for url in infos['episode_urls']:
            try:
                index += 1
                video_file = '%0.2d.%s.mp4' % (index, infos['url_title'])

                if os.path.exists(video_file):
                    logger.info('Skipping download of %s', video_file)
                else:
                    video_url = newmoove_obj.get_video_download_url(url)
                    video_file_part = '%s.part' % video_file
                    if not subprocess.call(['wget', video_url, '-c', '-O', video_file_part]):
                        os.rename(video_file_part, video_file)
            except Exception as e:
                logger.warning('Failed to download episode "%s": %s', url, traceback.format_exc())


def download_workout(newmoove_obj, workout_category):
    '''
    Downloads all courses of a workout.

    A directory named after `workout_category` will be created.
    Inside this directory the courses of the workout are stored.

    Example directory listing after function call:

    sh-$ ls -1 yoga
        anti-stress-yoga
        balance-yoga
        cooldown-yoga
        dynamic-yoga
        ...
    '''
    os.makedirs(workout_category, exist_ok=True)
    with remember_cwd(workout_category):
        workout_url = '%s/%s/' % (newmoove_obj.workout_url, workout_category)

        for course_info in newmoove_obj.list_workout_courses(workout_url):
            download_course(newmoove_obj, course_info['url'])


def download_workouts_multi(newmoove_obj, root_directory, workout_categories):
    root_directory = os.path.abspath(root_directory)
    
    try:
        os.makedirs(root_directory, exist_ok=True)
    except Exception as e:
        raise Exception("Failed to create root directory '%s': %s" % (root_directory, str(e)))
    
    with remember_cwd(root_directory):
        infos = {}
        for i in nm.list_workout_categories():
            infos[i['url_title']] = i['title']

        with open('info.json', 'w') as fh:
            json.dump(infos, fh, indent=3)

        for workout_category in workout_categories:
            download_workout(newmoove_obj, workout_category)


# === program entry ===
options = argp.parse_args()

if options.cmd is None:
    print('please provide a subcommand (see --help)')
    sys.exit(1)

elif options.cmd == 'generate_html':
    html_generation.generate_html(options.root)

else:
    nm = newmoove.NewMoove()
    nm.useragent(options.useragent)
    nm.login(options.email, options.password)

    if options.cmd == 'list_workouts':
        for workout in nm.list_workout_categories():
            print(workout['url_title'], '~', workout['title'])
    elif options.cmd == 'download_workout':
        workout_categories = nm.list_workout_categories()
        available_workouts = list(map(lambda x: x['url_title'], workout_categories))

        if options.workout == 'all':
            workouts = available_workouts
        else:
            workouts = options.workout.split(',')

            for workout in workouts:
                if not workout in available_workouts:
                    raise Exception("Unknown workout category: '%s'" % workout)

        download_workouts_multi(nm, options.root, workouts)
    elif options.cmd == 'download_course':
        for course in options.course:
            download_course(nm, course)


