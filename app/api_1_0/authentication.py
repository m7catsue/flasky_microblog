# -*- coding: utf-8 -*-
from flask import g, jsonify
from flask_httpauth import HTTPBasicAuth
from ..models import User, AnonymousUser
from . import api
from .errors import unauthorized, forbidden

# [1]auth.verify_password(verify_password_callback):
# If defined, this callback function will be called by the framework to verify that
# the username and password combination provided by the client are valid.
# The callback function takes two arguments, the username and the password and must return True or False.

# [2]auth.login_required(view_function_callback):
# This callback function will be called when authentication is succesful.
# This will typically be a Flask view function.

# [3] error_handler(error_callback):
# If defined, this callback function will be called by the framework when it is necessary to send
# an authentication error back to the client. The return value from this function can be the body
# of the response as a string or it can also be a response object created with make_response.
# If this callback isn’t provided a default error response is generated.

auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(email_or_token, password):
    """通过Flask-HTTPAuth进行HTTP认证(API请求);
    将通过认证的用户保存在flask全局对象g中,以便视图函数进行访问;
    [IMP] 可使用 (1)email(需同时发送email和password),(2)token(仅需发送token,password为空),(3)匿名用户(两个字段都为空);
    [IMP] 若credential验证不正确(最终返回False),服务器向客户端返回401(未授权)错误,由auth_error()函数处理"""
    if email_or_token == '':                                     # API蓝本支持匿名用户访问,此时客户端发送的电子邮件地址为空
        g.current_user = AnonymousUser()                         # 对匿名用户返回True,通过认证
        return True
    if password == '':                                           # password为空(此时email_or_token不为空):假定email_or_token发送的是token,进行密码验证
        g.current_user = User.verify_auth_token(email_or_token)  # User类的静态方法(staticmethod),返回user实例或者None
        g.token_used = True                                      # 设置g.token_used: 为使视图函数能分辨这2种认证方法(emial/token)
        return g.current_user is not None                        # 返回token验证结果(True/False);g.current_user=None时,这里即返回False [IMP]
    user = User.query.filter_by(email=email_or_token).first()
    if not user:                                                 # email(所对应的user)不存在,返回False
        return False
    g.current_user = user                                        # email所对应的user存在;将通过认证的用户保存在flask全局对象g中,以便视图函数进行访问
    g.token_used = False
    return user.verify_password(password)                        # 验证密码成功返回True,否则返回False


@auth.error_handler
def auth_error():
    """处理http认证的错误(401,未授权);
    [IMP] 401错误在verify_password()函数认证失败时(即verify_password()最终返回False)由Flask-HTTPAuth(装饰器)生成"""
    return unauthorized('Invalid credentials')


@api.before_request   # 属于api蓝本
@auth.login_required  # 这里login_required由Flask-HTTPAuth的HTTPBasicAuth类提供
def before_request():
    """[IMP] 在每个API request之前执行此函数(api蓝本);
    若flask全局变量g中的current_user不是匿名用户(已注册)且未confirm,拒绝其进行认证(403, 禁止);
    可进行认证的用户类型:匿名用户;注册且confirm的用户"""
    if not g.current_user.is_anonymous and \
            not g.current_user.confirmed:
        return forbidden('Unconfirmed account')


@api.route('/token')  # 属于api蓝本:before_request()函数适用(@api.before_request)
def get_token():
    """客户端请求生成auth token;
    只有已注册用户可生成token;增加encode()，将bytes解码为字符串"""
    if g.current_user.is_anonymous or g.token_used:          # 阻止:(1)匿名用户,(2)'token_used',防止客户端使用旧token来生成新token
        return unauthorized('Invalid credentials')           # 返回401(未授权)
    return jsonify({'token': g.current_user.generate_auth_token(
        expiration=3600).decode(), 'expiration': 3600})      # token有效期1小时

