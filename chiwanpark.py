# -*- coding: utf-8 -*-
import os
import shutil
from datetime import datetime

from jinja2 import Environment, PackageLoader
from markdown import Markdown
import plistop
import pytz
import requests
from io import BytesIO


OUTPUT_DIR = os.environ.get('OUTPUT_DIR', './_build')
ITUNES_LIB = os.environ.get('ITUNES_LIB', None)
ITUNES_USER = os.environ.get('ITUNES_USER', None)
ITUNES_PASS = os.environ.get('ITUNES_PASS', None)
DATE_FORMAT = '%b, %d, %Y'
MONTH_FORMAT = '%b, %Y'
KST_TIMEZONE = pytz.timezone('Asia/Seoul')

jinja2_env = Environment(loader=PackageLoader('chiwanpark'))
markdown = Markdown(extensions=['meta', 'footnotes'])
templates = {
    'index': jinja2_env.get_template('index.html'),
    'article': jinja2_env.get_template('article.html'),
    'articles': jinja2_env.get_template('articles.html'),
    'itunes': jinja2_env.get_template('itunes.html'),
    'skeleton': jinja2_env.get_template('skeleton.html')
}


def url(*args):
    trees = list(args)
    trees.insert(0, u'')

    return u'/'.join(trees) if len(trees) >= 2 else u'/'


def assets(name):
    return url('assets', name)


def to_aware(obj):
    if isinstance(obj, datetime):
        if obj.tzinfo:
            return obj.astimezone(KST_TIMEZONE)
        else:
            return KST_TIMEZONE.localize(obj)

    return obj


jinja2_env.globals.update(url=url, assets=assets)


def iter_pages(path=None, trees=None):
    if not trees:
        trees = []
    if not path:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pages')

    for file_name in os.listdir(path):
        file_path = os.path.join(path, file_name)
        if os.path.isdir(file_path):
            sub_trees = list(trees)
            sub_trees.append(file_name)
            for sub_path in iter_pages(file_path, sub_trees):
                yield sub_path
        else:
            with open(file_path, 'r') as f:
                content = f.read().decode('utf-8')

            yield {'name': os.path.splitext(file_name)[0], 'trees': trees, 'content': content}


def make_output_dir(path=None):
    if not path:
        path = OUTPUT_DIR

    if not os.path.exists(path):
        os.mkdir(path)


def clear_output_dir():
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    os.mkdir(OUTPUT_DIR)


def copy_assets():
    shutil.copytree(os.path.join('.', 'assets'), os.path.join(OUTPUT_DIR, 'assets'))


def build_itunes():
    if not ITUNES_LIB:
        return ''

    result = requests.get(ITUNES_LIB, auth=(ITUNES_USER, ITUNES_PASS))
    if result.status_code != 200:
        return ''

    tracks = []

    with BytesIO(result.content) as f:
        itunes_lib = plistop.parse(f)

        for idx, track in enumerate(itunes_lib['Tracks'].itervalues()):
            if track.get('Podcast', False):
                continue

            tracks.append({
                'artist': track['Artist'],
                'name': track['Name'],
                'count': track.get('Play Count', 0),
                'added': to_aware(track['Date Added']),
                'lastPlayed': to_aware(track.get('Play Date UTC', datetime.utcfromtimestamp(0)))
            })

    return templates['itunes'].render(tracks=tracks)


def create_itunes():
    build_itunes()


def build_article(page):
    date = page['meta']['date'][0]
    title = page['meta']['title'][0]
    content = page['content']

    return templates['article'].render(date=date, title=title, content=content)


def build_article_index(articles):
    def mapper(article):
        article['month'] = datetime.strptime(article['date'], DATE_FORMAT).strftime(MONTH_FORMAT)
        return article

    articles = map(mapper, articles)

    return templates['articles'].render(articles=articles)


def create_article_index(articles):
    rendered = build_article_index(articles)

    dir_path = os.path.join(OUTPUT_DIR, 'articles')
    make_output_dir(dir_path)

    file_path = os.path.join(dir_path, 'index.html')
    with open(file_path, 'w') as f:
        f.write(rendered.encode('utf-8'))


def build_index(page):
    content = page['content']
    return templates['index'].render(content=content)


def create_cname():
    file_path = os.path.join(OUTPUT_DIR, 'CNAME')
    with open(file_path, 'w') as f:
        f.write('chiwanpark.com')


def build():
    clear_output_dir()
    copy_assets()

    articles = []

    for page in iter_pages():
        page['content'] = markdown.reset().convert(page['content'])
        page['meta'] = markdown.Meta

        template = page['meta']['template'][0]

        if template == 'article':
            rendered = build_article(page)
            articles.append({
                'date': page['meta']['date'][0],
                'name': page['name'],
                'title': page['meta']['title'][0]
            })
        elif template == 'index':
            rendered = build_index(page)
        elif template == 'itunes':
            rendered = build_itunes()
        else:
            continue

        dir_path = os.path.join(OUTPUT_DIR, *page['trees'])
        file_path = os.path.join(dir_path, page['name'] + '.html')
        make_output_dir(dir_path)
        with open(file_path, 'w') as f:
            f.write(rendered.encode('utf-8'))

    create_article_index(articles)
    create_cname()

    create_itunes()


if __name__ == '__main__':
    build()