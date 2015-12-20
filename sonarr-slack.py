# -*- mode: python; coding: utf-8 -*-

import sys
import json
import datetime
import arrow
import argparse
from jinja2 import Template

from twisted.internet import defer
from twisted.internet import endpoints
from twisted.internet import reactor
from twisted.internet.protocol import Protocol
from twisted.logger import Logger
from twisted.logger import globalLogBeginner
from twisted.logger import textFileLogObserver
from twisted.web.client import Agent
from twisted.web.client import HTTPConnectionPool
from twisted.web.client import ResponseDone
from twisted.web.client import _HTTP11ClientFactory
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.web.resource import Resource
from twisted.web.server import Site

from zope.interface import implementer

class QuietHTTP11ClientFactory(_HTTP11ClientFactory):
    noisy = False

@implementer(IBodyProducer)
class StringProducer(object):
    log = Logger()
    
    def __init__(self, body):
        self.body = body
        self.length = len(self.body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def stopProducing(self):
        pass

    def pauseProducing(self):
        pass

class GetResults(Protocol):
    log = Logger()

    def __init__(self):
        self.finished = defer.Deferred()
        self.buffer = []

    def dataReceived(self, data):
        self.buffer.append(data)

    def connectionLost(self, reason):
        if not isinstance(reason.value, ResponseDone):
            self.log.debug(reason)

        self.finished.callback(b''.join(self.buffer))

template = Template("""{"text": "{% if data['EventType'] == 'Test' %}Tested{% elif data['EventType'] == 'Grab' %}Grabbed{% elif data['EventType'] == 'Download' %}Downloaded{% else %}Something unknown happened to{% endif %} episodes from _{{ data['Series']['Title'] }}_",
 "attachments": [
{% if data['Episodes'] is not none %}{% for episode in data['Episodes'] %}{% set s = '{:02d}'.format(episode['SeasonNumber']) %}{% set e = '{:02d}'.format(episode['EpisodeNumber']) %}    {"fallback": "S{{ s }}E{{ e }} - {{ episode['Title'] }}",
     "text": "S{{ s }}E{{ e }} - _{{ episode['Title'] }}_{% if episode['Quality'] is not none %} [{{ episode['Quality'] }}]{% endif %}{% if episode['AirDate'] is not none %}
First aired: {{ episode['AirDate'] }}{% endif %}",
     "mrkdwn_in": ["pretext", "text", "fields"],
     "color": "good"}{% if not loop.last %},
{% endif %}{% endfor %}{% endif %}]}
""")

class RootPage(Resource):
    log = Logger()

    def __init__(self, options):
        Resource.__init__(self)

        self.options = options
        self.pool = HTTPConnectionPool(reactor, persistent = True)
        self.pool.maxPersistentPerHost = 4
        self.pool._factory = QuietHTTP11ClientFactory
        self.agent = Agent(reactor, pool = self.pool)

    def getChild(self, name, request):
        if name == b'':
            return self
        return Resource.getChild(self, name, request)

    def render_GET(self, request):
        request.setHeader(b'Content-Type', 'text/plain; charset=utf-8')
        return b'OK'

    def render_POST(self, request):
        return self._render('POST', request)

    def render_PUT(self, request):
        return self._render('PUT', request)

    def _render(self, method, request):
        data = request.content.getvalue()
        reactor.callLater(0.0, self._send, data)
        request.setHeader(b'Content-Type', b'text/plain; charset=utf-8')
        return 'OK'.encode('utf-8')

    def _send(self, data):
        try:
            data = data.decode('utf-8')
        except UnicodeDecodeError as e:
            self.log.error('Invalid UTF-8 data: {r:}', r = e.reason)
            return

        try:
            data = json.loads(data)
        except ValueError as e:
            self.log.error('Invalid JSON data: {r:}', r = e.args[0])
            return

        if not isinstance(data, dict):
            self.log.error('Was expecting JSON mapping object')
            return
        
        if data.get('EventType') in ['Test', 'Grab', 'Download']:
            body = StringProducer(template.render(data = data).encode('utf-8'))
            headers = Headers({b'Content-Type': [b'application/json; charset=utf-8']})
            d = self.agent.request(b'POST', self.options.webhook.encode('utf-8'), headers, body)
            d.addCallback(self._finish)
            
        else:
            self.log.info('Not sending a Slack notification for event type {t:}', t = data.get('EventType'))
            
    def _finish(self, response):
        f = GetResults()
        f.finished.addCallback(self._results)
        response.deliverBody(f)

    def _results(self, results):
        self.log.debug('Slack says "{d:}"', d = results.decode('utf-8'))
        
class Main(object):
    log = Logger()

    def __init__(self, options):
        self.options = options

        reactor.callWhenRunning(self.start)

    def start(self):
        self.root = RootPage(self.options)
        self.site = Site(self.root)
        self.site.noisy = False
        
        self.endpoint = endpoints.serverFromString(reactor, self.options.endpoint)
        self.endpoint.listen(self.site)


parser = argparse.ArgumentParser()

parser.add_argument('--webhook', required=True)
parser.add_argument('--endpoint', default='tcp:10001')

options = parser.parse_args()

output = textFileLogObserver(sys.stderr)
globalLogBeginner.beginLoggingTo([output])

m = Main(options)
reactor.run()
