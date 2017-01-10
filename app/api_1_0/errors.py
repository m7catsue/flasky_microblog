# -*- coding: utf-8 -*-
from flask import jsonify                           # cwd是flasky_social_blogging目录
from app.exceptions import ValidationError          # 从app文件夹中的exceptions模组中导入ValidationError
from . import api                                   # 从当前文件夹(api_1_0)中的__init__.py中导入api(buleprint)

# main.errors.py中定义了403, 404, 500三种错误;
# 之所以要把404、500这两个错误的处理方法和403等其它HTTP错误分开说明，是因为通常404和500错误是由Flask自己生成的，
# 并且这两个错误通常会返回HTML响应，而其它的则只需要返回个状态码和提示信息就行了。
# The remaining status codes are generated explicitly by the web service, so they can be
# implemented as helper functions inside the blueprint in the errors.py module.


def bad_request(message):
    # API error handler for status code 400
    response = jsonify({'error': 'bad request', 'message': message})
    response.status_code = 400
    return response


def unauthorized(message):
    # API error handler for status code 401
    response = jsonify({'error': 'unauthorized', 'message': message})
    response.status_code = 401
    return response


def forbidden(message):
    # API error handler for status code 403
    response = jsonify({'error': 'forbidden', 'message': message})
    response.status_code = 403
    return response


@api.errorhandler(ValidationError)    # 接受一个Exception类作为参数; 对比于main.error.py中接受的403/404/500等参数
def validation_error(e):              # 当任何时候(api蓝本)这个exception类被抛出时,本装饰器函数即被调用来处理所抛出的ValidationError
    """api蓝本错误处理:处理ValidationError,返回状态码400(bad_request);
    ValidationError由数据库模型的from_json静态方法抛出;ValidationError是ValueError的空白子类"""
    # The except clause may specify a variable after the exception name (or tuple).
    # The variable is bound to an exception instance with the arguments stored in instance.args
    return bad_request(e.args[0])


# [INFO] 400, bad_request产生原因:
# the issue is that Flask raises an HTTP error when it fails to find a key in the args and form dictionaries.
# What Flask assumes by default is that if you are asking for a particular key and it's not there then something
# got left out of the request and the entire request is invalid.

