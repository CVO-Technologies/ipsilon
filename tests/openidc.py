#!/usr/bin/python
#
# Copyright (C) 2016 Ipsilon project Contributors, for license see COPYING

from helpers.common import IpsilonTestBase  # pylint: disable=relative-import
from helpers.http import HttpSessions  # pylint: disable=relative-import
import os
import json
import pwd
import sys
import requests
import hashlib
from string import Template

idp_g = {'TEMPLATES': '${TESTDIR}/templates/install',
         'CONFDIR': '${TESTDIR}/etc',
         'DATADIR': '${TESTDIR}/lib',
         'CACHEDIR': '${TESTDIR}/cache',
         'HTTPDCONFD': '${TESTDIR}/${NAME}/conf.d',
         'STATICDIR': '${ROOTDIR}',
         'BINDIR': '${ROOTDIR}/ipsilon',
         'WSGI_SOCKET_PREFIX': '${TESTDIR}/${NAME}/logs/wsgi'}


idp_a = {'hostname': '${ADDRESS}:${PORT}',
         'admin_user': '${TEST_USER}',
         'system_user': '${TEST_USER}',
         'instance': '${NAME}',
         'testauth': 'yes',
         'pam': 'no',
         'gssapi': 'no',
         'ipa': 'no',
         'openidc': 'yes',
         'openidc_subject_salt': 'testcase',
         'server_debugging': 'True'}


sp1_g = {'HTTPDCONFD': '${TESTDIR}/${NAME}/conf.d',
         'OPENIDC_TEMPLATE': '${TESTDIR}/templates/install/openidc/rp.conf',
         'CONFFILE': '${TESTDIR}/${NAME}/conf.d/ipsilon-%s.conf',
         'HTTPDIR': '${TESTDIR}/${NAME}/%s'}


sp1_a = {'hostname': '${ADDRESS}',
         'auth_location': '/sp',
         'openidc': 'yes',
         'openidc_idp_url': 'https://127.0.0.10:45080/idp1',
         'openidc_response_type': 'code',
         'openidc_skip_ssl_validation': 'yes',
         'httpd_user': '${TEST_USER}'}


sp2_g = {'HTTPDCONFD': '${TESTDIR}/${NAME}/conf.d',
         'OPENIDC_TEMPLATE': '${TESTDIR}/templates/install/openidc/rp.conf',
         'CONFFILE': '${TESTDIR}/${NAME}/conf.d/ipsilon-%s.conf',
         'HTTPDIR': '${TESTDIR}/${NAME}/%s'}


sp2_a = {'hostname': '${ADDRESS}',
         'auth_location': '/sp',
         'openidc': 'yes',
         'openidc_idp_url': 'https://127.0.0.10:45080/idp1',
         'openidc_response_type': 'id_token',
         'openidc_subject_type': 'public',
         'openidc_skip_ssl_validation': 'yes',
         'httpd_user': '${TEST_USER}'}


sp3_g = {'HTTPDCONFD': '${TESTDIR}/${NAME}/conf.d',
         'OPENIDC_TEMPLATE': '${TESTDIR}/templates/install/openidc/rp.conf',
         'CONFFILE': '${TESTDIR}/${NAME}/conf.d/ipsilon-%s.conf',
         'HTTPDIR': '${TESTDIR}/${NAME}/%s'}


sp3_a = {'hostname': '${ADDRESS}',
         'auth_location': '/sp',
         'openidc': 'yes',
         'openidc_idp_url': 'https://127.0.0.10:45080/idp1',
         'openidc_response_type': 'id_token token',
         'openidc_skip_ssl_validation': 'yes',
         'httpd_user': '${TEST_USER}'}


def fixup_sp_httpd(httpdir):
    location = """
AddOutputFilter INCLUDES .html

Alias /sp ${HTTPDIR}/sp

<Directory ${HTTPDIR}/sp>
    Options +Includes
    Require all granted
</Directory>
"""
    t = Template(location)
    text = t.substitute({'HTTPDIR': httpdir})
    with open(httpdir + '/conf.d/ipsilon-openidc.conf', 'a') as f:
        f.write(text)

    index = """<!--#printenv -->"""
    os.mkdir(httpdir + '/sp')
    with open(httpdir + '/sp/index.html', 'w') as f:
        f.write(index)


def convert_to_dict(envlist):
    values = {}
    for pair in envlist.split('\n'):
        if pair.find('=') > 0:
            (key, value) = pair.split('=', 1)
            if key.startswith('OIDC_') and not key.endswith('_0'):
                values[key] = value
    return values


def check_info_results(text, expected):
    """
    Logout, login, fetch RP page to get the info variables and
    compare the OIDC_CLAIM_ ones to what we expect.
    """

    # Confirm that the expected values are in the output and that there
    # are no unexpected OIDC_CLAIM_ vars, and drop the _0 version.
    data = convert_to_dict(text)

    toreturn = {}
    toreturn['access_token'] = data.pop('OIDC_access_token', None)
    toreturn['access_token_expires'] = data.pop('OIDC_access_token_expires',
                                                None)

    for key in expected:
        item = data.pop('OIDC_CLAIM_' + key)
        if item != expected[key]:
            raise ValueError('Expected %s, got %s' % (expected[key], item))

    # Ignore a couple of attributes
    ignored = ['exp', 'c_hash', 'at_hash', 'aud', 'nonce', 'iat', 'auth_time',
               'azp']
    for attr in ignored:
        data.pop('OIDC_CLAIM_%s' % attr, None)

    if len(data) > 0:
        raise ValueError('Unexpected values %s' % data)

    return toreturn


class IpsilonTest(IpsilonTestBase):

    def __init__(self):
        super(IpsilonTest, self).__init__('openidc', __file__)

    def setup_servers(self, env=None):
        print "Installing IDP server"
        name = 'idp1'
        addr = '127.0.0.10'
        port = '45080'
        idp = self.generate_profile(idp_g, idp_a, name, addr, port)
        conf = self.setup_idp_server(idp, name, addr, port, env)

        print "Starting IDP's httpd server"
        self.start_http_server(conf, env)

        print "Installing first SP server"
        name = 'sp1'
        addr = '127.0.0.11'
        port = '45081'
        sp = self.generate_profile(sp1_g, sp1_a, name, addr, port)
        conf = self.setup_sp_server(sp, name, addr, port, env)
        fixup_sp_httpd(os.path.dirname(conf))

        print "Starting first SP's httpd server"
        self.start_http_server(conf, env)

        print "Installing second SP server"
        name = 'sp2'
        addr = '127.0.0.12'
        port = '45082'
        sp = self.generate_profile(sp2_g, sp2_a, name, addr, port)
        conf = self.setup_sp_server(sp, name, addr, port, env)
        fixup_sp_httpd(os.path.dirname(conf))

        print "Starting second SP's httpd server"
        self.start_http_server(conf, env)

        print "Installing third SP server"
        name = 'sp3'
        addr = '127.0.0.13'
        port = '45083'
        sp = self.generate_profile(sp3_g, sp3_a, name, addr, port)
        conf = self.setup_sp_server(sp, name, addr, port, env)
        fixup_sp_httpd(os.path.dirname(conf))

        print "Starting third SP's httpd server"
        self.start_http_server(conf, env)


if __name__ == '__main__':

    idpname = 'idp1'
    sp1name = 'sp1'
    sp2name = 'sp2'
    sp3name = 'sp3'
    user = pwd.getpwuid(os.getuid())[0]

    sess = HttpSessions()
    sess.add_server(idpname, 'https://127.0.0.10:45080', user, 'ipsilon')
    sess.add_server(sp1name, 'https://127.0.0.11:45081')
    sess.add_server(sp2name, 'https://127.0.0.12:45082')
    sess.add_server(sp3name, 'https://127.0.0.13:45083')

    print "openidc: Authenticate to IDP ...",
    try:
        sess.auth_to_idp(idpname)
    except Exception, e:  # pylint: disable=broad-except
        print >> sys.stderr, " ERROR: %s" % repr(e)
        sys.exit(1)
    print " SUCCESS"

    print "openidc: Registering test client ...",
    try:
        client_info = {
            'redirect_uris': ['https://invalid/'],
            'response_types': ['code'],
            'grant_types': ['authorization_code'],
            'application_type': 'web',
            'client_name': 'Test suite client',
            'client_uri': 'https://invalid/',
            'token_endpoint_auth_method': 'client_secret_post'
        }
        r = requests.post('https://127.0.0.10:45080/idp1/openidc/Registration',
                          json=client_info)
        r.raise_for_status()
        reg_resp = r.json()
    except Exception, e:  # pylint: disable=broad-except
        print >> sys.stderr, " ERROR: %s" % repr(e)
        sys.exit(1)
    print " SUCCESS"

    print "openidc: Access first SP Protected Area ...",
    try:
        page = sess.fetch_page(idpname, 'https://127.0.0.11:45081/sp/')
        h = hashlib.sha256()
        h.update('127.0.0.11')
        h.update(user)
        h.update('testcase')
        expect = {
            'sub': h.hexdigest(),
            'iss': 'https://127.0.0.10:45080/idp1/openidc/',
            'amr': json.dumps([]),
            'acr': '0'
        }
        token = check_info_results(page.text, expect)
    except ValueError, e:
        print >> sys.stderr, " ERROR: %s" % repr(e)
        sys.exit(1)
    print " SUCCESS"

    print "openidc: Retrieving token info ...",
    try:
        # Testing token without client auth
        r = requests.post('https://127.0.0.10:45080/idp1/openidc/TokenInfo',
                          data={'token': token['access_token']})
        if r.status_code != 401:
            raise Exception('No 401 provided')

        # Testing token where we removed part of token ID
        r = requests.post('https://127.0.0.10:45080/idp1/openidc/TokenInfo',
                          data={'token': token['access_token'][1:],
                                'client_id': reg_resp['client_id'],
                                'client_secret': reg_resp['client_secret']})
        r.raise_for_status()
        info = r.json()
        if info['active']:
            raise Exception('Token active')

        # Testing token where we rempoved part of check string
        r = requests.post('https://127.0.0.10:45080/idp1/openidc/TokenInfo',
                          data={'token': token['access_token'][:-1],
                                'client_id': reg_resp['client_id'],
                                'client_secret': reg_resp['client_secret']})
        r.raise_for_status()
        info = r.json()
        if info['active']:
            raise Exception('Token active')

        # Testing valid token
        r = requests.post('https://127.0.0.10:45080/idp1/openidc/TokenInfo',
                          data={'token': token['access_token'],
                                'client_id': reg_resp['client_id'],
                                'client_secret': reg_resp['client_secret']})
        r.raise_for_status()
        info = r.json()
        if 'error' in info:
            raise Exception('Token introspection returned error: %s'
                            % info['error'])
        if not info['active']:
            raise Exception('Token not active')
        if info['username'] != user:
            raise Exception('Token for different user?')
        if info['token_type'] != 'Bearer':
            raise Exception('Unexpected token type: %s' % info['token_type'])

        scopes_needed = ['openid']
        info['scope'] = info['scope'].split(' ')
        for scope in scopes_needed:
            if scope not in info['scope']:
                raise Exception('Missing scope: %s' % scope)
            info['scope'].remove(scope)
        if len(info['scope']) != 0:
            raise Exception('Unexpected scopes found: %s' % info['scope'])
    except ValueError, e:
        print >> sys.stderr, " ERROR: %s" % repr(e)
        sys.exit(1)
    print " SUCCESS"

    print "openidc: Access second SP Protected Area ...",
    try:
        page = sess.fetch_page(idpname, 'https://127.0.0.12:45082/sp/')
        expect = {
            'sub': user,
            'iss': 'https://127.0.0.10:45080/idp1/openidc/',
            'amr': json.dumps([]),
            'acr': '0'
        }
        check_info_results(page.text, expect)
    except ValueError, e:
        print >> sys.stderr, " ERROR: %s" % repr(e)
        sys.exit(1)
    print " SUCCESS"

    print "openidc: Access third SP Protected Area ...",
    try:
        page = sess.fetch_page(idpname, 'https://127.0.0.13:45083/sp/')
        h = hashlib.sha256()
        h.update('127.0.0.13')
        h.update(user)
        h.update('testcase')
        expect = {
            'sub': h.hexdigest(),
            'iss': 'https://127.0.0.10:45080/idp1/openidc/',
            'amr': json.dumps([]),
            'acr': '0'
        }
        check_info_results(page.text, expect)
    except ValueError, e:
        print >> sys.stderr, " ERROR: %s" % repr(e)
        sys.exit(1)
    print " SUCCESS"
