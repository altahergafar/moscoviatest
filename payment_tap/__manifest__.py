# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

{
    'name': 'Tap Payment Gateway',
    'category': 'Accounting/Payment Providers',
    'version': '17.0.1.0',
    'author': 'Kanak Infosystems LLP.',
    'website': 'https://www.kanakinfosystems.com',
    'license': 'OPL-1',
    'summary': '''
Tap Payment Gateway module is used in payment method to simplifies online payment.
KNET | MADA | BENEFIT | BENEFITPAY | BENEFIT PAY | Oman Net | Apple Pay | Visa | Mastercard | meeza | Amex
Refund | Subscription | Save Card | Use save card to pay
Tap payment gateway
Secure online payments with Tap
Tap payment processing
Tap payment integration
Tap payment API
Tap payment solutions
Tap payment system
Tap checkout
Tap payment methods
Tap payment processing for e-commerce
Tap payment gateway for businesses
Tap mobile payments
Tap payment technology
Tap payment platform
Tap payment services
Tap payment gateway for websites
Tap payment acceptance
Tap payment processing fees
Tap payment gateway setup
Tap payment gateway benefits
Tap payment gateway for small businesses
Tap payment gateway for developers
Tap payment gateway security
Tap payment gateway documentation
Tap payment gateway reviews
Tap vs. other payment gateways
Tap payment gateway for international transactions
Tap payment gateway for Middle East markets
Tap payment gateway for GCC countries
Tap payment gateway for MENA region
    ''',
    'description': """Tap Payment Gateway module is used in payment method to simplifies online payment.""",
    'depends': ['payment'],
    'images': ['static/description/banner.jpg'],
    'data': [
        'data/payment_provider_cron_data.xml',
        'views/payment_provider_views.xml',
        'views/payment_provider_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'installable': True,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'price': 69,
    'currency': 'EUR'
}
