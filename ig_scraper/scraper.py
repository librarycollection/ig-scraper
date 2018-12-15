import hashlib
import json
import requests
import sys

from .constants import *  # noqa


class IGScraper:
    def __init__(self):
        self.items = []

        self.session = requests.Session()
        self.session.headers = {'user-agent': CHROME_WIN_UA}
        self.session.cookies.set('ig_pr', '1')
        self.rhx_gis = None

    def get_shared_data(self, username=''):
        """Fetches the user's metadata."""
        response = self.session.get(BASE_URL + username)
        content = str(response.content)
        if '_sharedData' in content:
            try:
                shared_data = content.split("window._sharedData = ")[
                    1].split(";</script>")[0]
                return json.loads(shared_data)
            except (TypeError, KeyError, IndexError):
                pass

    def get_ig_gis(self, rhx_gis, params):
        data = rhx_gis + ":" + params
        if sys.version_info.major >= 3:
            return hashlib.md5(data.encode('utf-8')).hexdigest()
        else:
            return hashlib.md5(data).hexdigest()

    def update_ig_gis_header(self, params):
        self.rhx_gis = self.get_shared_data()['rhx_gis']
        self.session.headers.update({
            'x-instagram-gis': self.get_ig_gis(
                self.rhx_gis,
                params
            )
        })

    def scrape_hashtag(self, hashtag, end_cursor='', maximum=10, first=10, initial=True,
                       detail=False):
        if initial:
            self.items = []

        try:
            params = QUERY_HASHTAG_VARS.format(hashtag, end_cursor)
            self.update_ig_gis_header(params)
            response = self.session.get(QUERY_HASHTAG.format(params))
            response = response.json()
            data = response['data']['hashtag']
        except Exception:
            data = []

        if data:
            for item in data['edge_hashtag_to_media']['edges']:
                node = item['node']
                if node['edge_media_to_caption']['edges']:
                    caption = node['edge_media_to_caption']['edges'][0]['node']['text']
                else:
                    caption = None

                if any([detail, node['is_video']]):
                    try:
                        r = requests.get(MEDIA_URL.format(
                            node['shortcode'])).json()
                    except Exception:
                        continue

                if node['is_video']:
                    display_url = r['graphql']['shortcode_media']['video_url']
                else:
                    display_url = node['display_url']

                item = {
                    'is_video': node['is_video'],
                    'caption': caption,
                    'display_url': display_url,
                    'thumbnail_src': node['thumbnail_src'],
                    'owner_id': node['owner']['id'],
                    'id': node['id'],
                    'shortcode': node['shortcode'],
                    'taken_at_timestamp': node['taken_at_timestamp']
                }

                if detail:
                    owner = r['graphql']['shortcode_media']['owner']
                    item['profile_picture'] = owner['profile_pic_url']
                    item['username'] = owner['username']

                if item not in self.items and len(self.items) < maximum:
                    self.items.append(item)

            end_cursor = data['edge_hashtag_to_media']['page_info']['end_cursor']

            if end_cursor and len(self.items) < maximum:
                self.scrape_hashtag(end_cursor=end_cursor, detail=detail,
                                    maximum=maximum, initial=False)

        return self.items
