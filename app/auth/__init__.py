# -*- coding: utf-8 -*-
from flask import Blueprint

auth = Blueprint('auth', __name__)

from . import views
# relative import: 从当前文件夹(auth)中导入views.py中的全部内容
