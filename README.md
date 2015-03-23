logstash-juju-charm
==============================

Juju Charm for logstash

This charm uses deb packages from http://logstash.net/docs/1.4.2/repositories
or whatever is configured by the apt-repository setting.

Inputs :
  TCP - relate a charm which supports writing log to TCP port
Outputs :
  elasticsearch - create relationship with elasticsearch charm

*disabled the web service ...   use kibana! (also joinable charm)*

example 1 - NOOP ELK
=====================================

    juju deploy local:trusty/logstash
    juju deploy local:trusty/elasticsearch
    juju deploy local:trusty/kibana
    juju add-relation kibana elasticsearch:rest
    juju add-relation logstash elasticsearch
    juju expose kibana

http://ip-of-kibana

example 2 - something logging
=====================================

    juju deploy local:trusty/logstash
    juju deploy local:trusty/elasticsearch
    juju deploy local:trusty/kibana
    juju add-relation kibana elasticsearch:rest
    juju add-relation logstash elasticsearch
    juju deploy local:trusty/somecharmwhichlogs
    juju add-relation logstash somecharmwhichlogs
    juju expose kibana

http://ip-of-kibana
