from flask import Flask, Blueprint, request, jsonify, current_app
from db.db_connector import DBConnector
from Crypto.Cipher import DES
from Crypto.Util.Padding import pad, unpad
import base64

auth = Blueprint('auth', __name__)

def encrypt_password(password: str, key: str) -> str:
    des = DES.new(key.encode('utf-8'), DES.MODE_ECB)
    padded_password = pad(password.encode('utf-8'), DES.block_size)
    encrypted_password = des.encrypt(padded_password)
    return base64.b64encode(encrypted_password).decode('utf-8')

def decrypt_password(encrypted_password: str, key: str) -> str:
    print(f'Encrypted password: {encrypted_password}')
    des = DES.new(key.encode('utf-8'), DES.MODE_ECB)
    decoded_encrypted_password = base64.b64decode(encrypted_password)
    print(f'Decoded password: {decoded_encrypted_password}')
    decrypted_password = unpad(des.decrypt(decoded_encrypted_password), DES.block_size)
    print(f'Decrypted password: {decrypted_password}')
    return decrypted_password.decode('utf-8')

DES_KEY = "12345678"

@auth.route('/login', methods=['POST'])
def login():
    ''' Login function'''
    dbc = DBConnector()
    dict_data = request.get_json()
    username = dict_data['username']
    password = dict_data['password']

    _id = dbc.execute_query(query='get_user_by_name', args=username)
    if not isinstance(_id, int):
        return jsonify({'status': 'Bad request'}), 400

    # Check if it is Temporary password
    decrypted_password = ''
    if password == 'T3MP-password-32':
        decrypted_password = password
    else:
        encrypted_password = dbc.execute_query(query='get_user_password', args=_id)
        decrypted_password = str(decrypt_password(encrypted_password, DES_KEY))
        print(f'Password comparsion!! input: {password} vs decrypted_password: {decrypted_password}')
    if password == decrypted_password:
        result = dbc.execute_query(query='update_user_activity', args={
            'user_id': _id,
            'active': True
        })
        is_admin = dbc.execute_query(query='get_user_admin', args=_id)
        print(f'Admin --> {is_admin}')
        if is_admin == 1:
            is_admin = 'true'
            token = current_app.config['ADMIN_AUTH_TOKEN']
        else:
            is_admin = 'false'
            token = current_app.config['AUTH_TOKEN']

        comp_id = dbc.execute_query(query='get_user_comp_id', args=_id)
        is_agent = dbc.execute_query('get_user_agent', args=_id)
        if not isinstance(comp_id, int):
            return jsonify({'status': 'Bad request'}), 400

        return jsonify({
            'status': 'Ok',
            'user_id': _id, 
            'username': username,
            'token': token,
            'is_admin': is_admin,
            'comp_id': comp_id,
            'is_agent': is_agent
        }), 200

    return jsonify({'status': 'Bad credentials'}), 403

@auth.route('/logout', methods=['POST'])
def logout():
    ''' Logout function'''
    dbc = DBConnector()
    dict_data = request.get_json()
    _id = dbc.execute_query(query='update_user_activity', args={
        'user_id': dict_data['user_id'],
        'active': False
    })
    if not isinstance(_id, int):
        return jsonify({'status': 'Bad request'}), 400
    else:
        return jsonify({'status': 'Ok'}), 200

@auth.route('/user/reset-password', methods=['POST'])
def reset_password():
    ''' Reset password function '''
    dbc = DBConnector()
    dict_data = request.get_json()
    user_id = dict_data['user_id']
    new_password = dict_data['new_password']
    token = dict_data['token']

    if token != current_app.config["AUTH_TOKEN"] and token != current_app.config["ADMIN_AUTH_TOKEN"]:
        return jsonify({'status': 'Unauthorised'}), 403

    encrypted_password = encrypt_password(new_password, DES_KEY)
    
    result = dbc.execute_query(query='update_user_password', args={
        "user_id": user_id,
        "new_password": encrypted_password
    })
    if result is True:
        return jsonify({'status': 'Ok'}), 200
    else:
        return jsonify({'status': 'Bad request'}), 400

@auth.route('/signup', methods=['POST'])
def signup():
    ''' Signup function, create new user and company'''
    dbc = DBConnector()
    dict_data = request.get_json()
    user_id = 0
    
    encrypted_password = encrypt_password(dict_data['password'], DES_KEY)

    result = dbc.execute_query('create_user_admin', args={
        "username": dict_data['username'],
        "password": encrypted_password,
        "email": dict_data['email'],
        "comp_name": dict_data['comp_name'],
        "num_employees": dict_data['num_employees'],
        "is_admin": True 
    })
    if isinstance(result, int):
        user_id = result
    else:
        return jsonify({'status': 'Bad request'}), 400

    comp_id = dbc.execute_query('create_company', args={
        "user_id": user_id,
        "comp_name": dict_data['comp_name'],
        "num_employees": dict_data['num_employees']
    })
    result = dbc.execute_query('update_user_comp_id', args={
        'user_id': user_id,
        'comp_id': comp_id
    })
    if isinstance(result, int):
        return jsonify(
            {
                'status': 'Ok',
                'comp_id': comp_id,
                'user_id': user_id,
                'is_admin': True,
                'token': current_app.config["ADMIN_AUTH_TOKEN"]
            }
        ), 200
    else:
        return jsonify({'status': 'Bad request'}), 400

@auth.route('/employee/new', methods=['POST'])
def new_employee():
    ''' Create new employee function '''
    dbc = DBConnector()
    dict_data = request.get_json()
    if dict_data['token'] != current_app.config['ADMIN_AUTH_TOKEN']:
        return jsonify({'status': 'Unauthorized'}), 403
    result = dbc.execute_query('create_user_employee', args={
        'username': dict_data['username'],
        'email': dict_data['email'],
        'comp_id': dict_data['comp_id']
    })
    if isinstance(result, int):
        return jsonify({'status': 'Ok', 'employee_id': result})
    else:
        return jsonify({'status': 'Bad request'})

@auth.route('/retire', methods=['POST'])
def retire():
    ''' Retire function, delete company and all employees '''
    dbc = DBConnector()
    dict_data = request.get_json()
    if dict_data['token'] != current_app.config['ADMIN_AUTH_TOKEN']:
        return jsonify({'status': 'Unauthorized'}), 403
    result = dbc.execute_query(query='delete_sales_by_comp_id', args=dict_data['comp_id'])
    if result is False:
        return jsonify({'status': 'Bad request'}), 400
    result = dbc.execute_query(query='delete_products_by_comp_id', args=dict_data['comp_id'])
    if result is False:
        return jsonify({'status': 'Bad request'}), 400
    result = dbc.execute_query(query='delete_users_by_comp_id', args=dict_data['comp_id'])
    if result is False:
        return jsonify({'status': 'Bad request'}), 400
    result = dbc.execute_query('delete_company_by_id', dict_data['comp_id'])
    if result is not True:
        return jsonify({'status': "Bad request"}), 400
    result = dbc.execute_query('delete_user_by_id', dict_data['user_id'])
    if result is not True:
        return jsonify({'status': "Bad request"}), 400
    if result is True:
        return jsonify({'status': 'Ok'}), 200
    else:
        return jsonify({'status': 'Bad request'}), 400

@auth.route('/employee/delete', methods=['POST'])
def delete_employee():
    ''' Delete employee function '''
    dbc = DBConnector()
    dict_data = request.get_json()
    if dict_data['token'] != current_app.config['ADMIN_AUTH_TOKEN']:
        return jsonify({'status': 'Unauthorized'}), 403
    result = dbc.execute_query('delete_user_by_id', dict_data['employee_id'])
    if result is True:
        return jsonify({'status': 'Ok'}), 200
    else:
        return jsonify({'status': "Bad request"}), 400
