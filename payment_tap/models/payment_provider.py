# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

from odoo import fields, models


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('tap', 'Tap')],
        ondelete={'tap': 'set default'}
    )
    tap_publishable_key = fields.Char(
        string='Publishable Key',
        required_if_provider='tap'
    )
    tap_secret_key = fields.Char(
        string='Secret Key',
        required_if_provider='tap'
    )
    tap_payment_options = fields.Selection([
        ('src_all', 'All'), ('src_card', 'Card Payment'), ('src_kw.knet', 'KNET'), ('src_bh.benefit', 'BENEFIT'),
        ('src_sa.mada', 'MADA'), ('src_om.omannet', 'Oman Net'), ('src_apple_pay', 'Apple Pay')],
        string='Payment Options',
        required_if_provider='tap',
        default="src_all"
    )
    tap_use_3d_secure = fields.Boolean(
        string='Use 3D Secure'
    )

    def write(self, vals):
        res = super().write(vals)
        method = vals.get('tap_payment_options')
        if method:
            for rec in self:
                rec._compute_available_currency_ids()
        return res

    def _get_supported_currencies(self):
        """ Override of `payment` to return the supported currencies. """
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'tap':
            if self.tap_payment_options == 'src_card':
                supported_currencies = supported_currencies.filtered(
                    lambda c: c.name in ["AED", "BHD", "EGP", "EUR", "GBP", "KWD", "OMR", "QAR", "SAR", "USD"]
                )
            elif self.tap_payment_options == 'src_kw.knet':
                supported_currencies = supported_currencies.filtered(
                    lambda c: c.name == "KWD"
                )
            elif self.tap_payment_options == 'src_bh.benefit':
                supported_currencies = supported_currencies.filtered(
                    lambda c: c.name == "BHD"
                )
            elif self.tap_payment_options == 'src_sa.mada':
                supported_currencies = supported_currencies.filtered(
                    lambda c: c.name == "SAR"
                )
            elif self.tap_payment_options == 'src_om.omannet':
                supported_currencies = supported_currencies.filtered(
                    lambda c: c.name == "OMR"
                )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'tap':
            return default_codes
        return ['tap']

    def _compute_feature_support_fields(self):
        """ Override of `payment` to enable additional features. """
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'tap').update({
            'support_refund': 'partial'
        })
        self.filtered(lambda p: p.code == 'tap' and p.tap_payment_options == 'src_card').update({
            'support_tokenization': True
        })
        self.filtered(lambda p: p.code == 'tap' and p.tap_payment_options != 'src_card').update({
            'support_tokenization': False,
            'allow_tokenization': False
        })
