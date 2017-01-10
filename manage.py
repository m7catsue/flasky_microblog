# -*- coding: utf-8 -*-
# [1] sys.executable: A string giving the absolute path of the executable binary for the Python interpreter,
#                    on systems where this makes sense.
# [2] os.execvp(file, args): executes a new program, replacing the current process;  [os.exec*] [IMP]
#                            'v': number of command-line arguments is variable;
#                            'p': use the PATH environment variable to locate the program file.

import os                                                  # 覆盖检测(检查测试的代码覆盖率)的设置
COV = None
if os.environ.get('FLASKY_COVERAGE'):                      # 若未设置环境变量,返回None,不执行if下面的语句 (COV为None)
    import coverage
    COV = coverage.coverage(branch=True, include='app/*')  # 参数branch:检查条件语句的True和False分支是否都执行;
    COV.start()                                            # 参数include:设置进行覆盖检测的范围
                                                           # 仅对app文件夹中的代码;若不指定include则所有代码都会包含进来,包括venv和tests等

import subprocess
from app import create_app, db                             # relative import:从app文件夹中的__init__.py中导入create_app, db
from app.models import User, Role, Permission, Post, Comment
from flask_script import Manager, Shell
from flask_migrate import Migrate, MigrateCommand

app = create_app(os.getenv('FLASK_CONFIG') or 'default')   # 通过工厂函数创建app,
manager = Manager(app)                                     # 之后初始化Flask-Script, Flask-Migrate和为Python shell定义的上下文
migrate = Migrate(app, db)


def make_shell_context():
    return dict(app=app, db=db, User=User,                 # [IMP] 新增加数据库模型后,需在此加入新模型
                Role=Role, Permission=Permission,
                Post=Post, Comment=Comment)
manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)                  # MigrateCommand类连接flask-migrate和flask-script的manager对象


@manager.command
def test(coverage=False):                                       # 函数名(test)即是命令名:python manage.py test进行单元测试;或python manage.py test --coverage
    """Run the unit tests;包括执行覆盖检测"""
    if coverage and not os.environ.get('FLASKY_COVERAGE'):      # cmd-line参数传入coverage参数,但环境变量未设置
        import sys                                              # 设置FLASKY-COVERAGE环境变量;重新启动manage.py;此时COV会依照脚本顶端进行设置
        os.environ['FLASKY_COVERAGE'] = '1'
        if sys.platform == 'win32':
            # 若传入subprocess.Popen()的args是一个seq,则默认seq中的第一个item为'运行的程序';若args是string,则依据platform执行之
            child = subprocess.Popen([sys.executable, os.path.realpath(__file__), 'test', '--coverage'])
            child.wait()  # 等待子进程执行完成再继续执行父进程 [IMP]
        else:                                                       # executes a new program, replacing the current process
            os.execvp(sys.executable, [sys.executable] + sys.argv)  # 在windows无法运行,路径名中有空格

    import unittest
    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)
    if COV:
        COV.stop()                                              # stop measuring code coverage; COV.start()在脚本顶端
        COV.save()                                              # save the collected coverage data to the data file
        print('Coverage Summary:')
        COV.report()                                            # write a summary report to file
        basedir = os.path.abspath(os.path.dirname(__file__))
        covdir = os.path.join(basedir, 'tmp/coverage')
        COV.html_report(directory=covdir)                       # generate an HTML report.The HTML is written to directory
        print('HTML version: file://%s/index.html' % covdir)    # the file “index.html” is the overview starting point, with links to more detailed pages for individual modules
        COV.erase()                                             # erase previously-collected coverage data


@manager.command
def profile(length=25, profile_dir=None):                       # 函数名(profile)即是命令名:python manage.py profile; python manage.py profile --length 50
    """Start the application under the code profiler;
    在请求分析器的监视下运行程序:记录调用的函数及消耗的时间,报告最慢的函数;
    --length选项可以修改报告中显示的函数数量;若指定--profile_dir选项,则每条请求的分析数据会保存到指定目录下"""
    from werkzeug.contrib.profiler import ProfilerMiddleware
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[length],
                                      profile_dir=profile_dir)
    app.run()


@manager.command
def deploy():
    """执行部署命令:每次安装或升级程序时运行deploy命令"""
    from flask_migrate import upgrade
    from app.models import Role, User
    upgrade()                          # migrate database to latest revision
    Role.insert_roles()                # create user roles
    User.add_self_follows()            # create self-follows for all users


if __name__ == '__main__':
    manager.run()

