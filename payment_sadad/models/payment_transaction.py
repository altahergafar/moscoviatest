# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import hashlib
import random
import json
import base64
import string
from datetime import datetime
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from werkzeug import urls
from odoo.http import request
from odoo import api, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_repr
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_sadad.controllers.main import SadadController

_logger = logging.getLogger(__name__)
IV = "@@@@&&&&####$$$$"
BLOCK_SIZE = 16


def pad(data):
    pad_len = BLOCK_SIZE - len(data) % BLOCK_SIZE
    return data + (chr(pad_len) * pad_len).encode('utf-8')


def unpad(data):
    pad_len = data[-1]
    return data[:-pad_len]


class AESCipher:
    def __init__(self, key):
        self.key = key

    def encode(self, to_encode, iv):
        to_encode = pad(to_encode.encode('utf-8'))
        cipher = Cipher(algorithms.AES(self.key.encode('utf-8')), modes.CBC(iv.encode('utf-8')),
                        backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(to_encode) + encryptor.finalize()
        return base64.b64encode(encrypted).decode('utf-8')

    def decode(self, to_decode, iv):
        to_decode = base64.b64decode(to_decode.encode('utf-8'))
        cipher = Cipher(algorithms.AES(self.key.encode('utf-8')), modes.CBC(iv.encode('utf-8')),
                        backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(to_decode) + decryptor.finalize()
        return unpad(decrypted).decode('utf-8')


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    @api.model
    def _compute_reference(self, provider, prefix=None, separator='-', **kwargs):
        if provider == 'sadad':
            if not prefix:
                prefix = self.sudo()._compute_reference_prefix(provider, separator, **kwargs) or None
            prefix = payment_utils.singularize_reference_prefix(prefix=prefix, separator=separator)
        return super()._compute_reference(provider, prefix=prefix, separator=separator, **kwargs)

    def generate_checksum(self, param_dict, merchant_key, salt=None):
        salt = salt if salt else self._id_generator(4)
        final_string = param_dict + '|' + salt
        hasher = hashlib.sha256(final_string.encode())
        hash_string = hasher.hexdigest() + salt
        return self._encode(hash_string, IV, self.provider_id.sadad_api_key)

    def return_checksum(self, param_dict, merchant_key, flags):
        salt = "AAAA"
        final_string = param_dict + '|' + salt
        hasher = hashlib.sha256(final_string.encode())
        hash_string = hasher.hexdigest() + salt
        return flags

    def _id_generator(self, size=6, chars=string.ascii_uppercase + string.digits + string.ascii_lowercase):
        return ''.join(random.choice(chars) for _ in range(size))

    def _encode(self, to_encode, iv, key):
        aes = AESCipher(key)
        return aes.encode(to_encode, iv)

    def _decode(self, to_decode, iv, key):
        aes = AESCipher(key)
        return aes.decode(to_decode, iv)

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Sadad-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of acquirer-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'sadad':
            return res
        lang = 'Arb'
        if self.partner_lang == 'en_US':
            lang = 'ENG'
        number = quantity = amount = 0
        itemname = type = ''
        print("sale_order_ids", self.sale_order_ids, processing_values)
        if self.sale_order_ids:
            order_id = str(self.sale_order_ids[0].id)
            sale_order_id = request.session.get('sale_order_id')
            sale_order = request.env['sale.order'].sudo().browse(sale_order_id)
            print("order_id", self.amount)
            for line in sale_order.order_line:
                if line.price_unit:
                    number += 1
                    itemname += f"Item {number}:{line.product_id.display_name} Quantity:{line.product_uom_qty} Price Unit:{line.price_unit} #"
                    quantity = 1
                    type = line.product_id.detailed_type
                    amount += line.product_uom_qty * line.price_unit
            if itemname:
                itemname = itemname[:-1]
            if number == 1:
                for line in sale_order.order_line:
                    if line.price_unit:
                        itemname = line.product_id.display_name
                        quantity = str(int(line.product_uom_qty))
                        amount = str(int(line.price_unit))

            dt_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("date and time =", dt_string)

            callback_url = urls.url_join(self.provider_id.base_url, SadadController._return_url)

            # Converting price based on pricelist
            if sale_order.pricelist_id.currency_id.id != self.env.ref("base.QAR").id:
                current_amount = float_repr(processing_values['amount'], self.currency_id.decimal_places or 2)
                company = self.provider_id.company_id if self.provider_id.company_id else sale_order.company_id
                new_price = sale_order.pricelist_id.currency_id._convert(float(current_amount), company.currency_id, company)
                new_price = float_repr(new_price, company.currency_id.decimal_places or 2)
            else:
                new_price = str(float_repr(processing_values['amount'], self.currency_id.decimal_places or 2))

            sadad_values = {"postData": {
                'merchant_id': self.provider_id.sadad_merchant_id,
                # 'ORDER_ID': str(self.sale_order_ids[0].id),
                'ORDER_ID': self.reference.replace('-', 'aa0').replace("/", 'aa1'),
                'WEBSITE': self.provider_id.sadad_domain,
                'TXN_AMOUNT': str(new_price),
                'CUST_ID': self.partner_email,
                'EMAIL': self.partner_email,
                'MOBILE_NO':self.partner_phone,
                # 'MOBILE_NO': '21458742',
                'SADAD_WEBCHECKOUT_PAGE_LANGUAGE': lang,
                'CALLBACK_URL': callback_url,  # \/\/
                'txnDate': dt_string,
                'productdetail': [{
                    'order_id': order_id,
                    'itemname': itemname,
                    'amount': str(new_price),
                    'quantity': '1',
                    'type': type
                }]
            }, "secretKey": self.provider_id.sadad_api_key}
            # _logger.info('###########'+str(sadad_values['postData']['productdetail']))
            datas = json.dumps(sadad_values, separators=(',', ':'))
            datas = datas.replace("/", "\\/")

            checksum = self.generate_checksum(datas,
                                              self.provider_id.sadad_api_key)  # + self.provider_id.sadad_merchant_id

            if self.provider_id.state != 'enabled':
                sadad_values['test'] = 1
            return {
                'merchant_id': self.provider_id.sadad_merchant_id,
                # 'ORDER_ID': str(self.sale_order_ids[0].id),
                'ORDER_ID': self.reference.replace('-', 'aa0').replace("/", 'aa1'),
                'WEBSITE': self.provider_id.sadad_domain,
                'TXN_AMOUNT': str(new_price),
                'CUST_ID': self.partner_email,
                'EMAIL': self.partner_email,
                'MOBILE_NO':self.partner_phone,
                # 'MOBILE_NO': '21458742',
                'SADAD_WEBCHECKOUT_PAGE_LANGUAGE': lang,
                'txnDate': dt_string,
                'CALLBACK_URL': callback_url,

                'order_id': order_id,
                'itemname': itemname,
                'amount': str(new_price),
                'quantity': '1',
                'type': type,
                'checksum': checksum,
            }
        elif self.invoice_ids:
            invoice_id = self.invoice_ids[0]
            # sale_order = request.env['account.move'].sudo().browse(sale_order_id)

            print("order_id", self.amount)
            for line in invoice_id.invoice_line_ids:
                if line.price_unit:
                    number += 1
                    itemname += f"Item {number}:{line.product_id.display_name} Quantity:{line.quantity} Price Unit:{line.price_unit} #"
                    quantity = 1
                    type = line.product_id.detailed_type
                    amount += line.quantity * line.price_unit
            if itemname:
                itemname = itemname[:-1]
            if number == 1:
                for line in invoice_id.invoice_line_ids:
                    if line.price_unit:
                        itemname = line.product_id.display_name
                        quantity = str(int(line.quantity))
                        amount = str(int(line.price_unit))

            dt_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("date and time =", dt_string)

            callback_url = urls.url_join(self.provider_id.base_url, SadadController._return_url)

            # Converting price based on pricelist
            if invoice_id.currency_id.id != self.env.ref("base.QAR").id:
                current_amount = float_repr(processing_values['amount'], self.currency_id.decimal_places or 2)
                company = self.provider_id.company_id if self.provider_id.company_id else invoice_id.company_id
                new_price = invoice_id.currency_id._convert(float(current_amount), company.currency_id, company)
                new_price = float_repr(new_price, company.currency_id.decimal_places or 2)

            else:
                new_price = str(float_repr(processing_values['amount'], self.currency_id.decimal_places or 2))

            sadad_values = {"postData": {
                'merchant_id': self.provider_id.sadad_merchant_id,
                # 'ORDER_ID': str(self.sale_order_ids[0].id),
                'ORDER_ID': self.reference.replace('-', 'aa0').replace("/", 'aa1'),
                'WEBSITE': self.provider_id.sadad_domain,
                'TXN_AMOUNT': str(new_price),
                'CUST_ID': self.partner_email,
                'EMAIL': self.partner_email,
                'MOBILE_NO':self.partner_phone,
                # 'MOBILE_NO': '21458742',
                'SADAD_WEBCHECKOUT_PAGE_LANGUAGE': lang,
                'CALLBACK_URL': callback_url,  # \/\/
                'txnDate': dt_string,
                'productdetail': [{
                    'order_id': str(invoice_id.id),
                    'itemname': itemname,
                    'amount': str(new_price),
                    'quantity': '1',
                    'type': type
                }]
            }, "secretKey": self.provider_id.sadad_api_key}
            # _logger.info('###########'+str(sadad_values['postData']['productdetail']))
            datas = json.dumps(sadad_values, separators=(',', ':'))
            datas = datas.replace("/", "\\/")

            checksum = self.generate_checksum(datas,
                                              self.provider_id.sadad_api_key)  # + self.provider_id.sadad_merchant_id

            if self.provider_id.state != 'enabled':
                sadad_values['test'] = 1
            return {
                'merchant_id': self.provider_id.sadad_merchant_id,
                # 'ORDER_ID': str(self.sale_order_ids[0].id),
                'ORDER_ID': self.reference.replace('-', 'aa0').replace("/", 'aa1'),
                'WEBSITE': self.provider_id.sadad_domain,
                'TXN_AMOUNT': str(new_price),
                'CUST_ID': self.partner_email,
                'EMAIL': self.partner_email,
                'MOBILE_NO':self.partner_phone,
                # 'MOBILE_NO': '21458742',
                'SADAD_WEBCHECKOUT_PAGE_LANGUAGE': lang,
                'txnDate': dt_string,
                'CALLBACK_URL': callback_url,

                'order_id': str(invoice_id.id),
                'itemname': itemname,
                'amount': str(new_price),
                'quantity': '1',
                'type': type,
                'checksum': checksum,
            }

    def _convert_price(self, processing_values, sale_order):
        if sale_order.pricelist_id.currency_id.id != self.env.ref("base.QAR").id:
            current_amount = float_repr(processing_values['amount'], self.currency_id.decimal_places or 2)
            company = self.provider_id.company_id if self.provider_id.company_id else sale_order.company_id
            new_price = sale_order.pricelist_id.currency_id._convert(float(current_amount), company.currency_id,
                                                                     company)
            return float_repr(new_price, company.currency_id.decimal_places or 2)
        else:
            return str(float_repr(processing_values['amount'], self.currency_id.decimal_places or 2))

    def _process_invoice(self, processing_values, callback_url, dt_string):
        invoice_id = self.invoice_ids[0]
        number = amount = 0
        itemname = type = ''
        for line in invoice_id.invoice_line_ids:
            if line.price_unit:
                number += 1
                itemname += f"Item {number}:{line.product_id.display_name} Quantity:{line.quantity} Price Unit:{line.price_unit} #"
                type = line.product_id.detailed_type
                amount += line.quantity * line.price_unit

        itemname = itemname[:-1] if itemname else itemname
        if number == 1:
            line = invoice_id.invoice_line_ids[0]
            itemname = line.product_id.display_name
            quantity = str(int(line.quantity))
            amount = str(int(line.price_unit))

        new_price = self._convert_price(processing_values, invoice_id)

        sadad_values = {
            "postData": {
                'merchant_id': self.provider_id.sadad_merchant_id,
                'ORDER_ID': self.reference.replace('-', 'aa0').replace("/", 'aa1'),
                'WEBSITE': self.provider_id.sadad_domain,
                'TXN_AMOUNT': str(new_price),
                'CUST_ID': self.partner_email,
                'EMAIL': self.partner_email,
                'MOBILE_NO': self.partner_phone,
                'SADAD_WEBCHECKOUT_PAGE_LANGUAGE': 'ENG' if self.partner_lang == 'en_US' else 'Arb',
                'CALLBACK_URL': callback_url,
                'txnDate': dt_string,
                'productdetail': [{
                    'order_id': str(invoice_id.id),
                    'itemname': itemname,
                    'amount': str(new_price),
                    'quantity': '1',
                    'type': type
                }]
            },
            "secretKey": self.provider_id.sadad_api_key
        }

        datas = json.dumps(sadad_values, separators=(',', ':')).replace("/", "\\/")
        checksum = self.generate_checksum(datas, self.provider_id.sadad_api_key)
        if self.provider_id.state != 'enabled':
            sadad_values['test'] = 1

        return {
            **sadad_values["postData"],
            'checksum': checksum,
        }


    @api.model
    def _get_tx_from_notification_data(self, provider, data):
        """ Override of payment to find the transaction based on Sadad data.

        :param str provider: The provider of the acquirer that handled the transaction
        :param dict data: The notification data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if inconsistent data were received
        :raise: ValidationError if the data match no transaction
        :raise: ValidationError if the signature can not be verified
        """
        tx = super()._get_tx_from_notification_data(provider, data)
        if provider != 'sadad':
            return tx
        reference = data.get('ORDERID').replace('aa0', '-').replace('aa1', '/')

        if not reference:
            raise ValidationError(
                "sadad: " + _(
                    "Received data with missing reference (%(ref)s).",
                    ref=reference
                )
            )

        # tx = self.search([('sale_order_ids.id', '=', order_id), ('provider', '=', 'sadad')],limit=1)
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'sadad')])
        if not tx:
            raise ValidationError(
                "sadad: " + _("No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_notification_data(self, data):
        super()._process_notification_data(data)
        if self.provider_code != 'sadad':
            return

        self.provider_reference = data.get('transaction_number')
        response_code = data.get('RESPCODE')

        if response_code == '400':
            self._set_pending(state_message="Transaction Pending")
        elif response_code == '1':
            self._set_done(state_message="Transaction Success")
        elif response_code == '402':
            self._set_pending(state_message="Transaction pending confirmation from bank")
        elif response_code == '810':
            self._set_canceled(state_message="Transaction failed.")
        else:
            _logger.warning("Received unrecognized payment state %s for transaction with reference %s", response_code,
                            self.reference)
            self._set_error("sadad: " + _("Invalid payment status."))
