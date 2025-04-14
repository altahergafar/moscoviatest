from odoo import api,models, fields

class CurrencyRateNew(models.Model):
    _inherit = "res.currency.rate"

    rate = fields.Float(
        digits=(16,3),
        group_operator="avg",
        help='The rate of the currency to the currency of rate 1',
        string='Technical Rate'
    )
    company_rate = fields.Float(
        digits=(16,3),
        compute="_compute_company_rate",
        inverse="_inverse_company_rate",
        group_operator="avg",
        help="The currency of rate 1 to the rate of the currency.",
    )
    inverse_company_rate = fields.Float(
        digits=(16,3),
        compute="_compute_inverse_company_rate",
        inverse="_inverse_inverse_company_rate",
        group_operator="avg",
        help="The rate of the currency to the currency of rate 1 ",
    )
