# -*- coding: utf-8 -*-
from flask import jsonify, request, g, abort, url_for, current_app
from .. import db
from ..models import Post, Permission
from . import api                             # api蓝本
from .decorators import permission_required   # 为api请求制定的permission_required装饰器;若无权限返回403('禁止')状态码的json响应,而不是触发http错误(abort(403))
from .errors import forbidden                 # forbidden()返回403('禁止')的json响应


@api.route('/posts/')
def get_posts():
    """处理客户端对posts集合的GET请求"""
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_posts', page=page-1, _external=True)
    next = None
    if pagination.has_next:
        next = url_for('api.get_posts', page=page+1, _external=True)
    return jsonify({
        'posts': [post.to_json() for post in posts],  # 通过list comprehension生成所有posts的JSON版本
        'prev': prev,
        'next': next,
        'count': pagination.total
    })


@api.route('/posts/<int:id>')
def get_post(id):
    """处理客户端对单篇post的GET请求"""
    post = Post.query.get_or_404(id)     # 404(not found)错误在整个应用的层面定义(app.main.errors.py中)
    return jsonify(post.to_json())       # 已在14章修改支持对客户端返回404的json响应(而对浏览器返回http 404错误)


@api.route('/posts/', methods=['POST'])
@permission_required(Permission.WRITE_ARTICLES)
def new_post():
    """博客文章POST请求的处理;
    响应主体包含了新建的资源,所以客户端无需在创建资源后再发起一个GET请求来获取资源"""
    post = Post.from_json(request.json)  # Post类方法:通过JSON格式数据生成Post实例(只需提交body字段)
    post.author = g.current_user
    db.session.add(post)
    db.session.commit()
    return jsonify(post.to_json()), 201, \
        {'Location': url_for('api.get_post', id=post.id, _external=True)}  # 201代码:创建成功


@api.route('/posts/<int:id>', methods=['PUT'])
@permission_required(Permission.WRITE_ARTICLES)
def edit_post(id):
    """博客文章PUT请求(更新现有资源)的处理;
    响应主体包含了更新后的资源,所以客户端无需在创建资源后再发起一个GET请求来获取资源"""
    post = Post.query.get_or_404(id)
    if g.current_user != post.author and \
            not g.current_user.can(Permission.ADMINISTER):
        return forbidden('Insufficient permissions')  # 返回403(禁止)的JSON响应
    post.body = request.json.get('body', post.body)   # 更新post.body
    db.session.add(post)
    db.session.commit()
    return jsonify(post.to_json())


