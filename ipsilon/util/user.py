#!/usr/bin/python
#
# Copyright (C) 2013  Simo Sorce <simo@redhat.com>
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

from ipsilon.util.data import Store
from ipsilon.util.log import Log
import cherrypy


class Site(object):
    def __init__(self, value):
        # implement lookup of sites id for link/name
        self.link = value
        self.name = value


class User(object):
    def __init__(self, username):
        if username is None:
            self.name = None
            self._userdata = dict()
        else:
            self._userdata = self._get_user_data(username)
            self.name = username

    def _get_user_data(self, username):
        store = Store()
        return store.get_user_preferences(username)

    def reset(self):
        self.name = None
        self._userdata = dict()

    @property
    def is_anonymous(self):
        if self.name:
            return False
        return True

    @property
    def is_admin(self):
        if 'is_admin' in self._userdata:
            if str(self._userdata['is_admin']) == '1':
                return True
        return False

    @is_admin.setter
    def is_admin(self, value):
        if value is True:
            self._userdata['is_admin'] = '1'
        else:
            self._userdata['is_admin'] = '0'

    @property
    def fullname(self):
        if 'fullname' in self._userdata:
            return self._userdata['fullname']
        else:
            return self.name

    @fullname.setter
    def fullname(self, value):
        self._userdata['fullname'] = value

    @property
    def email(self):
        if 'email' in self._userdata:
            return self._userdata['email']
        else:
            return None

    @property
    def sites(self):
        if 'sites' in self._userdata:
            d = []
            for site in self._userdata['sites']:
                d.append(Site(site))
        else:
            return []

    @sites.setter
    def sites(self):
        # TODO: implement setting sites via the user object ?
        raise AttributeError


class UserSession(Log):
    def __init__(self):
        self.user = self.get_data('user', 'name')
        self.userattrs = self.get_user_attrs()

    def get_user(self):
        return User(self.user)

    def remote_login(self):
        if cherrypy.request.login:
            self.login(cherrypy.request.login)
        else:
            self.nuke_data('user')

    def login(self, username, userattrs=None):
        if self.user == username:
            return

        # REMOTE_USER changed, replace user
        self.nuke_data('user')
        self.save_data('user', 'name', username)
        self.user = username

        # Save additional data provided by the login manager
        self.nuke_data('userattrs')
        if userattrs:
            self.save_user_attrs(userattrs)

        cherrypy.log('LOGIN SUCCESSFUL: %s' % username)

    def logout(self, user):
        if user is not None:
            if not type(user) is User:
                raise TypeError
            # Completely reset user data
            cherrypy.log.error('%s %s' % (user.name, user.fullname))
            user.reset()

        # Destroy current session in all cases
        cherrypy.lib.sessions.expire()

    def get_user_attrs(self):
        userattrs = dict()
        if 'userattrs' in cherrypy.session:
            userattrs = cherrypy.session['userattrs']
        return userattrs

    def save_user_attrs(self, userattrs):
        cherrypy.session['userattrs'] = userattrs
        cherrypy.session.save()
        self._debug('Saved user attrs')
        self.userattrs = userattrs

    def save_data(self, facility, name, data):
        """ Save named data in the session so it can be retrieved later """
        if facility not in cherrypy.session:
            cherrypy.session[facility] = dict()
        cherrypy.session[facility][name] = data
        cherrypy.session.save()
        self._debug('Saved session data named [%s:%s]' % (facility, name))

    def get_data(self, facility, name):
        """ Get named data in the session if available """
        if facility not in cherrypy.session:
            return None
        if name not in cherrypy.session[facility]:
            return None
        return cherrypy.session[facility][name]

    def nuke_data(self, facility, name=None):
        if facility not in cherrypy.session:
            return
        if name:
            if name not in cherrypy.session[facility]:
                return
            cherrypy.session[facility][name] = None
            del cherrypy.session[facility][name]
            self._debug('Nuked session data named [%s:%s]' % (facility, name))
        else:
            del cherrypy.session[facility]
            self._debug('Nuked session facility [%s]' % (facility,))
        cherrypy.session.save()
