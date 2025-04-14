# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
import json

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SadadController(http.Controller):
    _return_url = '/payment/sadad/return'
    
    @http.route(_return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False, save_session=False)
    def sadad_return(self, **data):
        print("adjnkjnsf sdfsmdfkmsdlf ,s fksnfks ")
        _logger.info("beginning _handle_notification_data with data %s", pprint.pformat(data))            
       
        if self._sadad_validate_data(data):
            request.env['payment.transaction'].sudo()._handle_notification_data('sadad', data)
       
        return request.redirect('/payment/status')

    def _sadad_validate_data(self, data):
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('sadad', data)
        acquirer_sudo = tx_sudo.provider_id
        IV = "@@@@&&&&####$$$$"
        sadad_hash = tx_sudo._decode(data['checksumhash'], IV, acquirer_sudo.sadad_api_key)
        salt = sadad_hash[-4:]
        checksumhash = data.get('checksumhash')
        data.pop('checksumhash')
        datas = json.dumps(data,separators=(',', ':'))
        datas=datas.replace("/","\\/")

        generated_checksum = tx_sudo.return_checksum(datas,acquirer_sudo.sadad_api_key,True)
        if generated_checksum and data.get('RESPCODE') == "1" and data.get('STATUS') == "TXN_SUCCESS":
            _logger.info("checksumhash checksumhash checksumhash checksumhash checksumhash**************")
            _logger.debug('validated data')
            return True
        else:
            _logger.warning('data are tampered')
            return False
