# Part of Odoo. See LICENSE file for full copyright and licensing details.

from hashlib import md5

from odoo import api, fields, models
from odoo.tools.float_utils import float_repr
from odoo.addons.payment_sadad import const
# SUPPORTED_CURRENCIES = ('ARS', 'BRL', 'CLP', 'COP', 'MXN', 'PEN', 'USD')


class PaymentAcquirer(models.Model):
    _inherit = 'payment.provider'

    _sql_constraints = [(
        'custom_providers_setup',
        "CHECK(custom_mode IS NULL OR (code IN ('custom', 'sadad') AND custom_mode IS NOT NULL))",
        "Only custom providers should have a custom mode."
    )]

    code = fields.Selection(
        selection_add=[('sadad', 'sadad')], ondelete={'sadad': 'set default'})
    sadad_merchant_id = fields.Char(
        string="sadad Merchant ID",
        help="The ID solely used to identify the account with Sadad",
        required_if_code='sadad')
    
    sadad_api_key = fields.Char(
        string="sadad API Key", required_if_code='sadad',
        groups='base.group_system')
    
    sadad_domain = fields.Char(
        string="sadad Domain", required_if_code='sadad')
    base_url = fields.Char(required_if_code='sadad', string="Base Return URL")


    @api.model
    def _get_compatible_acquirers(self, *args, currency_id=None, **kwargs):
        """ Override of payment to unlist sadad acquirers for unsupported currencies. """
        acquirers = super()._get_compatible_acquirers(*args, currency_id=currency_id, **kwargs)
        return acquirers

