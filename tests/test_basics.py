# -*- coding: utf-8 -*-
import unittest
from flask import current_app
from app import create_app, db  # 从app文件夹中的__init__.py中导入


class BasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()  # 激活程序上下文,确保能再测试中使用current_app,像普通请求一样
        db.create_all()          # 创建新的测试数据库(测试数据库位置在'测试类'中定义)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_app_exists(self):
        self.assertFalse(current_app is None)

    def test_app_is_testing(self):
        self.assertTrue(current_app.config['TESTING'])
