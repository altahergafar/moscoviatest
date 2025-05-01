from odoo import models, fields, api


class Product(models.Model):
    #_inherit = "product.product"
    
    _inherit = 'product.template'

    vendor_code = fields.Char('Vendor Code',)
    mtcode = fields.Char('MtCode',)
    