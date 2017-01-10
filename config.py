# -*- coding: utf-8 -*-
import os
from whoosh.analysis import StemmingAnalyzer, SimpleAnalyzer
from jieba.analyse import ChineseAnalyzer

basedir = os.path.abspath(os.path.dirname(__file__))                      # 当前文件(config.py)所在文件夹的绝对路径


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard_to_guess_string'

    # [IMP] 已被flask-sqlalchemy删除] 当前request结束时自动commit对sqlalchemy的所有更改
    # [IMP] 相应视图函数中需要增加db.session.commit()语句
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True

    # UserWarning: SQLALCHEMY_TRACK_MODIFICATIONS adds significant overhead and
    # will be disabled by default in the future. Set it to True to suppress this warning.
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True                            # 启用缓慢查询记录功能的配置(FLASKY_SLOW_DB_QUERY_TIME=0.5)

    MAIL_SERVER = 'smtp.qq.com'                                 # 由于GFW使用qq邮箱
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'm7catsue@qq.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'lxkimgiejkuwbiai'  # qq邮箱设置中生成的授权码,在第三方客户端中替代密码使用
    FLASKY_MAIL_SUBJECT_PREFIX = '[Flasky]'
    FLASKY_MAIL_SENDER = 'Flasky Admin <m7catsue@qq.com>'                  # 发件人名称字符串
    FLASKY_ADMIN = os.environ.get('FLASKY_ADMIN') or 'luyaxin1990@gmail.com'
    FLASKY_POSTS_PER_PAGE = 20                                             # pagination/分页:设置每页显示的条数
    FLASKY_FOLLOWERS_PER_PAGE = 50
    FLASKY_COMMENTS_PER_PAGE = 30
    FLASKY_SLOW_DB_QUERY_TIME = 0.5

    WHOOSH_ANALYZER = ChineseAnalyzer()                        # 设置whoosh搜索引擎的默认分析器(用于分词)

    @staticmethod           # behave like plain functions except that you can call them from an instance or the class
    def init_app(app):      # staticmethods are used to group functions which have some logical connection to a class
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')

    WHOOSH_BASE = os.path.join(basedir, 'search-dev')   # [IMP] set location for the whoosh index (指向文件夹search-dev)


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-test.sqlite')
    WHOOSH_BASE = os.path.join(basedir, 'search-test')
    WTF_CSRF_ENABLED = False                    # flask-wtf生成的表单中包含一个隐藏字段,其内容是CSRF令牌,需要和表单中数据一起提交;
                                                # 在测试中为了避免处理CSRF令牌这一繁琐操作,在测试配置中禁止CSRF保护功能


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data.sqlite')
    WHOOSH_BASE = os.path.join(basedir, 'search')

    @classmethod
    def init_app(cls, app):
        """生产环境下程序出错时发送邮件给admin;
        在ProductionConfig类的init_app()方法实现中,配置程序的日志记录器把错误写入电子邮件日志记录器"""
        Config.init_app(app)

        import logging
        from logging.handlers import SMTPHandler
        credentials = None
        secure = None
        if getattr(cls, 'MAIL_USERNAME', None) is not None:
            credentials = (cls.MAIL_USERNAME, cls.MAIL_PASSWORD)
            if getattr(cls, 'MAIL_USE_TLS', None):
                secure = ()
        mail_handler = SMTPHandler(
            mailhost=(cls.MAIL_SERVER, cls.MAIL_PORT),
            fromaddr=cls.FLASKY_MAIL_SENDER,
            toaddrs=cls.FLASKY_ADMIN,
            subject=cls.FLASKY_MAIL_SUBJECT_PREFIX + ' Application Error',
            credentials=credentials,
            secure=secure)
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,

    'default': DevelopmentConfig
}

