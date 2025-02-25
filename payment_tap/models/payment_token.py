# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

from odoo import fields, models


class PaymentTokenTap(models.Model):
    _inherit = 'payment.token'

    tap_customer_id = fields.Char('Customer ID')
