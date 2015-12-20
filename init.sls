{% if grains['id'] in pillar['sonarr-slack-servers'] %}

include:
  - systemd

/opt/sonarr-slack:
  file:
    - directory
  virtualenv:
    - managed
    - python: /usr/bin/python3
    - pip_upgrade: true
    - pip_pkgs:
      - arrow >= 0.7.0
      - cffi >= 1.4.1
      - characteristic >= 14.3.0
      - cryptography >= 1.1.2
      - idna >= 2.0
      - Jinja2 >= 2.8
      - MarkupSafe >= 0.23
      - pip >= 7.1.2
      - pyasn1 >= 0.1.9
      - pyasn1-modules >= 0.0.8
      - pycparser >= 2.14
      - pyOpenSSL >= 0.15.1
      - python-dateutil >= 2.4.2
      - pytz >= 2015.7
      - service-identity >= 14.0.0
      - setuptools >= 19.1.1
      - six >= 1.10.0
      - Twisted >= 15.5.0
      - zope.interface >= 4.1.3
    - require:
      - file: /opt/sonarr-slack

/opt/sonarr-slack/bin:
  file.directory

/opt/sonarr-slack/bin/sonarr-slack.py:
  file.managed:
    - source: salt://sonarr/slack/sonarr-slack.py
    - require:
      - file: /opt/sonarr-slack/bin

/etc/systemd/system/sonarr-slack.service:
  file.managed:
    - source: salt://sonarr/slack/sonarr-slack.service
    - template: jinja
    - watch_in:
      - cmd: systemctl-daemon-reload
  
sonarr-slack:
  service:
    - running
    - enable: true
    - watch:
      - virtualenv: /opt/sonarr-slack
      - file: /opt/sonarr-slack/bin/sonarr-slack.py
      - file: /etc/systemd/system/sonarr-slack.service

{% endif %}
