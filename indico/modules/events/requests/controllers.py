# This file is part of Indico.
# Copyright (C) 2002 - 2016 European Organization for Nuclear Research (CERN).
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

from flask import request, flash, redirect, session
from werkzeug.exceptions import NotFound, BadRequest, Forbidden

from indico.modules.events.requests import get_request_definitions
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.modules.events.requests.util import is_request_manager
from indico.modules.events.requests.views import WPRequestsEventManagement
from indico.util.i18n import _
from indico.web.flask.util import url_for
from MaKaC.webinterface.rh.conferenceModif import RHConferenceModifBase


class EventOrRequestManagerMixin:
    def _checkProtection(self):
        self.protection_overridden = False
        if hasattr(self, 'definition'):
            # check if user can manage *that* request
            can_manage_request = session.user and self.definition and self.definition.can_be_managed(session.user)
        else:
            # check if user can manage any request
            can_manage_request = session.user and is_request_manager(session.user)
        can_manage_event = self.event_new.can_manage(session.user, allow_key=True)
        self.protection_overridden = can_manage_request and not can_manage_event
        if not can_manage_request and not can_manage_event:
            RHConferenceModifBase._checkProtection(self)


class RHRequestsEventRequests(EventOrRequestManagerMixin, RHConferenceModifBase):
    """Overview of existing requests (event)"""

    CSRF_ENABLED = True

    def _process(self):
        definitions = get_request_definitions()
        if not definitions:
            raise NotFound
        requests = Request.find_latest_for_event(self.event_new)
        if self.protection_overridden:
            definitions = {name: def_ for name, def_ in definitions.iteritems() if def_.can_be_managed(session.user)}
            requests = {name: req for name, req in requests.iteritems()
                        if req.definition and req.definition.can_be_managed(session.user)}
        return WPRequestsEventManagement.render_template('event_requests.html', self._conf, event=self.event_new,
                                                         definitions=definitions, requests=requests)


class RHRequestsEventRequestBase(RHConferenceModifBase):
    """Base class for pages handling a specific request type"""

    CSRF_ENABLED = True

    #: if a request must be present in the database
    _require_request = True

    def _checkParams(self, params):
        RHConferenceModifBase._checkParams(self, params)
        try:
            self.definition = get_request_definitions()[request.view_args['type']]
        except KeyError:
            raise NotFound
        self.request = Request.find_latest_for_event(self.event_new, self.definition.name)
        if self._require_request and not self.request:
            raise NotFound


class RHRequestsEventRequestDetailsBase(EventOrRequestManagerMixin, RHRequestsEventRequestBase):
    """Base class for the details/edit/manage views of a specific request"""

    def _process(self):
        self.is_manager = self.definition.can_be_managed(session.user)
        self.form = self.definition.create_form(self.event_new, self.request)
        self.manager_form = None
        if self.request and self.is_manager:
            self.manager_form = self.definition.create_manager_form(self.request)
            if self.request.state not in {RequestState.accepted, RequestState.rejected}:
                del self.manager_form.action_save
            if self.request.state == RequestState.accepted:
                del self.manager_form.action_accept
            if self.request.state == RequestState.rejected:
                del self.manager_form.action_reject

        rv = self.process_form()
        if rv:
            return rv

        form_html = self.definition.render_form(event=self.event_new, definition=self.definition, req=self.request,
                                                form=self.form, manager_form=self.manager_form,
                                                is_manager=self.is_manager)
        return WPRequestsEventManagement.render_string(form_html, self._conf)

    def process_form(self):
        raise NotImplementedError


class RHRequestsEventRequestDetails(RHRequestsEventRequestDetailsBase):
    """Details/form for a specific request"""

    _require_request = False

    def process_form(self):
        form = self.form
        if not form.validate_on_submit():
            return
        if not self.request or not self.request.can_be_modified:
            req = Request(event_new=self.event_new, definition=self.definition, created_by_user=session.user)
            new = True
        else:
            req = self.request
            new = False
        self.definition.send(req, form.data)
        if new:
            flash_msg = _("Your request ({0}) has been sent. "
                          "You will be notified by e-mail once it has been accepted or rejected.")
        else:
            flash_msg = _("Your request ({0}) has been modified.")
        flash(flash_msg.format(self.definition.title), 'success')
        if self.is_manager:
            return redirect(url_for('.event_requests_details', self.event_new, type=self.definition.name))
        else:
            return redirect(url_for('.event_requests', self.event_new))


class RHRequestsEventRequestProcess(RHRequestsEventRequestDetailsBase):
    """Accept/Reject a request"""

    def _checkProtection(self):
        self._checkSessionUser()
        if not self.definition.can_be_managed(session.user):
            raise Forbidden

    def process_form(self):
        form = self.manager_form
        if self.request.state == RequestState.withdrawn:
            return
        elif not form.validate_on_submit():
            # very unlikely, unless the definition uses a custom form
            return
        if 'action_accept' in form and form.action_accept.data:
            action = 'accept'
        elif 'action_reject' in form and form.action_reject.data:
            action = 'reject'
        elif 'action_save' in form and form.action_save.data:
            action = 'save'
        else:
            # This happens when the request was already processed, e.g. in another
            # tab or if you simply click the submit button twice.  No nee to fail;
            # just don't do anything.
            return redirect(url_for('.event_requests_details', self.request))
        if action == 'accept':
            self.definition.accept(self.request, self.manager_form.data, session.user)
            flash(_('You have accepted this request.'), 'info')
        elif action == 'reject':
            self.definition.reject(self.request, self.manager_form.data, session.user)
            flash(_('You have rejected this request.'), 'info')
        elif action == 'save':
            self.definition.manager_save(self.request, self.manager_form.data)
            flash(_("You have updated the request (only management-specific data)."), 'info')
        return redirect(url_for('.event_requests_details', self.request))


class RHRequestsEventRequestWithdraw(EventOrRequestManagerMixin, RHRequestsEventRequestBase):
    """Withdraw a request"""

    def _process(self):
        if self.request.state not in {RequestState.pending, RequestState.accepted}:
            raise BadRequest
        self.definition.withdraw(self.request)
        flash(_('You have withdrawn your request ({0})').format(self.definition.title))
        return redirect(url_for('.event_requests', self.event_new))
