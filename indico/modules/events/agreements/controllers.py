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

import os
from io import BytesIO

from flask import flash, jsonify, redirect, request, session
from werkzeug.exceptions import NotFound

from indico.core.errors import AccessError, NoReportError
from indico.modules.events.agreements.forms import AgreementForm, AgreementEmailForm, AgreementUploadForm
from indico.modules.events.agreements.models.agreements import Agreement
from indico.modules.events.agreements.notifications import notify_agreement_reminder, notify_new_signature_to_manager
from indico.modules.events.agreements.views import WPAgreementForm, WPAgreementManager
from indico.modules.events.agreements.util import get_agreement_definitions, send_new_agreements
from indico.util.i18n import _
from indico.web.flask.util import url_for, send_file
from indico.web.forms.base import FormDefaults
from MaKaC.webinterface.pages.base import WPJinjaMixin
from MaKaC.webinterface.rh.conferenceDisplay import RHConferenceBaseDisplay
from MaKaC.webinterface.rh.conferenceModif import RHConferenceModifBase


class RHAgreementForm(RHConferenceBaseDisplay):
    """Agreement form page"""

    def _checkParams(self, params):
        RHConferenceBaseDisplay._checkParams(self, params)
        self.agreement = Agreement.find_one(id=request.view_args['id'])

    def _checkSessionUser(self):
        if session.user is None:
            self._redirect(self._getLoginURL())
        if self.agreement.user != session.user:
            raise AccessError()

    def _checkProtection(self):
        RHConferenceBaseDisplay._checkProtection(self)
        if self.agreement.uuid != request.view_args['uuid']:
            raise AccessError()
        if self.agreement.user:
            self._checkSessionUser()

    def _process(self):
        form = AgreementForm()
        if form.validate_on_submit() and self.agreement.pending:
            self.agreement.signed_from_ip = request.remote_addr
            reason = form.reason.data if form.agreed.data else None
            func = self.agreement.accept if form.agreed.data else self.agreement.reject
            func(reason=reason)
            if self.agreement.definition.event_settings.get(self._conf, 'manager_notifications_enabled'):
                notify_new_signature_to_manager(self.agreement)
            return redirect(url_for('.agreement_form', self.agreement, uuid=self.agreement.uuid))
        html = self.agreement.render(form)
        return WPAgreementForm.render_string(html, self._conf)


class RHAgreementManager(RHConferenceModifBase):
    """Agreements types page (admin)"""

    def _process(self):
        definitions = get_agreement_definitions().values()
        return WPAgreementManager.render_template('event_agreements.html', self._conf,
                                                  event=self._conf, definitions=definitions)


class RHAgreementManagerDetails(RHConferenceModifBase):
    """Management page for all agreements of a certain type (admin)"""

    def _checkParams(self, params):
        RHConferenceModifBase._checkParams(self, params)
        definition_name = request.view_args['definition']
        self.definition = get_agreement_definitions().get(definition_name)
        if self.definition is None:
            raise NotFound("Agreement type '{}' does not exist".format(definition_name))

    def _process(self):
        event = self._conf
        agreements = Agreement.find_all(event_id=event.getId(), type=self.definition.name)
        return WPAgreementManager.render_template('event_agreements_details.html', event,
                                                  event=event, definition=self.definition, agreements=agreements)


class RHAgreementManagerDetailsToggleNotifications(RHAgreementManagerDetails):
    """Toggles notifications to managers for an agreement type on an event"""

    def _process(self):
        enabled = request.form['enabled'] == '1'
        self.definition.event_settings.set(self._conf, 'manager_notifications_enabled', enabled)
        return jsonify(success=True, enabled=enabled)


class RHAgreementManagerDetailsEmailBase(RHAgreementManagerDetails):
    dialog_template = None

    def _checkParams(self, params):
        self._doNotSanitizeFields.append('from_address')
        RHAgreementManagerDetails._checkParams(self, params)

    def _success_handler(self, form):
        raise NotImplementedError

    def _get_form(self):
        template = self.definition.get_email_body_template(self._conf)
        form_defaults = FormDefaults(body=template.get_html_body())
        return AgreementEmailForm(obj=form_defaults, definition=self.definition)

    def _process(self):
        event = self._conf
        form = self._get_form()
        if form.validate_on_submit():
            self._success_handler(form)
            return jsonify(success=True)
        return WPJinjaMixin.render_template(self.dialog_template, event=event, form=form, definition=self.definition)


class RHAgreementManagerDetailsSend(RHAgreementManagerDetailsEmailBase):
    dialog_template = 'events/agreements/agreement_email_form_send.html'

    def _get_people(self):
        identifiers = set(request.form.getlist('references'))
        return {k: v for k, v in self.definition.get_people_not_notified(self._conf).iteritems()
                if v.identifier in identifiers}

    def _success_handler(self, form):
        people = self._get_people()
        email_body = form.body.data
        send_new_agreements(self._conf, self.definition.name, people, email_body,
                            form.cc_addresses.data, form.from_address.data)


class RHAgreementManagerDetailsRemind(RHAgreementManagerDetailsEmailBase):
    dialog_template = 'events/agreements/agreement_email_form_remind.html'

    def _get_agreements(self):
        ids = set(request.form.getlist('references'))
        return Agreement.find_all(Agreement.id.in_(ids))

    def _success_handler(self, form):
        email_body = form.body.data
        agreements = self._get_agreements()
        for agreement in agreements:
            notify_agreement_reminder(agreement, email_body, form.cc_addresses.data, form.from_address.data)
        flash(_("Reminders sent"), 'success')


class RHAgreementManagerDetailsSendAll(RHAgreementManagerDetailsSend):
    dialog_template = 'events/agreements/agreement_email_form_send_all.html'

    def _get_people(self):
        return self.definition.get_people_not_notified(self._conf)


class RHAgreementManagerDetailsRemindAll(RHAgreementManagerDetailsRemind):
    dialog_template = 'events/agreements/agreement_email_form_remind_all.html'

    def _get_agreements(self):
        return Agreement.find_all(Agreement.pending, event_id=self._conf.getId(), type=self.definition.name)


class RHAgreementManagerDetailsAgreementBase(RHAgreementManagerDetails):
    def _checkParams(self, params):
        RHAgreementManagerDetails._checkParams(self, params)
        self.agreement = Agreement.find_one(id=request.view_args['id'])
        if self._conf != self.agreement.event:
            raise NotFound


class RHAgreementManagerDetailsUploadAgreement(RHAgreementManagerDetailsAgreementBase):
    def _checkParams(self, params):
        RHAgreementManagerDetailsAgreementBase._checkParams(self, params)
        if not self.agreement.pending:
            raise NoReportError("The agreement is already signed")

    def _process(self):
        event = self._conf
        agreement = self.agreement
        form = AgreementUploadForm()
        if form.validate_on_submit():
            func = agreement.accept if form.answer.data else agreement.reject
            func(on_behalf=True)
            agreement.attachment_filename = form.document.data.filename
            agreement.attachment = form.document.data.read()
            flash(_("Agreement uploaded on behalf of {0}".format(agreement.person_name)), 'success')
            return jsonify(success=True)
        return WPJinjaMixin.render_template('events/agreements/agreement_upload_form.html', form=form,
                                            event=event, agreement=agreement)


class RHAgreementManagerDetailsDownloadAgreement(RHAgreementManagerDetailsAgreementBase):
    def _checkParams(self, params):
        RHAgreementManagerDetailsAgreementBase._checkParams(self, params)
        if not self.agreement.signed_on_behalf:
            raise NoReportError("The agreement was not signed via file upload")

    def _process(self):
        io = BytesIO(self.agreement.attachment)
        file_ext = os.path.splitext(self.agreement.attachment_filename)[1]
        return send_file(self.agreement.attachment_filename, io, file_ext)