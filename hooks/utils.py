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
from charmhelpers.core.services import RelationContext
from charmhelpers.contrib.charmsupport import nrpe

APT_SOURCES_LIST = '/etc/apt/sources.list.d/logstash.list'
SERVICE = 'logstash'
APT_REPOSITORY_KEY = 'apt-repository'
APT_KEY_URL_KEY = 'apt-key-url'
NAGIOS_CONTEXT_KEY = 'nagios_context'
ES_RELATION = 'elasticsearch'
TCP_LISTEN_PORTS_KEY = 'tcp-listen-ports'

hooks = hookenv.Hooks()
log = hookenv.log
relations = hookenv.relations()
config = hookenv.config()
config.implicit_save = False


@hooks.hook('install')
def install():
    log('install')
    ensure_apt_repo()
    if not os.path.exists('/opt/logstash/bin/logstash'):
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
    for type, port in config.get(TCP_LISTEN_PORTS_KEY, {}).iteritems():
        inputconf += r'''  tcp {{
            port => {}
            type => "{}"
        }}'''.format(port, type)
    inputconf += '}'
    host.write_file('/etc/logstash/conf.d/input-elasticsearch.conf', inputconf)
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
    return (
        open(APT_SOURCES_LIST, 'r').read().strip()
        in config[APT_REPOSITORY_KEY]
    )


def ensure_apt_repo():
    if not has_source_list():
        apt_key_add(config[APT_KEY_URL_KEY])
        add_source_list()
        return True
    return False


def apt_key_add(keyurl):
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


def get_next_port(ports):
    if ports:
        return max(ports) + 1
    return 11001


@hooks.hook('input-tcp-relation-joined')
@hooks.hook('input-tcp-relation-changed')
def tcp_input_relation_joined():
    lsr = LogstashTcpRelation()
    log("LogstashTcpRelation: {}".format(lsr))
    if 'input-tcp' not in lsr:
        return
    r = lsr['input-tcp']
    if not r or 'types' not in r[0]:
        return
    types = r[0]['types'].split()

    portmap = config.get(TCP_LISTEN_PORTS_KEY, {})
    for type in types:
        next_port = get_next_port([port for rel, port in portmap.iteritems()])
        portmap[type] = next_port
    log("input-tcp-relation-joined/changed: using {} ".format(
        portmap))
    config[TCP_LISTEN_PORTS_KEY] = portmap
    config.save()
    if 'groks' in r[0]:
        groks = r[0]['groks'].split()
        config['grokmap'] = zip(types, groks)
    hookenv.relation_set(ports=' '.join(
        [str(port) for _, port in portmap.iteritems()]))
    write_config_and_restart()


@hooks.hook('input-tcp-relation-departed')
@hooks.hook('input-tcp-relation-broken')
def tcp_input_relation_departed():
    lsr = LogstashTcpRelation()
    log("LogstashTcpRelation: {}".format(lsr))
    print("LogstashTcpRelation: {}".format(lsr))
    r = lsr['input-tcp']
    if not r or 'types' not in r[0]:
        return
    # Assume that each unit of a relation sends identical values.
    # This should be true because all units have the same charm config.
    types = r[0]['types'].split()

    portmap = config.get(TCP_LISTEN_PORTS_KEY, {})
    for type in types:
        print "found:"+type
        if type in portmap:
            print "removing "+type
            del portmap[type]
    config[TCP_LISTEN_PORTS_KEY] = portmap
    write_config_and_restart()
    log("input-tcp-relation-departed: new ports {}".format(
        str(portmap)))
    print("input-tcp-relation-departed: new ports {}".format(
        str(portmap)))


def get_listen_ports():
    if config.get(TCP_LISTEN_PORTS_KEY, False):
        return [port for rel, port in config[TCP_LISTEN_PORTS_KEY].iteritems()]
    return []


@hooks.hook('nrpe-external-master-relation-changed')
@hooks.hook('local-monitors-relation-changed')
def update_nrpe_checks():
    listen_ports = get_listen_ports()
    nrpe_compat = nrpe.NRPE()
    ip_address = hookenv.unit_private_ip()
    for port in listen_ports:
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


class LogstashTcpRelation(RelationContext):
    name = 'input-tcp'
    interface = 'logstash-tcp'
    required_keys = ['types']


if __name__ == "__main__":
    # execute a hook based on the name the program is called by
    hooks.execute(sys.argv)
