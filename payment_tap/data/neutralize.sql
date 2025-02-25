-- disable tap payment provider
UPDATE payment_provider
   SET tap_secret_key = NULL,
       tap_publishable_key = NULL,
       tap_payment_options = NULL,
       tap_use_3d_secure = False;