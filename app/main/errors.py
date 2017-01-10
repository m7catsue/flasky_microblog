# -*- coding: utf-8 -*-
from flask import render_template, request, jsonify
from . import main

# [IMP] 错误处理程序检查Accept请求首部(Werkzeug将其解码为request.accept_mimeytpes),根据首部的值决定客户端期望接收的相应格式
# [IMP] 浏览器一般不限制响应的格式;为只接受JSON而不接受HTML格式的客户端生成JSON格式的响应


@main.app_errorhandler(403)
def forbidden(e):
    if request.accept_mimetypes.accept_json and \
            not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'forbidden'})
        response.status_code = 403
        return response
    return render_template('403.html'), 403


@main.app_errorhandler(404)
def page_not_found(e):
    if request.accept_mimetypes.accept_json and \
            not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'not found'})
        response.status_code = 404
        return response
    return render_template('404.html'), 404


@main.app_errorhandler(500)
def internal_server_error(e):
    if request.accept_mimetypes.accept_json and \
            not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'internal server error'})
        response.status_code = 500
        return response
    return render_template('500.html'), 500
