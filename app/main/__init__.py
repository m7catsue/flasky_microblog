# -*- coding: utf-8 -*-
from flask import Blueprint

main = Blueprint('main', __name__)

from . import views, errors
from ..models import Permission


# 把Permission类加入模板上下文;上下文处理器能让变量在所有模板中全局可访问
@main.app_context_processor
def inject_permissions():
    return dict(Permission=Permission)

# Context processors run before the template is rendered and have the ability to inject
# new values into the template context. A context processor is a function that returns a dictionary.
# The keys and values of this dictionary are then merged with the template context, for all templates in the app.

