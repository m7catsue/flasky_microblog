# -*- coding: utf-8 -*-
from datetime import datetime
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from flask import current_app, request, url_for
from flask_login import UserMixin, AnonymousUserMixin
from markdown import markdown
import bleach
from . import db, login_manager                 # 从app文件夹中的__init__.py中导入, login_manager供装饰器使用
from app.exceptions import ValidationError      # cwd是flasky_social_blogging文件夹


class Permission:
    """使用不同权限组合定义角色的整体权限赋值(转为2进制,按位运算,管理员权限8个位上都为1);
    [不同类型用户的权限组合] 匿名用户: 0x00(0000 0000), 普通用户: 0x07(0000 0111),
                          协管员: 0x0f(0000 1111), 管理员: 0xff(1111 1111);
    [IMP] '0x'开头代表16进制: 0x01和0x02即为10进制数字1和2; '0b'开头代表2进制;
    0x01|0x02|0x04=0x07,先将16进制转为2进制,再进行'按位或运算'(参加运算的两个对象只要有一个为1，其值为1),2进制0111即为16进制0x07"""
    FOLLOW = 0x01
    COMMENT = 0x02
    WRITE_ARTICLES = 0x04
    MODERATE_COMMENTS = 0x08
    ADMINISTER = 0x80


class Follow(db.Model):
    """用户之间相互关注的关系"""
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'),  # follower_id是关注者/追随者
                            primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'),  # followed_id是被关注者/被追随者
                            primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)     # follow的时间戳


class Role(db.Model):
    """用户角色定义: 匿名用户: 0x00, 普通用户: 0x07, 协管员: 0x0f, 管理员: 0xff"""
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)

    users = db.relationship('User', backref='role', lazy='dynamic')  # 由User.role获得相应的Role实例;Role.users得到角色对应的所有User实例

    @staticmethod
    def insert_roles():
        """不直接创建新角色对象,而是通过角色名查找现有的角色,进行更新;仅当数据库中没有某个角色名时才会创建新角色;
        想要添加新角色,或者修改角色权限,修改roles字典,再运行函数即可"""
        roles = {
            'User': (Permission.FOLLOW |
                     Permission.COMMENT |
                     Permission.WRITE_ARTICLES, True),
            'Moderator': (Permission.FOLLOW |
                          Permission.COMMENT |
                          Permission.WRITE_ARTICLES |
                          Permission.MODERATE_COMMENTS, False),
            'Administrator': (0xff, False)
        }
        for r in roles:                                  # r为dictionary的key(str)
            role = Role.query.filter_by(name=r).first()  # name是指的角色名(Role.name)
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name


class User(UserMixin, db.Model):
    """User表中保存password_hash; User.password只可写(赋值),不可读
    UserMixin父类中设定方法: is_authenticated返回True; is_active返回True; is_anonymous返回False;
    User.followed表示该用户正在关注的用户;User.followers表示该用户的关注者"""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    password_hash = db.Column(db.String(128))
    confirmed = db.Column(db.Boolean, default=False)
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    avatar_hash = db.Column(db.String(32))

    posts = db.relationship('Post', backref='author', lazy='dynamic')           # 由Post.author获得对应的User实例;User.posts得到用户的所有Post实例
    followed = db.relationship('Follow',
                               foreign_keys=[Follow.follower_id],               # [IMP] 这里foreign_key是指当前user.id在Follow模型中的foreign_key
                               backref=db.backref('follower', lazy='joined'),   # 为了消除外键间的歧义(2个外键),定义关系时须用可选参数foreign_keys指定的外键
                               lazy='dynamic',                                  # [IMP] backref()参数并不是指定这两个关系之间的引用关系,而是回引Follow模型
                               cascade='all, delete-orphan')                    # joined模式实现立即从关联查询结果中加载相关对象(list of instances)
    followers = db.relationship('Follow',                                       # dynamic模式:不会直接返回记录,返回可添加额外过滤器的查询对象
                                foreign_keys=[Follow.followed_id],              # cascade参数配置在父对象上执行的操作对相关对象的影响
                                backref=db.backref('followed', lazy='joined'),  # 'all, delete-orphan'表示启用所有默认层叠选项,且还要删除孤儿记录
                                lazy='dynamic',
                                cascade='all, delete-orphan')                   # 多对多关系定义为两个一对多关系:user.followed 和 user.followers
    comments = db.relationship('Comment', backref='author', lazy='dynamic')

    @staticmethod
    def generate_fake(count=100):
        """生成用于开发和测试的虚拟user数据"""
        from sqlalchemy.exc import IntegrityError
        from random import seed
        import forgery_py                                                       # 移植自Ruby

        seed()
        for i in range(count):
            u = User(email=forgery_py.internet.email_address(),
                     username=forgery_py.internet.user_name(True),
                     password=forgery_py.lorem_ipsum.word(),
                     confirmed=True,
                     name=forgery_py.name.full_name(),
                     location=forgery_py.address.city(),
                     about_me=forgery_py.lorem_ipsum.sentence(),
                     member_since=forgery_py.date.date(True))
            db.session.add(u)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()

    @staticmethod
    def add_self_follows():
        """更新现有用户:使现有用户follow自己,在其查看好友文章的时也显示自己的文章;
        [IMP] 通过创建函数来更新已部署程序中的数据库"""
        for user in User.query.all():
            if not user.is_following(user):
                user.follow(user)                                          # user.follow()方法会创建新的Follow实例
                db.session.add(user)
                db.session.commit()

    def __init__(self, **kwargs):
        """只要设置变量中的FLASKY_ADMIN的邮件地址出现在注册请求中,即设为管理员角色;
        若创建基类对象后还未定义角色,则根据邮件地址决定将其设为管理员或者默认角色"""
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['FLASKY_ADMIN']:
                self.role = Role.query.filter_by(permissions=0xff).first()  # 通过管理员权(0xff)限查询admin角色,设为管理员角色
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()      # 设为普通用户角色(default=True)
        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = hashlib.md5(                                 # 创建User实例时
                self.email.encode('utf-8')).hexdigest()                     # 为email地址生成对应MD5散列值 [IMP]
        self.followed.append(Follow(followed=self))                         # self.follow(self);为在首页查看好友文章时也显示自己的文章

    @property
    def password(self):
        """password不可读"""
        raise AttributeError('Password is not a readable attribute.')

    @password.setter
    def password(self, password):
        """写入password信息时(some_user.password='pswd_str'),保存password_hash而不是password明文"""
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        """验证密码:对比散列值/哈希值"""
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self, expiration=3600):
        """生成用于<确认>的token(令牌字符串)"""
        s = Serializer(current_app.config['SECRET_KEY'], expiration)  # 需要用到secret_key
        return s.dumps({'confirm': self.id})  # 返回token(令牌字符串)

    def confirm(self, token):
        """<确认>函数:加载token并验证"""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:                              # 无法加载token/加载无效的token,返回False
            return False
        if data.get('confirm') != self.id:   # 加载token成功, 但不是所需验证的user_id, 返回Flase
            return False
        self.confirmed = True                # 加载token且验证成功,写入数据库confirmed=True
        db.session.add(self)
        db.session.commit()
        return True

    def generate_reset_token(self, expiration=3600):
        """生成用于<重置密码>的token(令牌字符串)"""
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'reset': self.id})

    def reset_password(self, token, new_password):
        """<重置密码>:加载token并验证"""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:                               # 无法加载token/加载无效的token,返回False
            return False
        if data.get('reset') != self.id:      # 加载token成功, 但不是所需验证的user_id, 返回Flase
            return False
        self.password = new_password          # 加载token且验证成功,将新密码写入数据库
        db.session.add(self)
        db.session.commit()
        return True

    def generate_email_change_token(self, new_email, expiration=3600):
        """生成用于<改变邮箱>的token(令牌字符串)"""
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'change_email': self.id, 'new_email': new_email})

    def change_email(self, token):
        """<改变邮箱>:加载token并验证;
        改变邮箱地址之后,重新生成用户的MD5散列值/哈希值(avatar_hash)"""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:                                            # 无法加载token/加载无效的token,返回False
            return False
        if data.get('change_email') != self.id:            # 加载token成功, 但不是所需验证的user_id, 返回Flase
            return False
        new_email = data.get('new_email')
        if not new_email:                                  # new_email为空,返回False
            return False
        if self.query.filter_by(email=new_email).first():  # 数据库中new_email已存在:已有其他用户注册该email,返回False
            return False
        self.email = new_email                             # 加载token且验证成功,将new_email写入数据库
        self.avatar_hash = hashlib.md5(
            self.email.encode('utf-8')).hexdigest()        # 改变email后,重新生成avatar_hash
        db.session.add(self)
        db.session.commit()
        return True

    def can(self, permissions):
        """can()方法在请求和赋予角色这两种权限之间进行位与操作;
        若角色中包含请求的所有权限位,则返回True,表示允许用户执行此项操作"""
        return self.role is not None and \
            (self.role.permissions & permissions) == permissions  # [IMP] 按位与运算: 两位同时为1，结果才为1，否则为0

    def is_administrator(self):
        """检查管理员权限"""
        return self.can(Permission.ADMINISTER)

    def ping(self):
        """每次收到用户请求时调用ping方法;
        更新数据库中用户的最后在线时间"""
        self.last_seen = datetime.utcnow()
        db.session.add(self)
        db.session.commit()

    def gravatar(self, size=100, default='identicon', rating='g'):
        """构建Gravatar url;具体参数解释参见Flask Web Development
        size(s):图片大小,单位为像素;rating(r):图片级别;default(d):没有注册gravatar服务的用户的默认图片生成方式"""
        if request.is_secure:
            url = 'https://cn.gravatar.com/avatar'
        else:
            url = 'http://cn.gravatar.com/avatar'
        hash = self.avatar_hash or hashlib.md5(
            self.email.encode('utf-8')).hexdigest()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
            url=url, hash=hash, size=size, default=default, rating=rating)

    def follow(self, user):
        """当前用户关注某用户;将Follow实例插入Follow关联表"""
        if not self.is_following(user):
            f = Follow(follower=self, followed=user)
            db.session.add(f)
            db.session.commit()

    def unfollow(self, user):
        """当前用户取消关注某用户;
        self.followed.filter_by(followed_id=user.id).first()返回Follow类实例 [IMP];
        current_user.id为Follow.follower_id(db.relationship()中的外键),user.id为Follow.followed_id"""
        f = self.followed.filter_by(followed_id=user.id).first()  # lazy='dynamic'返回可加额外过滤器的查询对象
        if f:
            db.session.delete(f)
            db.session.commit()

    def is_following(self, user):
        """检查当前用户是否正在关注某用户"""
        return self.followed.filter_by(                           # lazy='dynamic'返回可加额外过滤器的查询对象
            followed_id=user.id).first() is not None

    def is_followed_by(self, user):
        """检查当前用户是否正在被某用户关注"""
        return self.followers.filter_by(
            follower_id=user.id).first() is not None              # lazy='dynamic'返回可加额外过滤器的查询对象

    @property
    def followed_posts(self):
        """用户所关注的其他用户的博客文章(用于主页显示)"""
        return Post.query.join(Follow, Follow.followed_id == Post.author_id)\
            .filter(Follow.follower_id == self.id)                # SQLAlchemy会先收集所有的过滤器,然后再以最高效的方式生成查询

    def to_json(self):
        """将用户User实例转为JSON格式;
        _external=True: return fully qualified URLs instead of relative URLs;
        [IMP] 为保护隐私,用户的email和role没有加入响应"""
        json_user = {
            'url': url_for('api.get_user', id=self.id, _external=True),            # api蓝本的get_user视图函数
            'username': self.username,
            'member_since': self.member_since,
            'last_seen': self.last_seen,
            'posts': url_for('api.get_user_posts', id=self.id, _external=True),    # api蓝本中的get_user_posts视图函数
            'followed_posts': url_for('api.get_user_followed_posts', id=self.id, _external=True),
            'post_count': self.posts.count()
        }
        return json_user

    def generate_auth_token(self, expiration):
        """生成用于<API请求>的auth token;
        不需要最后encode(),否则会报错"""
        s = Serializer(current_app.config['SECRET_KEY'],
                       expires_in=expiration)
        return s.dumps({'id': self.id})

    @staticmethod
    def verify_auth_token(token):
        """验证<API请求>的auth token; the user will be known only after the token is decoded;
        [IMP] query.get(id): return an instance based on the given <primary key> identifier, or None if not found"""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:                                                   # 加载token异常,返回None
            return None
        return User.query.get(data['id'])                         # 获得user实例或者返回None

    def __repr__(self):
        return '<User %r>' % self.username


class AnonymousUser(AnonymousUserMixin):
    """未登录用户"""
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False


login_manager.anonymous_user = AnonymousUser  # 关联AnonymousUser模型和flask-login;可对未登录用户进行权限检查


@login_manager.user_loader
def load_user(user_id):
    """回调函数,使用user_id加载用户对象;
    Flask-login requires a “user_loader” function which, given a user ID, returns the associated user object;
    [IMP] 关联flask-login和flask-sqlalchemy,使得flask-login所提供的current_user可以取到对应User模型中数据;
    [IMP] 在flask-login中用户id永远是unicode字符串,将用户id发送给flask-sqlalchemy之前须转换为整型,否则会报错"""
    return User.query.get(int(user_id))


class Post(db.Model):
    """用户发表的博客文章;
    博客文章的html代码缓存在body_html字段中,避免重复转换"""
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    comments = db.relationship('Comment', backref='post', lazy='dynamic')

    @staticmethod
    def generate_fake(count=100):
        """生成用于开发和测试的虚拟post数据"""
        from random import seed, randint
        import forgery_py

        seed()
        user_count = User.query.count()
        for i in range(count):
            u = User.query.offset(randint(0, user_count - 1)).first()
            p = Post(body=forgery_py.lorem_ipsum.sentences(randint(1, 5)),
                     timestamp=forgery_py.date.date(True),
                     author=u)
            db.session.add(p)
            db.session.commit()

    @staticmethod
    def on_changed_body(target, value, oldvalue, initator):
        """将body中的Markdown文本转换为HTML文本;
        在body文本改变时自动调用本方法;target为Post实例,value为Post.body的新值"""
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                        'h1', 'h2', 'h3', 'p']
        target.body_html = bleach.linkify(bleach.clean(    # (1)markdown函数初步将Markdown文本转换为HTML;
            markdown(value, output_format='html'),         # (2)clean()函数删除不在白名单中的标签;
            tags=allowed_tags, strip=True))                # (3)linkify()函数将纯文本中的url转换成适当的<a>链接

    def to_json(self):
        """将博客文章Post实例转为JSON格式;
        _external=True: return fully qualified URLs instead of relative URLs"""
        json_post = {
            'url': url_for('api.get_post', id=self.id, _external=True),             # api蓝本中的get_post视图函数
            'body': self.body,
            'body_html': self.body_html,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id, _external=True),   # api蓝本中的get_user视图函数
            'comments': url_for('api.get_post_comments', id=self.id, _external=True),
            'comment_count': self.comments.count()
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        """从JSON格式数据创建一篇博客文章:客户端只提交body部分"""
        body = json_post.get('body')
        if body is None or body == '':
            raise ValidationError('post does not have a body')  # 由api模块中的error handler处理(400, bad_request) [IMP]
        return Post(body=body)


# on_changed_body函数注册在Post.body字段上,是SQLAlchemy"set"事件的监听程序,
# 这意味着只要这个类实例的body字段设了新值(receive a scalar set event;某类的某个属性进行set操作),函数就会自动被调用
db.event.listen(Post.body, 'set', Post.on_changed_body)


class Comment(db.Model):
    """用户对博客文章的评论;保存评论的html代码的缓存"""
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    disabled = db.Column(db.Boolean)                       # 布尔型变量,表示该评论是否被管理员屏蔽
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        """在body文本改变时,自动调用本方法,将body中的Markdown文本转换为HTML文本"""
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'code', 'em', 'i',  # Comment比post更短,可使用的HTML tag限制更多
                        'strong']
        target.body_html = bleach.linkify(bleach.clean(
            markdown(value, output_format='html'),
            tags=allowed_tags, strip=True))

    def to_json(self):
        """将Comment实例转为JSON格式"""
        json_comment = {
            'url': url_for('api.get_comment', id=self.id, _external=True),
            'post': url_for('api.get_post', id=self.post_id, _external=True),
            'body': self.body,
            'body_html': self.body_html,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),
        }
        return json_comment

    @staticmethod
    def from_json(json_comment):
        """从JSON格式数据创建comment: 客户端只提交body部分"""
        body = json_comment.get('body')
        if body is None or body == '':
            raise ValidationError('comment does not have a body')
        return Comment(body=body)


db.event.listen(Comment.body, 'set', Comment.on_changed_body)

