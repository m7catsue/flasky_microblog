# -*- coding: utf-8 -*-
from flask import render_template, redirect, url_for, flash, abort, \
    request, current_app, make_response, g
from flask_login import login_required, current_user
from flask_sqlalchemy import get_debug_queries
from flask_whooshalchemyplus import index_one_record  # 创建Post实例后对其进行index_one_record()操作 [IMP]
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm, CommentForm, SearchForm
from .. import db
from ..models import User, Role, Permission, Post, Comment
from ..decorators import admin_required, permission_required


#################################################################################################################
# 供测试部分使用

@main.after_app_request                                                 # 在视图函数处理完请求之后执行
def after_request(response):
    """报告影响性能的缓慢数据库查询;通过python manage.py profile命定启动;
    get_debug_queries()默认情况下只在调试模式中可用;但其更适合生产环境下使用,因为在开发阶段中使用的数据库较小,很少发生性能问题"""
    for query in get_debug_queries():
        if query.duration >= current_app.config['FLASKY_SLOW_DB_QUERY_TIME']:
            current_app.logger.warning(
                'Slow query: %s\nParameters: %s\nDuration: %fs\nContext: %s\n'
                % (query.statement, query.parameters, query.duration,
                   query.context))
    return response


@main.route('/shutdown')
def server_shutdown():
    """关闭服务器 [seleium测试使用,所有测试完成后,停止flask服务器]"""
    if not current_app.testing:                                         # 仅在测试配置环境中可用
        abort(404)
    shutdown = request.environ.get('werkzeug.server.shutdown')
    if not shutdown:
        abort(500)
    shutdown()
    return 'Shutting down...'


#################################################################################################################


@main.route('/', methods=['GET', 'POST'])
def index():
    """microblog应用的主页面,包含功能:(1)发表新文章(2)显示所有人或用户关注的人的文章"""
    form = PostForm()
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        post = Post(body=form.body.data,
                    author=current_user._get_current_object())  # current_user._get_current_object():这个对象的表现类似用户对象,
        db.session.add(post)                                    # 但实际上却是一个轻度包装,包含真正的用户对象;数据库需要真正的用户对象,
        db.session.commit()                                     # 因此要调用_get_current_object()方法
        index_one_record(post)                                  # [IMP] index新创建的Post实例,否则无法被搜索到?
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)                        # 渲染的页数从request.args中获取
    show_followed = False                                               # 若未指定,则默认为1;type=int保证参数无法转换为整数时,返回默认值(1)
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed', ''))  # cookies是dict,其get方法的默认值为空字符串
    if show_followed:
        query = current_user.followed_posts                             # 主页显示关注的人的博客文章
    else:
        query = Post.query                                              # 主页显示所有人的博客文章
    pagination = query.order_by(Post.timestamp.desc()).paginate(        # query对象由上if..else..语句提供
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],     # paginate()参数: (1)页数:唯一必需参数(2)每页显示记录的数量,默认20条
        error_out=False)                                                # (3)error_out为True时,若请求的页数超出了范围,则返回404错误;为False时,页数超出范围返回一个空列表
    posts = pagination.items
    return render_template('index.html', form=form, posts=posts,
                           show_followed=show_followed, pagination=pagination)


@main.route('/all')
@login_required                                                 # 若是游客,则index()视图函数返回所有人的博客文章
def show_all():
    """将show_followed cookie设为空,重定向到main.index,显示所有人的博客文章"""
    resp = make_response(redirect(url_for('.index')))           # cookie只能在response对象中设置,需用make_response()方法创建相应对象
    resp.set_cookie('show_followed', '', max_age=30*24*60*60)   # max_age设置cookie的过期时间,单位为秒;若不指定max_age,浏览器关闭后cookie即过期
    return resp


@main.route('/followed')
@login_required
def show_followed():
    """将show_followed cookie设为非空,重定向到main.index,显示用户所关注的人的博客文章"""
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '1', max_age=30*24*60*60)
    return resp


@main.route('/user/<username>')  # 尖括号中username即为视图函数user()的参数
def user(username):
    """用户资料页面"""
    user = User.query.filter_by(username=username).first_or_404()    # 用户不存在抛出404错误
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('user.html', user=user, posts=posts,
                           pagination=pagination)


@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """用户编辑资料页面"""
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        db.session.commit()
        flash('Your Profile has been updated.')
        return redirect(url_for('.user', username=current_user.username))  # 重定向到用户对应的main.user用户资料页面
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form)


@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])  # 尖括号中id即为视图函数edit_profile_admin()的参数
@login_required
@admin_required  # 检查管理员权限
def edit_profile_admin(id):
    """管理员编辑用户资料页面;
    用户由id指定,因此可用flask-sqlalchemy使用get_or_404()函数,若提供的id不正确,则返回404错误"""
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        flash('The profile has been updated.')
        return redirect(url_for('.user', username=user.username))  # 重定向到用户对应的main.user用户资料页面
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user)


@main.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    """一篇博客文章的页面;博客文章的url通过使用插入数据库时分配的唯一id字段构建;
    增加对博客文章的评论功能"""
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data,
                          post=post,
                          author=current_user._get_current_object())  # [IMP] 使用_get_current_object()获得user对象
        db.session.add(comment)                                       # current_user是对user对象的轻度包装
        db.session.commit()
        flash('Your comment has been published.')
        return redirect(url_for('.post', id=post.id, page=-1))        # page=-1;comment顺序排列,新提交的comment在最后一页
    page = request.args.get('page', 1, type=int)                      # type=int保证参数无法转换为整数时,返回默认值(1)
    if page == -1:
        page = (post.comments.count()) // \
            current_app.config['FLASKY_COMMENTS_PER_PAGE'] + 1        # 当page=-1时,通过整数除法得到最后一页的确切页码
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('post.html', posts=[post], form=form,      # post.html接收列表作为参数,以重复使用 _posts.html 模板
                           comments=comments, pagination=pagination)  # 在post.html模板中,通过posts[0].id获得当前post的id


@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """用户编辑博客文章页面"""
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
        not current_user.can(Permission.ADMINISTER):   # 当前用户不是文章作者或管理员
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        db.session.commit()
        flash('The post has been updated.')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html', form=form)


@main.route('/follow/<username>')  # current_user 'follow' <username>
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    """当前用户follow其他用户;
    用户的follow动作在数据库中创建新的Follow实例"""
    user = User.query.filter_by(username=username).first()  # 当前用户尝试follow的用户
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('You are already following this user.')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)                               # 在数据库中创建新的Follow实例
    flash('You are now following %s.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/unfollow/<username>')  # current_user 'unfollow' <username>
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    """当前用户unfollow其他用户;
    用户的unfollow动作在数据库中删除相应的Follow实例"""
    user = User.query.filter_by(username=username).first()  # 当前用户尝试unfollow的用户
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('You are not following this user.')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)                             # 在数据库中删除相应的Follow实例
    flash('You are not following %s anymore.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/followers/<username>')
def followers(username):
    """用户(<username>)的关注者(<username>'s followers)"""
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp}          # 返回的item为Follow实例;item.follower为User实例 [IMP]
               for item in pagination.items]                                 # list of dicts
    return render_template('followers.html', user=user, title="Followers of",
                           endpoint='.followers', pagination=pagination,
                           follows=follows)


@main.route('/followed-by/<username>')
def followed_by(username):
    """用户(<username>)正在关注的其他用户(followed by <username>)"""
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(
        page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
               for item in pagination.items]                                  # list of dicts
    return render_template('followers.html', user=user, title="Followed by",  # 仍然使用followers.html模板
                           endpoint='.followed_by', pagination=pagination,
                           follows=follows)


@main.route('/moderate')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate():
    """评论管理页面;需要MODERATE_COMMENTS权限;将评论按发表时间逆序排列;
    [IMP] moderate.html模板中set moderate=True,_comments.html子模板根据moderate变量的值进行相应渲染"""
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('moderate.html', comments=comments,                # moderate.html中套用_comments.html子模板(处理具体评论是否显示)
                           pagination=pagination, page=page)                  # moderate.html只有高级权限才能访问


@main.route('/moderate/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_enable(id):
    """评论管理操作(评论id由url传入): enable comment"""
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('.moderate',                                       # 进行评论管理操作后,重定向到'.moderate'
                            page=request.args.get('page', 1, type=int)))       # _comments.html模板指定了page参数,重定向后会返回之前的页面


@main.route('/moderate/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_disable(id):
    """评论管理操作(评论id由url传入): disable comment"""
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))       # 进行评论管理操作后,重定向到'.moderate'


#################################################################################################################


@main.route('/delete-post/<int:id>')
@login_required
@permission_required(Permission.WRITE_ARTICLES)
def delete_post(id):
    """<新增自定义功能> 用户删除已发表的博客文章"""
    post = Post.query.get_or_404(id)
    if current_user.id == post.author_id \
            or current_user.can(Permission.ADMINISTER):                        # 当前用户为文章作者或管理员:可以删除博客文章
        db.session.delete(post)
        db.session.commit()
        flash('The post has been deleted.')
        return redirect(url_for('main.index'))
    else:                                                                      # 当前用户没有相应权限
        flash("You don't have permission to delete the post.")
        return redirect(url_for('main.index'))


@main.route('/delete-comment/<int:id>')
@login_required
@permission_required(Permission.COMMENT)
def delete_comment(id):
    """<新增自定义功能> 用户删除在自己博客文章下已发表的评论;
    博客文章作者可删除其文章下的任何评论;comment.post.author_id [IMP 数据库模型 IMP]"""
    comment = Comment.query.get_or_404(id)
    if current_user.id == comment.author_id \
            or current_user.can(Permission.ADMINISTER) \
            or current_user.id == comment.post.author_id:                      # 可删除评论:(1)评论作者(2)评论所属文章的作者(3)管理员
        db.session.delete(comment)
        db.session.commit()
        flash('The comment has been deleted.')
        return redirect(url_for('main.post', id=comment.post_id))
    else:                                                                      # 当前用户没有相应权限
        flash("You don't have permission to delete the comment.")
        return redirect(url_for('main.index'))


@main.route('/search', methods=['POST'])
@login_required
def search():
    """<新增自定义功能> 处理用户的搜索请求;
    request.path表示当前页面路径(i.e. /search);
    search_form保存在全局变量g中,由@auth.before_app_request设置;
    搜索工作不在这里直接做的原因还是担心用户无意中触发了刷新，这样会导致表单数据被重复提交"""
    if not g.search_form.validate_on_submit():
        return redirect(url_for('main.index'))
    return redirect(url_for('main.search_results', query=g.search_form.search.data))


@main.route('/search-results/<query>')
@login_required
def search_results(query):
    """<新增自定义功能> 处理用户的搜索请求,返回搜索结果;
    whoosh_search()和paginate()连用已达到对搜索结果的分页效果"""
    page = request.args.get('page', 1, type=int)                               # 设置pagination的默认起始位置
    pagination = Post.query.whoosh_search(query).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    searched_posts = pagination.items
    return render_template('search_results.html', pagination=pagination,
                           query=query, posts=searched_posts)                  # 需要使用_posts.html模板,所以需传入posts参数

