# This file is part of Indico.
# Copyright (C) 2002 - 2015 European Organization for Nuclear Research (CERN).
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# Indico is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Indico; if not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from uuid import uuid4

from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declared_attr

from indico.core.db import db
from indico.util.string import return_ascii


class OAuthApplication(db.Model):
    """OAuth applications registered in Indico"""

    __tablename__ = 'applications'

    @declared_attr
    def __table_args__(cls):
        return (db.Index('ix_uq_applications_name_lower', db.func.lower(cls.name), unique=True),
                {'schema': 'oauth'})

    #: the unique id of the application
    id = db.Column(
        db.Integer,
        primary_key=True
    )
    #: human readable name
    name = db.Column(
        db.String,
        nullable=False
    )
    #: human readable description
    description = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    #: the OAuth client_id
    client_id = db.Column(
        db.String,
        unique=True,
        nullable=False,
        default=lambda: unicode(uuid4())
    )
    #: the OAuth client_secret
    client_secret = db.Column(
        db.String,
        nullable=False,
        default=lambda: unicode(uuid4())
    )
    #: the OAuth default scopes the application may request access to
    default_scopes = db.Column(
        ARRAY(db.String),
        nullable=False,
        default=['api']
    )
    #: the OAuth absolute URIs that a application may use to redirect to after authorization
    redirect_uris = db.Column(
        ARRAY(db.String),
        nullable=False,
        default=[]
    )
    #: whether the application is enabled or disabled
    is_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )
    #: whether the application can access user data without asking for permission
    is_trusted = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    @property
    def client_type(self):
        return 'public'

    @property
    def default_redirect_uri(self):
        if self.redirect_uris:
            return self.redirect_uris[0]
        return None

    @property
    def locator(self):
        return {'id': self.id}

    @return_ascii
    def __repr__(self):
        return '<OAuthApplication({}, {}, {})>'.format(self.id, self.name, self.client_id)

    def reset_client_secret(self):
        self.client_secret = unicode(uuid4())