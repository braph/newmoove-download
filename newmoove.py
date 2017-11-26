import re, os
import requests
import logging

from lxml import html
from urllib.parse import urlparse, parse_qs, urlunparse

logger = logging.getLogger()

class NewMoove:
    main_url = 'https://www.newmoove.com'
    login_url = 'https://www.newmoove.com/cas/login?service=https://www.newmoove.com:443/system/login/dispatcher.jsp%3FrequestedResource=/cms/courseSearch.html'
    workout_url = 'https://www.newmoove.com/workouts'

    def __init__(self):
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

        for a_tag in tree.xpath('//a[contains(@class, "mr-category-item")]'):
            url_title = a_tag.get('href').replace('workouts', '').replace('/', '')
            title = a_tag.xpath('./img/@alt')[0]
            workouts.append({'url_title': url_title, 'title': title})

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
            infos['title'] = 'unknown'
            logger.warning('Could not extract title: %s', e)

        # cleared title
        infos['url_title'] = os.path.basename(url)

        # description
        try:
            infos['description'] = tree.xpath('//p[@itemprop="description"]')[0].text.strip()
        except Exception as e:
            infos['description'] = 'unknown'
            logger.warning('Could not extract description: %s', e)

        # misc infos
        try:
            duration = tree.xpath('//img[@src="/res/img/icons/Icon_Uhr.png"]/@title')[0].strip()
            infos['duration'] = re.sub('^.*: ?', '', duration)
        except Exception as e:
            infos['duration'] = '0'
            logger.warning('Could not extract duration: %s', e)

        try:
            calories = tree.xpath('//img[@src="/res/img/icons/Icon_Apfel.png"]/@title')[0].strip()
            infos['calories'] = re.sub('^.*: ?', '', calories)
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

        # approach #1, extracting 'background' parameter by <script>
        try:
            js = tree.xpath('//script[@type="text/javascript" and contains(text(), "/cms/img")]/text()')[0]
            data['background'] = re.findall("/cms[^']+", js)[0]
        except:
            # approach #2, extract background parameter by <div>, https://www.newmoove.com/workouts/original-pilates
            try:
                data['background'] = tree.xpath('//div[contains(@class, "as-radio-aktiv")]/@id')[0]
            except:
                logger.debug('Could not get background parameter')

        r = self.session.post(self.newmoove_url('/cms/LightBox.html'), data)
        #with open('/tmp/test.html', 'w') as f:
        #    f.write(r.text)
        tree = html.fromstring(r.text)
        return tree.xpath('//source/@src')[0]

