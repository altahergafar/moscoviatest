{
    'name': 'Stock custom', 
    'summary': 'Adds a sidebar to the main screen',
    'description': '''
        This module adds a sidebar to the main screen. The sidebar has a list
        of all installed apps similar to the home menu to ease navigation.
    ''',
    'version': '17.0.1.1.2',
    'category': 'Tools/UI',
    'license': 'LGPL-3', 
    'depends': [
        'web',
        'stock',
    ],
    'data': [
        'views/stock.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': '_setup_module',
}
