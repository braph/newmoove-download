import os
import json
from string import Template
from utils import remember_cwd

def read_template(file_name):
    with open(os.path.join(__path__[0], 'templates', file_name), 'r') as fh:
        return fh.read()

css = read_template('style.css')

def generate_course_html(course_directory, course_info):
    template = Template(read_template('course.html'))
    video_template = Template('''
    <div class="course_video">
        <video width="100%" controls="controls" onclick="this.paused ? this.play() : this.pause();" preload="metadata">
            <source src="$file" type="video/mp4">
            Your browser does not support the video tag.
        </video>

        <p>$description</p>
    </div>''')

    with remember_cwd(course_directory):
        videos = ''
        index = 0
        for description in course_info['episode_descriptions']:
            index += 1
            video_file = '%0.2d.%s.mp4' % (index, course_info['url_title'])
            videos += video_template.substitute(file=video_file, description=description)

        generated = template.substitute(**course_info, videos=videos, style=css)
        with open('index.html', 'w') as fh:
            fh.write(generated)


def generate_course_listing_html(workouts_directory):
    template = Template(read_template('course_listing.html'))
    course_template = Template('''
    <div class="course_listing_table">
        <table>
            <tr>
                <td>Titel: </td>
                <td><a href="$url_title/index.html">$title</a></td>
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
            <!--
            <tr>
                <td>Level: </td>
                <td>$level</td>
            </tr>
            -->
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
    </div>''')

    with remember_cwd(workouts_directory):
        course_infos = []

        for directory in filter(os.path.isdir, os.listdir('.')):
            with open(os.path.join(directory, 'info.json'), 'r') as fh:
                course_infos.append(json.load(fh))

            generate_course_html(directory, course_infos[-1])


        body = ''

        for level in ('Einsteiger', 'Fortgeschrittene', 'Experten'):
            body += '<h2>%s</h2>' % level

            for course_info in filter(lambda x: x['level'] == level, course_infos):
                body += course_template.substitute(**course_info)

        generated = template.substitute(title=workouts_directory, body=body, style=css)
        with open('index.html', 'w') as fh:
            fh.write(generated)


def generate_html(root_directory):
    template = Template(read_template('main.html'))

    with remember_cwd(root_directory):
        with open('info.json', 'r') as fh:
            workout_titles = json.load(fh)

        links = ''

        for directory in filter(os.path.isdir, os.listdir('.')):
            with remember_cwd(directory):
                num_courses = len(list(filter(os.path.isdir, os.listdir('.'))))
            links += '<li><a href="%s/index.html">%s (%d Kurse)</a></li>' % (
                directory, workout_titles[directory], num_courses)
            generate_course_listing_html(directory)

        generated = template.substitute(links=links, style=css)
        with open('index.html', 'w') as fh:
            fh.write(generated)

