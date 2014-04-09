#!/usr/bin/python
#
# Copyright (C) 2014  Simo Sorce <simo@redhat.com>
#
# see file 'COPYING' for use and warranty information
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from ipsilon.tools.certs import Certificate
from lxml import etree
import lasso


SAML2_NAMEID_MAP = {
    'email': lasso.SAML2_NAME_IDENTIFIER_FORMAT_EMAIL,
    'encrypted': lasso.SAML2_NAME_IDENTIFIER_FORMAT_ENCRYPTED,
    'entity': lasso.SAML2_NAME_IDENTIFIER_FORMAT_ENTITY,
    'kerberos': lasso.SAML2_NAME_IDENTIFIER_FORMAT_KERBEROS,
    'persistent': lasso.SAML2_NAME_IDENTIFIER_FORMAT_PERSISTENT,
    'transient': lasso.SAML2_NAME_IDENTIFIER_FORMAT_TRANSIENT,
    'unspecified': lasso.SAML2_NAME_IDENTIFIER_FORMAT_UNSPECIFIED,
    'windows': lasso.SAML2_NAME_IDENTIFIER_FORMAT_WINDOWS,
    'x509': lasso.SAML2_NAME_IDENTIFIER_FORMAT_X509,
}

SAML2_SERVICE_MAP = {
    'sso-post': ('SingleSignOnService',
                 lasso.SAML2_METADATA_BINDING_POST),
    'sso-redirect': ('SingleSignOnService',
                     lasso.SAML2_METADATA_BINDING_REDIRECT),
    'logout-redirect': ('SingleLogoutService',
                        lasso.SAML2_METADATA_BINDING_REDIRECT),
    'response-post': ('AssertionConsumerService',
                      lasso.SAML2_METADATA_BINDING_POST)
}

EDESC = '{%s}EntityDescriptor' % lasso.SAML2_METADATA_HREF
NSMAP = {
    'md': lasso.SAML2_METADATA_HREF,
    'ds': lasso.DS_HREF
}

IDPDESC = 'IDPSSODescriptor'
SPDESC = 'SPSSODescriptor'

IDP_ROLE = 'idp'
SP_ROLE = 'sp'


def mdElement(_parent, _tag, **kwargs):
    tag = '{%s}%s' % (lasso.SAML2_METADATA_HREF, _tag)
    return etree.SubElement(_parent, tag, **kwargs)


def dsElement(_parent, _tag, **kwargs):
    tag = '{%s}%s' % (lasso.DS_HREF, _tag)
    return etree.SubElement(_parent, tag, **kwargs)


class Metadata(object):

    def __init__(self, role=None):
        self.root = etree.Element(EDESC, nsmap=NSMAP)
        self.entityid = None
        self.role = None
        self.set_role(role)

    def set_entity_id(self, url):
        self.entityid = url
        self.root.set('entityID', url)

    def set_role(self, role):
        if role is None:
            return
        elif role == IDP_ROLE:
            description = IDPDESC
        elif role == SP_ROLE:
            description = SPDESC
        else:
            raise ValueError('invalid role: %s' % role)
        self.role = mdElement(self.root, description)
        self.role.set('protocolSupportEnumeration', lasso.SAML2_PROTOCOL_HREF)
        return self.role

    def add_cert(self, certdata, use):
        desc = mdElement(self.role, 'KeyDescriptor')
        desc.set('use', use)
        info = dsElement(desc, 'KeyInfo')
        data = dsElement(info, 'X509Data')
        cert = dsElement(data, 'X509Certificate')
        cert.text = certdata

    def add_certs(self, signcert=None, enccert=None):
        if signcert:
            self.add_cert(signcert.get_cert(), 'signing')
        if enccert:
            self.add_cert(enccert.get_cert(), 'encryption')

    def add_service(self, service, location):
        svc = mdElement(self.role, service[0])
        svc.set('Binding', service[1])
        svc.set('Location', location)

    def add_allowed_name_format(self, name_format):
        nameidfmt = mdElement(self.role, 'NameIDFormat')
        nameidfmt.text = name_format

    def output(self, path):
        data = etree.tostring(self.root, xml_declaration=True,
                              encoding='UTF-8', pretty_print=True)
        with open(path, 'w') as f:
            f.write(data)


if __name__ == '__main__':
    import tempfile
    import shutil
    import os

    tmpdir = tempfile.mkdtemp()

    try:
        # Test IDP generation
        sign_cert = Certificate(tmpdir)
        sign_cert.generate('idp-signing-cert', 'idp.ipsilon.example.com')
        enc_cert = Certificate(tmpdir)
        enc_cert.generate('idp-encryption-cert', 'idp.ipsilon.example.com')
        idp = Metadata()
        idp.set_entity_id('https://ipsilon.example.com/idp/metadata')
        idp.set_role(IDP_ROLE)
        idp.add_certs(sign_cert, enc_cert)
        idp.add_service(SAML2_SERVICE_MAP['sso-post'],
                        'https://ipsilon.example.com/idp/saml2/POST')
        idp.add_service(SAML2_SERVICE_MAP['sso-redirect'],
                        'https://ipsilon.example.com/idp/saml2/Redirect')
        for k in SAML2_NAMEID_MAP:
            idp.add_allowed_name_format(SAML2_NAMEID_MAP[k])
        md_file = os.path.join(tmpdir, 'metadata.xml')
        idp.output(md_file)
        with open(md_file) as fd:
            text = fd.read()
        print '==================== IDP ===================='
        print text
        print '============================================='

        # Test SP generation
        sign_cert = Certificate(tmpdir)
        sign_cert.generate('sp-signing-cert', 'sp.ipsilon.example.com')
        sp = Metadata()
        sp.set_entity_id('https://ipsilon.example.com/samlsp/metadata')
        sp.set_role(SP_ROLE)
        sp.add_certs(sign_cert)
        sp.add_service(SAML2_SERVICE_MAP['logout-redirect'],
                       'https://ipsilon.example.com/samlsp/logout')
        sp.add_service(SAML2_SERVICE_MAP['response-post'],
                       'https://ipsilon.example.com/samlsp/postResponse')
        md_file = os.path.join(tmpdir, 'metadata.xml')
        sp.output(md_file)
        with open(md_file) as fd:
            text = fd.read()
        print '===================== SP ===================='
        print text
        print '============================================='

    finally:
        shutil.rmtree(tmpdir)