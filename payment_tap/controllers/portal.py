# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

from odoo import http
from odoo.addons.payment.controllers import portal as payment_portal


class CustomerPortal(payment_portal.PaymentPortal):
    @http.route()
    def payment_method(self, **kwargs):
        response = super().payment_method(**kwargs)
        if response.qcontext.get('payment_methods_sudo'):
            response.qcontext['payment_methods_sudo'] = response.qcontext['payment_methods_sudo'].filtered(lambda x: not x.code)
        return response
