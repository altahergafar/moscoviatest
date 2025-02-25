# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

import base64
import logging
import json
import pprint
import requests
from werkzeug import urls

from odoo import _, api, fields, models
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_tap.controllers.main import TapController
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import get_lang


_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    tap_payment_method = fields.Char('Tap Payment Method')
    is_tap_refund = fields.Boolean('Tap Refund')

    def _tap_create_charges(self, values):
        base_url = self.provider_id.get_base_url()
        partner_first_name, partner_last_name = payment_utils.split_partner_name(self.partner_name)
        payload = {
            "amount": values.get('amount', 0.0),
            "currency": self.currency_id.name,
            "threeDSecure": self.provider_id.tap_use_3d_secure,
            "save_card": True if self.operation == 'online_redirect' and self.tokenize else False,
            "description": '%s: %s' % (self.company_id.name, values['reference']),
            "statement_descriptor": '%s: %s' % (self.company_id.name, values['reference']),
            "reference": {
                "transaction": values['reference'],
                "order": values['reference']
            },
            "customer": {
                "first_name": partner_first_name,
                "last_name": partner_last_name,
                "email": self.partner_email,
                "phone": {
                    "country_code": self.partner_country_id.code or "965",
                    "number": self.partner_phone
                }
            },
            "source": {"id": self.provider_id.tap_payment_options},
            "redirect": {"url": urls.url_join(base_url, TapController._return_url + '?provider_id=%d' % self.provider_id.id)}
        }
        headers = {
            'authorization': "Bearer %s" % self.provider_id.tap_secret_key,
            'content-type': "application/json",
            'lang_code': get_lang(self.env, self.partner_lang).iso_code
        }
        response = requests.post("https://api.tap.company/v2/charges", data=json.dumps(payload), headers=headers)
        return response.json()

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Tap-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'tap':
            return res

        res = self._tap_create_charges(processing_values)
        error_msg = ''
        if res.get('errors'):
            error_msg += '\n'.join(error.get('code') + ' - ' + error.get('description') for error in res.get('errors'))
        if error_msg != '':
            raise ValidationError(error_msg)
        url = res.get('transaction').get('url')

        processing_values.update({
            'form_url': '/payment/tap/redirect?redirect_url=%s' % base64.b64encode(url.encode()).decode(),
        })
        return processing_values

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of payment to find the transaction based on Tap data.

        :param str provider_code: The code of the provider that handled the transaction
        :param dict notification_data: The notification data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if inconsistent data were received
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'tap' or len(tx) == 1:
            return tx

        reference = notification_data.get('reference').get('transaction')
        if notification_data.get('object') == 'refund':
            reference = notification_data.get('reference').get('merchant')
        if not reference:
            raise ValidationError(
                "Tap: " + _(
                    "Received data with missing reference %(r)s.", r=reference
                )
            )

        tx = self.search([('reference', '=', reference), ('provider_code', '=', provider_code)])
        if notification_data.get('object') == 'refund' and (not tx or tx.operation != 'refund'):
            # If a refund is initiated from Tap, the merchant reference can be personalized. We
            # need to get the source transaction and manually create the refund transaction.
            source_provider_reference = notification_data.get('originalReference')
            source_tx = self.search(
                [('provider_reference', '=', source_provider_reference), ('provider_code', '=', 'tap')]
            )
            tx = self._tap_create_refund_tx_from_feedback_data(source_tx, notification_data)

        if not tx:
            raise ValidationError(
                "Tap: " + _("No transaction found matching reference %s.", reference)
            )

        return tx

    def _tap_create_refund_tx_from_feedback_data(self, source_tx, data):
        """ Create a refund transaction based on Tap data.

        :param recordset source_tx: The source transaction for which a refund is initiated, as a
                                    `payment.transaction` recordset
        :param dict data: The feedback data sent by the provider
        :return: The created refund transaction
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if inconsistent data were received
        """
        refund_provider_reference = data.get('id')
        amount_to_refund = data.get('amount')
        if not refund_provider_reference or not amount_to_refund:
            raise ValidationError(
                "Tap: " + _("Received refund data with missing transaction values")
            )

        return source_tx._create_refund_transaction(
            amount_to_refund=amount_to_refund, provider_reference=refund_provider_reference, is_tap_refund=True
        )

    def _process_notification_data(self, notification_data):
        """ Override of `payment' to process the transaction based on Tap data.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider.
        :return: None
        :raise ValidationError: If inconsistent data are received.
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'tap':
            return

        if notification_data.get('object') == 'refund':
            if float_compare(float(-notification_data.get('amount', '0.0')), (self.amount), 2) != 0:
                # amount + fees
                logging_values = {
                    'amount': -notification_data.get('amount', '0.0'),
                    'total': self.amount,
                    'reference': self.reference,
                }
                _logger.error(
                    "the paid amount (%(amount)s) does not match the total %(total)s for the transaction with reference %(reference)s", logging_values
                )
                raise ValidationError("Tap: " + _("The amount does not match the total."))
        else:
            if float_compare(float(notification_data.get('amount', '0.0')), (self.amount), 2) != 0:
                # amount + fees
                logging_values = {
                    'amount': notification_data.get('amount', '0.0'),
                    'total': self.amount,
                    'reference': self.reference,
                }
                _logger.error(
                    "the paid amount (%(amount)s) does not match the total %(total)s for the transaction with reference %(reference)s", logging_values
                )
                raise ValidationError("Tap: " + _("The amount does not match the total."))
        if notification_data.get('currency') != self.currency_id.name:
            raise ValidationError(
                "Tap: " + _(
                    "The currency returned by Tap %(rc)s does not match the transaction "
                    "currency %(tc)s.", rc=notification_data.get('currency'), tc=self.currency_id.name
                )
            )
        status = notification_data.get('response').get('code')
        self.write({
            'provider_reference': notification_data.get('id'),
        })
        if notification_data.get('source'):
            if notification_data['source'].get('payment_method'):
                self.write({'tap_payment_method': notification_data['source']['payment_method']})
        if status == '000':
            if self.tokenize:
                if notification_data.get('card') and notification_data.get('save_card'):
                    self._tap_tokenize_from_feedback_data(notification_data)
            _logger.info('Tap payment for tx %s: set as DONE' % (self.reference))
            self._set_done()
        elif status == '001':
            self._set_authorized()
        elif status in ['100', '200']:
            self._set_pending()
        elif status in ['301', '302']:
            _logger.info('Tap payment for tx %s: set as CANCELLED' % (self.reference))
            self._set_canceled()
        else:
            erro_msg = notification_data.get('response').get('message')
            _logger.info(
                "received invalid transaction status for transaction with reference %s: %s",
                self.reference, status
            )
            self._set_error("Tap: " + _("received invalid transaction status: %s", erro_msg))

    def _tap_create_refund(self, amount, currency, reference):
        provider = self.provider_id
        headers = {
            'authorization': "Bearer %s" % provider.tap_secret_key,
            'content-type': "application/json",
            'lang_code': get_lang(self.env, self.partner_id.lang).iso_code
        }
        url = "https://api.tap.company/v2/refunds"
        payload = {
            "charge_id": self.provider_reference,
            "amount": amount,
            "currency": currency,
            "description": reference,
            "reason": "requested_by_customer",
            "reference": {
                "merchant": reference
            },
            "metadata": {
                "udf1": self.id,
                "udf2": provider.id
            }
        }
        response = requests.request("POST", url, data=json.dumps(payload), headers=headers)
        result = response.json()
        return result

    def _send_refund_request(self, amount_to_refund=None):
        """ Override of payment to send a refund request to Tap.

        Note: self.ensure_one()

        :param float amount_to_refund: The amount to refund
        :param bool create_refund_transaction: Whether a refund transaction should be created or not
        :return: The refund transaction if any
        :rtype: recordset of `payment.transaction`
        """
        if self.provider_code != 'tap':
            return super()._send_refund_request(
                amount_to_refund=amount_to_refund
            )
        refund_tx = super()._send_refund_request(
            amount_to_refund=amount_to_refund
        )
        refund_tx.is_tap_refund = True

        # Make the refund request to Tap
        converted_amount = -refund_tx.amount  # The amount is negative for refund transactions

        response_content = self._tap_create_refund(converted_amount, refund_tx.currency_id.name, refund_tx.reference)
        _logger.info(
            "Response of tap refund request for transaction with reference %s:\n%s",
            self.reference, pprint.pformat(response_content)
        )

        if response_content.get('errors'):
            raise UserError(", ".join(err.get('description') for err in response_content['errors']))

        # Handle the refund request response
        reference = response_content.get('id')
        status = response_content.get('response').get('code')
        if reference and status in ['000', '100', '200']:
            refund_tx.provider_reference = reference
        response_content.update(entity_type='refund')
        refund_tx._handle_notification_data('tap', response_content)
        return refund_tx

    @api.model
    def cron_get_refund_status_and_process(self):
        txs = self.search([('provider_code', '=', 'tap'), ('is_tap_refund', '=', True), ('state', 'in', ['draft', 'pending'])])
        for tx in txs:
            headers = {
                'authorization': "Bearer %s" % tx.provider_id.tap_secret_key,
                'content-type': "application/json",
            }
            response = requests.request("GET", "https://api.tap.company/v2/refunds/%s" % tx.provider_reference, headers=headers)
            res = response.json()
            tx.sudo()._handle_notification_data('tap', res)

    # --------------------------------------------------
    # TOKENIZE METHODS
    # --------------------------------------------------
    def _tap_requests(self, payload, endpoint):
        url = "https://api.tap.company"
        headers = {
            'authorization': "Bearer %s" % self.provider_id.tap_secret_key,
            'content-type': "application/json",
            'lang_code': get_lang(self.env, self.partner_id.lang).iso_code
        }
        response = requests.request("POST", url + endpoint, data=json.dumps(payload), headers=headers)
        res = response.json()
        if response.status_code != 200:
            errors = res.get('errors')
            error_msg = ', '.join(e.get('description') for e in errors)
            raise ValidationError(error_msg)
        return res

    def _send_payment_request(self):
        """ Override of payment to send a payment request to Tap.

        Note: self.ensure_one()

        :return: None
        :raise: UserError if the transaction is not linked to a token
        """
        super()._send_payment_request()
        if self.provider_code != 'tap':
            return

        if not self.token_id:
            raise UserError("Tap: " + _("The transaction is not linked to a token."))

        base_url = self.provider_id.get_base_url()
        # Make the payment request
        saved_card_token_payload = {
            "saved_card": {
                "card_id": self.token_id.provider_ref,
                "customer_id": self.token_id.tap_customer_id
            }
        }
        save_card_token_resp = self._tap_requests(saved_card_token_payload, "/v2/tokens")

        save_card_payload = {
            "source": save_card_token_resp.get('id')
        }
        self._tap_requests(save_card_payload, "/v2/card/%s" % self.token_id.tap_customer_id)

        headers = {
            'authorization': "Bearer %s" % self.provider_id.tap_secret_key,
            'content-type': "application/json",
            'lang_code': get_lang(self.env, self.partner_id.lang).iso_code
        }
        url = "https://api.tap.company/v2/charges"
        payload = {
            "amount": self.amount,
            "currency": self.currency_id.name,
            "threeDSecure": self.provider_id.tap_use_3d_secure,
            "save_card": False,
            "description": self.reference,
            "statement_descriptor": self.reference,
            "reference": {
                "transaction": self.reference,
                "order": self.reference
            },
            "receipt": {
                "email": False,
                "sms": False
            },
            "customer": {
                "id": self.token_id.tap_customer_id
            },
            "source": {"id": save_card_token_resp.get('id')},
            "redirect": {"url": urls.url_join(base_url, TapController._return_url)}
        }

        res = requests.request("POST", url, data=json.dumps(payload), headers=headers)
        response_content = json.loads(res.text)

        _logger.info("entering _handle_notification_data with data:\n%s", pprint.pformat(response_content))
        self._handle_notification_data('tap', response_content)

    def _tap_tokenize_from_feedback_data(self, data):
        """ Create a token from feedback data.

        :param dict data: The feedback data sent by the provider
        :return: None
        """
        token = self.env['payment.token'].create({
            'provider_id': self.provider_id.id,
            'payment_method_id': self.payment_method_id.id,
            'payment_details': data['card']['last_four'],
            'partner_id': self.partner_id.id,
            'provider_ref': data['card']['id'],
            'tap_customer_id': data['customer']['id']
        })
        self.write({
            'token_id': token.id,
            'tokenize': False,
        })
        _logger.info(
            "created token with id %s for partner with id %s", token.id, self.partner_id.id
        )
