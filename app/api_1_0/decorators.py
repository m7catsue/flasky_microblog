# -*- coding: utf-8 -*-
from functools import wraps
from flask import g                 # flask全局变量g
from .errors import forbidden       # 403,禁止

# [IMP] 针对客户端的API请求,定义新的permission_required()装饰器,返回403('禁止')状态码
# [IMP] 与app文件夹中decorators.py中的同名函数不同的是:这里对客户端返回json状态码,而不是触发http错误( abort(403) )


def permission_required(permission):
    # permission_required()函数是一个decorator maker [IMP]
    # functools.wraps作用: takes a function used in a decorator and adds the
    # functionality of copying over the function name, docstring, arguments list, etc
    def decorator(f):                                           # f是需要装饰的目标函数
        @wraps(f)                                               # 使用@functools.wraps装饰装饰器内的函数,代指元信息和函数
        def decorated_function(*args, **kwargs):
            if not g.current_user.can(permission):              # 若当前用户没有特定permission权限,返回403('禁止')状态码的json响应
                return forbidden('Insufficient permissions')    # forbidden()在api模块的errors.py中定义,对客户端返回json响应
            return f(*args, **kwargs)                           # 有特定permission权限,正常执行函数
        return decorated_function
    return decorator

