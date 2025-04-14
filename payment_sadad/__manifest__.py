# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sadad Payment Provider',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Payment Acquirers',
    'sequence': 1,
    'author' : 'Taqat for Technology / Rimes Gold',
    'summary': 'Payment Provider: Sadad Implementation',
    'description': """Sadad Payment Provider""",
    'depends': ['base','payment'],
    'data': [
        'views/payment_sadad_templates.xml',
        'data/payment_acquirer_data.xml',
        'views/payment_views.xml',
        'views/res_currency.xml'
    ],
    'application': True,
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}
