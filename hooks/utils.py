#!/usr/bin/python
import os
import subprocess
import sys
import urllib2

from charmhelpers import fetch
from charmhelpers.core import (
    hookenv,
    host,
)
from charmhelpers.contrib.charmsupport import nrpe

APT_SOURCES_LIST = '/etc/apt/sources.list.d/logstash.list'
SERVICE = 'logstash'
APT_REPOSITORY_KEY = 'apt-repository'
APT_KEY_URL_KEY = 'apt-key-url'
NAGIOS_CONTEXT_KEY = 'nagios_context'
ES_RELATION = 'elasticsearch'
TCP_LISTEN_PORTS_KEY = 'tcp-listen-ports'
EXTRA_CONFIG_KEY = 'extra_config'

hooks = hookenv.Hooks()
log = hookenv.log
relations = hookenv.relations()
config = hookenv.config()
config.implicit_save = False


def maintenance_status(message):
    log(message)
    try:
        subprocess.call(['status-set', 'maintenance', message])
    except:
        pass


@hooks.hook('install')
def install():
    log('install')
    fat_option()
    ensure_apt_repo()
    if not os.path.exists('/etc/init/logstash.conf'):
        fetch.apt_update()
        fetch.apt_install(SERVICE, fatal=True)


@hooks.hook('config-changed')
def config_changed():
    for key in config:
        if config.changed(key):
            msg = "config['{}'] changed from {} to {}".format(
                key, config.previous(key), config[key])
            print(msg)
            log(msg)
    if config.changed(APT_KEY_URL_KEY) and config[APT_KEY_URL_KEY]:
        apt_key_add(config[APT_KEY_URL_KEY])
    if config.changed(APT_REPOSITORY_KEY) and config[APT_REPOSITORY_KEY]:
        install()
    if config.changed(NAGIOS_CONTEXT_KEY):
        update_nrpe_checks()
    write_config_and_restart()
    config.save()


@hooks.hook('start')
def start():
    host.service_start(SERVICE)


@hooks.hook('stop')
def stop():
    host.service_stop(SERVICE)
    subprocess.call(["update-rc.d", SERVICE, "disable"])


@hooks.hook('upgrade-charm')
def upgrade_charm():
    log('upgrading charm')


def fat_option():
    if not config['apt-repository'] and not config['apt-key-url']:
        config['apt-repository'] = (
            'deb http://localhost:8000/files/debian stable main')
        try:
            subprocess.check_call(["apt-key", "add",
                                   "files/GPG-KEY-elasticsearch"])
        except Exception as e:
            maintenance_status(e)
        if not os.fork():
            os.execvp('python', ['python', '-mSimpleHTTPServer'])


def write_config_file():
    es_host, es_port = get_es_endpoint()
    if not (es_host and es_port):
        try:
            os.unlink('/etc/logstash/conf.d/output-elasticsearch.conf')
        except:
            pass
        return False
    host.write_file('/etc/logstash/conf.d/output-elasticsearch.conf',
                    r'''
output {{
  elasticsearch {{ host => "{0}"
                  port => "{1}"
                  protocol => "http"
  }}
}}
'''.format(es_host, es_port))
    inputconf = 'input {'
    inputconf += r'''  tcp {{
            port => {}
            codec => "json"
        }}'''.format(9999)
    inputconf += '}'
    host.write_file('/etc/logstash/conf.d/input-tcp.conf', inputconf)
    host.write_file('/etc/logstash/conf.d/filter.conf',
                    open('files/filter.conf').read())
    host.write_file('/etc/logstash/conf.d/extra-config.conf',
                    config[EXTRA_CONFIG_KEY])
    return True


def write_config_and_restart():
    if write_config_file():
        host.service_restart(SERVICE)


def relation_param(relation, name, default=None):
    for rel in relations.get(relation, {}).itervalues():
        for unit in rel.itervalues():
            if name in unit:
                param = unit.get(name, default)
                log("relation_param({}, {}, {}) => {}".format(
                    relation, name, default, param))
                return param
    log("relation_param({}, {}, {}) => {} ## relations: {}".format(
        relation, name, default, default, str(relations)))
    return default


def get_es_endpoint():
    return (relation_param(ES_RELATION, 'host'),
            relation_param(ES_RELATION, 'port', '9200')
            )


def has_source_list():
    if not os.path.exists(APT_SOURCES_LIST):
        return False
    try:
        return (
            open(APT_SOURCES_LIST, 'r').read().strip()
            in config[APT_REPOSITORY_KEY]
        )
    except:
        return False


def ensure_apt_repo():
    if not has_source_list():
        apt_key_add(config[APT_KEY_URL_KEY])
        add_source_list()
        return True
    return False


def apt_key_add(keyurl):
    if not keyurl:
        return
    try:
        r = urllib2.urlopen(keyurl)
        data = r.read()
        PIPE = subprocess.PIPE
        proc = subprocess.Popen(('apt-key', 'add', '-'),
                                stdin=PIPE, stdout=PIPE, stderr=PIPE)
        out, err = proc.communicate(input=data)
        if out != 'OK\n' or err != '':
            log("error running apt-key add:" + out + err)
    except Exception as e:
        log("error running apt-key add:" + str(e))


def add_source_list():
    host.write_file(APT_SOURCES_LIST, config[APT_REPOSITORY_KEY] + "\n")


@hooks.hook('input-tcp-relation-joined')
@hooks.hook('input-tcp-relation-changed')
def tcp_input_relation_joined():
    log("input-tcp-relation-joined/changed")
    hookenv.relation_set(port=9999)
    write_config_and_restart()


@hooks.hook('nrpe-external-master-relation-changed')
@hooks.hook('local-monitors-relation-changed')
def update_nrpe_checks():
    nrpe_compat = nrpe.NRPE()
    ip_address = hookenv.unit_private_ip()
    for port in [9999]:
        nrpe_compat.add_check(
            shortname=SERVICE,
            description='Check port listening',
            check_cmd='check_tcp -H {} -p {}'.format(
                ip_address, port))
    nrpe_compat.write()


@hooks.hook('elasticsearch-relation-departed')
@hooks.hook('elasticsearch-relation-broken')
def elasticsearch_relation_hooks_gone():
    log("elasticsearch-relation-(departed|broken)")
    write_config_and_restart()


@hooks.hook('elasticsearch-relation-joined')
@hooks.hook('elasticsearch-relation-changed')
def elasticsearch_relation_hooks():
    log("elasticsearch-relation-(joined|changed)")
    write_config_and_restart()


if __name__ == "__main__":
    # execute a hook based on the name the program is called by
    hooks.execute(sys.argv)
