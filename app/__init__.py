# -*- coding: utf-8 -*-
from flask import Flask
from flask_bootstrap import Bootstrap
from flask_mail import Mail
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_pagedown import PageDown
from config import config  # dict

bootstrap = Bootstrap()
mail = Mail()
moment = Moment()
db = SQLAlchemy()
pagedown = PageDown()

login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'          #'蓝本.登陆页面端点'


def create_app(config_name):                     # APP factory function
    app = Flask(__name__)
    app.config.from_object(config[config_name])  # config是在config.py中最后定义的dict; from_object()方法将配置导入app/程序
    config[config_name].init_app(app)            # config[config_name]是'配置类'

    bootstrap.init_app(app)
    mail.init_app(app)                           # 邮件的相关信息(邮箱/密码)由此传递到mail
    moment.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    pagedown.init_app(app)

    from .main import main as main_blueprint     # relative import: 从main文件夹中的__init__.py中导入'main' as 'main_blueprint'
    app.register_blueprint(main_blueprint)       # 蓝本在工厂函数create_app()中注册到程序/app上 (蓝本中包括: 路由 & 自定义的错误页面)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from.api_1_0 import api as api_1_0_blueprint
    app.register_blueprint(api_1_0_blueprint, url_prefix='/api/v1.0')

    return app

