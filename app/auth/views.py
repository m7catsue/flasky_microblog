# -*- coding: utf-8 -*-
from flask import render_template, redirect, request, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from . import auth
from .. import db
from ..models import User
from ..email import send_email
from .forms import LoginForm, RegistrationForm, ChangePasswordForm, \
    PasswordResetRequestForm, PasswordResetForm, ChangeEmailForm

################################################################################################################
# First of all, is_anonymous() and is_authenticated() are each other's inverse.
# You could define one as the negation of the other, if you want.
#
# You can use these two methods to determine if a user is logged in.
# When nobody is logged in Flask-Login's current_user is set to an AnonymousUser object.
# This object responds to is_authenticated() and is_active() with False and to is_anonymous() with True.
#
# The is_active() method has another important use.
# Instead of always returning True like I proposed in the tutorial,
# you can make it return False for banned or deactivated users and those users will not be allowed to login.
################################################################################################################


@auth.before_app_request
def before_request():
    """对属于蓝图auth的每个请求前判断: 若用户已注册(已登录)但还没有confirm,且其访问的页面不是confirm页面或static端节点,重定向到auth.unconfirmed
    任何使用了before_request装饰器的函数在接收请求之前都会运行;在蓝图(auth)中需要使用before_app_request;
    is_authenticated() must return True if the user has login credentials or False otherwise;
    From a blueprint, the before_request hook applies only to requests that belong to the blueprint."""
    if current_user.is_authenticated:
        current_user.ping()                                  # 更新数据库User模型的last_seen属性
        if not current_user.confirmed \
            and request.endpoint[:5] != 'auth.' \
            and request.endpoint != 'static':
            return redirect(url_for('auth.unconfirmed'))


@auth.route('/unconfirmed')
def unconfirmed():
    """is_anonymous() must always return False for regular users;
    is_anonymous()和is_authenticated()互为对立值"""
    if current_user.is_anonymous or current_user.confirmed:  # (条件)若当前用户is_anonymous(未登录) 或 已注册且confirm的用户:重定向到主页
        return redirect(url_for('main.index'))
    return render_template('auth/unconfirmed.html')          # (逆否)当前用户is_authenticated且未确认:重定向到unconfirmed.html


@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():                            # 通过form对信息进行验证(继承form父类的方法)
        user = User.query.filter_by(email=form.email.data).first()
        # 用户名和密码验证正确:
        if user and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)          # flask-login提供的函数
            # 重定向到[1]用户未登录前试图访问的页面(需登录页面)
            # 或者   [2]首页
            return redirect(request.args.get('next') or url_for('main.index'))
        # 用户名和密码验证错误:
        flash('Invalid username or password.')
    return render_template('auth/login.html', form=form)     # 模板在templates/auth文件夹中


@auth.route('/logout')
@login_required
def logout():
    logout_user()                                            # flask-login提供的函数
    flash('You have been logged out.')
    return redirect(url_for('main.index'))                   # 重定向到main蓝图的index视图函数


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():  # 通过form对信息进行验证(继承form父类的方法)
        user = User(email=form.email.data,
                    username=form.username.data,
                    password=form.password.data)
        db.session.add(user)
        db.session.commit()
        token = user.generate_confirmation_token()
        send_email(user.email, 'Confirm Your Account', 'auth/email/confirm',   # 收件人,主题,模板(不带扩展名)
                   user=user, token=token)                                     # 传入模板的参数 **kwargs
        flash('A confirmation email has been sent to you by email.')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)


@auth.route('/confirm/<token>')  # [IMP] 尖括号中的token即confirm()函数中所传入的参数token
@login_required
def confirm(token):
    """新注册用户的confirm页面:通过token进行用户注册验证;
    实际confirm过程在User模型中进行,视图函数confirm()需根据User模型的confirm结果进行反馈"""
    if current_user.confirmed:                                # 数据库中confirmed字段: True/False
        return redirect(url_for('main.index'))
    if current_user.confirm(token):                           # User类方法,成功后将confirmed字段设为True
        flash('You have confirmed your account. Thanks!')
    else:
        flash('The confirmation link is invalid or has expired.')
    return redirect(url_for('main.index'))                    # 重定向到main蓝图的index视图函数


@auth.route('/confirm')
@login_required
def resend_confirmation():
    """重新发送新账户confirm邮件;此时用户已注册,通过current_user可以取到该用户信息"""
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, 'Confirm Your Account', 'auth/email/confirm',  # 收件人,主题,模板(不带扩展名)
               user=current_user, token=token)                                    # 传入模板的参数 **kwargs
    flash('A new confirmation email has been sent to you by email.')
    return redirect(url_for('main.index'))                                        # 重定向到main蓝图的index视图函数


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """[增加功能] 更改用户密码"""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):   # current_user由flask-login提供;原密码验证正确
            current_user.password = form.password.data
            db.session.add(current_user)
            db.session.commit()
            flash('Your password has been updated.')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid password.')                             # 原密码验证错误
    return render_template("auth/change_password.html", form=form)


@auth.route('/reset', methods=['GET', 'POST'])
def password_reset_request():
    """[增加功能] 重置用户密码: (1)用户请求重置密码"""
    if not current_user.is_anonymous:                              # 若当前用户未登录,重定向至index页面
        return redirect(url_for('main.index'))
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:                                                   # email对应的user存在:生成token,发送邮件
            token = user.generate_reset_token()
            send_email(user.email, 'Reset Your Password', 'auth/email/reset_password',  # 收件人、主题、模板(不带扩展名)
                       user=user, token=token, next=request.args.get('next'))           # 传入模板的参数 **kwargs
        flash('An email with instructions to reset your password has been '
              'sent to you.')
        return redirect(url_for('auth.login'))                     # email对应的user不存在:重定向至auth.login
    return render_template('auth/reset_password.html', form=form)


@auth.route('/reset/<token>', methods=['GET', 'POST'])             # 尖括号中的token即password_reset()的参数token
def password_reset(token):
    """[增加功能] 重置用户密码: (2)进行密码重置
    用户通过点击邮件中链接(reset token)进入本页面"""
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))
    form = PasswordResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None:
            return redirect(url_for('main.index'))
        if user.reset_password(token, form.password.data):         # 用户重置密码:原密码通过验证(返回True)
            flash('Your password has been updated.')
            return redirect(url_for('auth.login'))
        else:                                                      # 用户重置密码:原密码未通过验证(返回False)
            return redirect(url_for('main.index'))
    return render_template('auth/reset_password.html', form=form)


@auth.route('/change-email', methods=['GET', 'POST'])
@login_required
def change_email_request():
    """[增加功能] 变更用户邮箱地址: (1)用户请求更改邮箱地址"""
    form = ChangeEmailForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            new_email = form.email.data
            token = current_user.generate_email_change_token(new_email)
            send_email(new_email, 'Confirm your email address', 'auth/email/change_email',  # 收件人、主题、模板(不带扩展名)
                       user=current_user, token=token)                                      # 传入模板的参数 **kwargs
            flash('An email with instructions to confirm your new email '
                  'address has been sent to you.')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid email or password.')
    return render_template("auth/change_email.html", form=form)


@auth.route('/change-email/<token>')
@login_required
def change_email(token):
    """[增加功能] 变更用户邮箱地址: (2)进行邮箱地址更改
    用户通过点击邮件中链接(change email token)进入本页面"""
    if current_user.change_email(token):                     # change_email()方法在User模型中定义
        flash('Your email address has been updated.')        # change_email()方法加载token并验证,若验证成功更新数据库
    else:
        flash('Invalid request.')
    return redirect(url_for('main.index'))

