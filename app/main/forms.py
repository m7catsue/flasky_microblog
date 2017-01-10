# -*- coding: utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Email, Regexp
from wtforms import ValidationError
from flask_pagedown.fields import PageDownField  # PageDownField和TextAreaField接口一致:将多行文本控件转换成Markdown富文本编辑器
from ..models import Role, User


class EditProfileForm(FlaskForm):
    """用户编辑个人资料的表单"""
    name = StringField('Real name', validators=[Length(0, 64)])
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')


class EditProfileAdminForm(FlaskForm):
    """管理员编辑用户资料的表单"""
    email = StringField('Email', validators=[DataRequired(), Length(1, 64), Email()])
    username = StringField('Username', validators=[DataRequired(), Length(1, 64),
                                                   Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                                                    'Usernames must have only letters, '
                                                    'numbers, dots or underscores')])
    confirmed = BooleanField('Confirmed')
    role = SelectField('Role', coerce=int)                       # SelectField实例须在其choices属性中设置各选项(list of tuples)
    name = StringField('Real name', validators=[Length(0, 64)])  # coerce=int: role.choices中元组的标识符是角色id(int)
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')

    def __init__(self, user, *args, **kwargs):
        super(EditProfileAdminForm, self).__init__(*args, **kwargs)
        self.role.choices = [(role.id, role.name)                # [IMP] 为SelectField实例(role)设置各选项(role.choices)
                             for role in Role.query.order_by(Role.name).all()]
        self.user = user                                         # user是传入EditProfileAdminForm的参数

    def validate_email(self, field):  # custom validator
        """验证用户email:管理员更改用户email时不能使用其他用户已经注册过的email"""
        if field.data != self.user.email and \
                User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self, field):  # custom validator
        """验证用户username:管理员更改用户username时不能使用其他用户已经注册过的username"""
        if field.data != self.user.username and \
                User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already in use.')


class PostForm(FlaskForm):
    """发表博客文章的表单;
    [IMP] PageDownField和TextAreaField接口一致:将多行文本控件转换成Markdown富文本编辑器"""
    body = PageDownField("What's on your mind? (Markdown文本预览已启用)", validators=[DataRequired()])
    submit = SubmitField('Submit')


class CommentForm(FlaskForm):
    """对博客文章发表评论的表单"""
    body = StringField('Enter your comment', validators=[DataRequired()])
    submit = SubmitField('Submit')


