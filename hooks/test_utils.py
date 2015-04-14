#!/usr/bin/python

import os
import re
import sys
import unittest

import mock

os.environ['CHARM_DIR'] = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(os.environ['CHARM_DIR'], 'lib'))

from charmhelpers.core import hookenv, services

hookenv.close_port = mock.MagicMock()
config = hookenv.Config({
    'apt-repository': 'myrepo',
    'apt-key-url': 'mykeyurl',
    'extra_config': 'myextraconfig',
    'nagios_context': 'juju',
    'nagios_servicegroups': ''})
config.save = mock.MagicMock()
hookenv.config = mock.MagicMock(return_value=config)
hookenv.log = mock.MagicMock()
hookenv.open_port = mock.MagicMock()
relations = {}
hookenv.relation_set = mock.MagicMock()
hookenv.relations = mock.MagicMock(return_value=relations)
hookenv.relation_ids = mock.MagicMock()
hookenv.unit_get = mock.MagicMock()

from charmhelpers import fetch
from charmhelpers.core import host

host.adduser = mock.MagicMock()
host.mkdir = mock.MagicMock()
host.service = mock.MagicMock(return_value=True)
host.write_file = mock.MagicMock()
fetch.apt_install = mock.MagicMock()
fetch.apt_update = mock.MagicMock()

import utils

utils.run = mock.MagicMock()
utils.unlink_if_exists = mock.MagicMock()
utils.apt_key_add = mock.MagicMock()
utils.add_source_list = mock.MagicMock()


class TestInstall(unittest.TestCase):
    '''Testing that there are no exceptions in install.'''

    def test_install_does_not_raise(self):
        utils.install()

    def test_installs_packages_if_no_source_list(self):
        with mock.patch('utils.has_source_list', return_value=False):
            with mock.patch('os.path.exists', return_value=False):
                utils.install()
                self.assertTrue(fetch.apt_install.called)
                self.assertEqual(
                    fetch.apt_install.call_args[0][0],
                    utils.SERVICE)

    def test_no_install_packages_if_file_exists(self):
        fetch.apt_install.reset_mock()
        with mock.patch('utils.has_source_list', return_value=True):
            with mock.patch('os.path.exists', return_value=True):
                utils.install()
                self.assertFalse(fetch.apt_install.called)


class TestConfigChanged(unittest.TestCase):

    def setUp(self):
        config._prev_dict = dict(config)
        relations.clear()
        hookenv.close_port.reset_mock()
        hookenv.open_port.reset_mock()
        hookenv.relation_set.reset_mock()
        host.service.reset_mock()
        utils.run.reset_mock()

    '''Testing that there are no exceptions in config_changed.'''
    def test_config_changed_does_not_raise(self):
        utils.config_changed()

    def test_config_changed_calls_save(self):
        utils.config_changed()
        self.assertTrue(config.save.called)

    def test_apt_key_url_calls_apt_key_add(self):
        config[utils.APT_KEY_URL_KEY] = 'foo'
        config._prev_dict[utils.APT_KEY_URL_KEY] = None
        utils.config_changed()
        self.assertTrue(utils.apt_key_add.called)
        self.assertEqual('foo', utils.apt_key_add.call_args[0][0])

    def test_password_writes_config_and_restarts(self):
        config['password'] = ''
        config._prev_dict['password'] = None
        with mock.patch('utils.write_config_file') as write_config_file:
            utils.config_changed()
            self.assertEqual(write_config_file.call_count, 1)
            self.assertEqual(host.service.call_count, 1)

    def test_source_restarts_if_es_relation(self):
        relations['elasticsearch'] = {1: {'elasticsearch/0': {
            'host': 'eshost', 'port': 'esport'}}}
        config[utils.APT_REPOSITORY_KEY] = 'master'
        config._prev_dict[utils.APT_REPOSITORY_KEY] = None
        utils.config_changed()
        self.assertEqual(host.service.call_count, 1)

    def test_source_no_restarts_if_no_es_relation(self):
        config[utils.APT_REPOSITORY_KEY] = 'master'
        config._prev_dict[utils.APT_REPOSITORY_KEY] = None
        utils.config_changed()
        self.assertEqual(host.service.call_count, 0)


class TestWriteConfigFile(unittest.TestCase):

    def setUp(self):
        host.write_file.reset_mock()

    def test_does_not_raise(self):
        utils.write_config_file()

    def test_values(self):
        relations['elasticsearch'] = {1: {'elasticsearch/0': {
            'host': 'eshost', 'port': 'esport'}}}
        self.assertEqual(utils.write_config_file(), True)
        self.assertTrue(host.write_file.called)
        self.assertEqual(
            host.write_file.call_args_list[0][0][0],
            '/etc/logstash/conf.d/output-elasticsearch.conf')
        data = host.write_file.call_args_list[0][0][1]
        self.assertTrue(None is not re.search(
            r'''output\s*\{\s*
                elasticsearch\s*\{\s*host\s*=>\s*"eshost"\s*
                  port\s* => \s* "esport"\s*
                  protocol \s* => \s*"http"\s*
            \}\s* \}
            ''', data, re.VERBOSE | re.MULTILINE), data)

    def test_no_elasticsearch(self):
        os.unlink = mock.MagicMock()
        if 'elasticsearch' in relations:
            del relations['elasticsearch']
        self.assertEqual(utils.write_config_file(), False)
        self.assertEqual(host.write_file.call_count, 0)
        self.assertEqual(os.unlink.call_count, 1)
        self.assertEqual(
            os.unlink.call_args[0][0],
            '/etc/logstash/conf.d/output-elasticsearch.conf')


class TestStart(unittest.TestCase):

    def test_start_does_not_raise(self):
        utils.start()

    def test_start_runs_service(self):
        utils.start()
        host.service.assert_called_with('start', 'logstash')


class TestStop(unittest.TestCase):

    def test_stop_does_not_raise(self):
        utils.stop()

    def test_stop_stops_service(self):
        utils.stop()
        host.service.assert_called_with('stop', 'logstash')


class TestNRPERelation(unittest.TestCase):

    def setUp(self):
        self.phookenv = mock.patch.object(services.helpers, 'hookenv')
        self.mhookenv = self.phookenv.start()
        self.mhookenv.relation_ids.return_value = ['baz']
        self.mhookenv.related_units.side_effect = lambda i: [i + '/0']
        self.mhookenv.relation_get.side_effect = [{'types': '1'},
                                                  ]
        self.mhookenv.reset_mock()

    def tearDown(self):
        self.phookenv.stop()

    def test_nrpe_relation_updates_config(self):
        utils.tcp_input_relation_joined()
        with mock.patch('charmhelpers.contrib.charmsupport.nrpe.NRPE') as nrpe:
            utils.update_nrpe_checks()
            nrpe().add_check.assert_called_once_with(
                shortname="logstash",
                description="Check port listening",
                check_cmd="check_tcp -H {} -p 11001"
                "".format(hookenv.unit_private_ip()))

    def test_nrpe_is_empty_if_no_tcp_relation(self):
        config[utils.TCP_LISTEN_PORTS_KEY] = {}
        with mock.patch('charmhelpers.contrib.charmsupport.nrpe.NRPE') as nrpe:
            utils.update_nrpe_checks()
            self.assertFalse(nrpe.add_check.called)


@mock.patch('urllib2.urlopen', mock.Mock())
class TestElasticsearchRelation(unittest.TestCase):

    def setUp(self):
        relations['elasticsearch'] = {2: {'elasticsearch/0': {
            'host': 'eshost', 'port': 'esport'}}}

    def test_elasticsearch_relation_does_not_raise(self):
        utils.elasticsearch_relation_hooks()

    def test_elasticsearch_relation_write_config_file(self):
        with mock.patch('utils.write_config_file') as mock_write_config_file:
            mock_write_config_file.return_value = (True, True)
            utils.elasticsearch_relation_hooks()
            self.assertTrue(mock_write_config_file.called)

    def test_elasticsearch_relation_write_config_file_on_departed(self):
        with mock.patch('utils.write_config_file') as mock_write_config_file:
            mock_write_config_file.return_value = (True, True)
            utils.elasticsearch_relation_hooks_gone()
            self.assertTrue(mock_write_config_file.called)


class TestInputTcpRelation(unittest.TestCase):

    def setUp(self):
        self.phookenv = mock.patch.object(services.helpers, 'hookenv')
        self.mhookenv = self.phookenv.start()
        self.mhookenv.relation_ids.return_value = ['baz']
        self.mhookenv.related_units.side_effect = lambda i: [i + '/0']
        self.mhookenv.relation_get.side_effect = [{'groks': 'a b',
                                                   'types': 'c d'},
                                                  {'groks': 'a b',
                                                   'types': 'c d'},
                                                  ]
        self.mhookenv.reset_mock()
        config[utils.TCP_LISTEN_PORTS_KEY] = {}

    def tearDown(self):
        self.phookenv.stop()

    def test_tcp_input_relation_does_not_raise(self):
        self.mhookenv.related_units.return_value = []
        utils.tcp_input_relation_joined()

    def test_tcp_input_relation_one_port_write_config_file(self):
        self.mhookenv.relation_get.side_effect = [{'groks': 'a',
                                                   'types': 'c'}]
        host.write_file.reset_mock()
        utils.tcp_input_relation_joined()
        self.assertTrue(host.write_file.called)
        contents = host.write_file.call_args_list[1][0][1]
        self.assertTrue(None is not re.search(
            r'''input \s* { \s* tcp \s* {\s*
            port \s* => \s* 11001 \s*
            type \s* => \s* "c" \s*
        }\s*
        }''', contents, re.VERBOSE | re.MULTILINE), contents)

    def test_tcp_input_relation_write_config_on_departed(self):
        utils.tcp_input_relation_joined()
        host.write_file.reset_mock()
        utils.tcp_input_relation_departed()
        self.assertTrue(host.write_file.called)
        contents = host.write_file.call_args_list[1][0][1]
        self.assertEquals(r'input {}', contents)

    def test_tcp_input_relation_sets_ports(self):
        utils.tcp_input_relation_joined()
        self.assertTrue(hookenv.relation_set.called)
        print hookenv.relation_set.call_args
        self.assertEquals({'ports': '11001 11002'},
                          hookenv.relation_set.call_args_list[0][1])

    def test_tcp_input_relation_sets_many_ports(self):
        x = utils.LogstashTcpRelation()
        print x
        self.assertEquals("c d", x['input-tcp'][0]['types'])
        host.write_file.reset_mock()
        utils.tcp_input_relation_joined()
        self.assertTrue(host.write_file.called)
        contents = host.write_file.call_args_list[1][0][1]
        self.assertTrue(None is not re.search(
            r'''input \s* { \s* tcp \s* {\s*
            port \s* => \s* 11001 \s*
            type \s* => \s* "c" \s*
        }\s*
            tcp \s* { \s*
            port \s* => \s* 11002 \s*
            type \s* => \s* "d" \s*
        }\s*
        }''', contents, re.VERBOSE | re.MULTILINE), contents)
