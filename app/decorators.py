# -*- coding: utf-8 -*-
from functools import wraps
from flask import abort
from flask_login import current_user
from .models import Permission
from threading import Thread


def permission_required(permission):
    # permission_required()函数是一个decorator maker [IMP]
    # functools.wraps作用: takes a function used in a decorator and adds the
    # functionality of copying over the function name, docstring, arguments list, etc
    def decorator(f):                             # f是需要装饰的目标函数
        @wraps(f)                                 # 使用@functools.wraps装饰装饰器内的函数,代指元信息和函数
        def decorated_function(*args, **kwargs):
            if not current_user.can(permission):  # 若当前用户没有特定permission权限,触发http'禁止'错误(403)
                abort(403)                        # abort由flask提供
            return f(*args, **kwargs)             # 有特定permission权限,正常执行函数
        return decorated_function
    return decorator


def admin_required(f):
    """making new decorator with passed argument (Permission.ADMINISTER);
    f is the decorated function"""
    return permission_required(Permission.ADMINISTER)(f)


def async(f):
    """用于执行异步任务的装饰器(Flask Mega-Tutorial);暂未使用"""
    def wrapper(*args, **kwargs):
        thr = Thread(target = f, args = args, kwargs = kwargs)
        thr.start()
    return wrapper

