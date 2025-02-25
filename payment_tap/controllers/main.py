# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

import base64
import json
import logging
import pprint
import requests
import werkzeug

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TapController(http.Controller):
    _return_url = '/payment/tap/return/'

    @http.route('/payment/tap/redirect', type='http', auth='public', csrf=False)
    def tap_redirect(self, **post):
        url = post.get('redirect_url')
        redirect_url = base64.b64decode(url).decode()
        return werkzeug.utils.redirect(redirect_url)

    @http.route(_return_url, type='http', auth='public', csrf=False, save_session=False)
    def tap_return_feedback(self, **post):
        tap_id = http.request.params.get('tap_id')
        provider = request.env['payment.provider'].sudo().browse(int(post.get('provider_id')))
        url = "https://api.tap.company/v2/charges/%s" % tap_id
        headers = {'authorization': 'Bearer %s' % provider.tap_secret_key}
        response = requests.request("GET", url, data="{}", headers=headers)
        data = json.loads(response.text)
        _logger.info('Tap: entering return feedback with post data %s', pprint.pformat(data))
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'tap', data
        )
        tx_sudo._handle_notification_data('tap', data)
        return request.redirect('/payment/status')
