import ssl
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///social_platform.db'
app.config['JWT_SECRET_KEY'] = 'your_secret_key'

# Ensure SSL module is available
try:
    _ = ssl.SSLContext()
except AttributeError:
    raise ImportError("Your Python environment lacks SSL support. Ensure OpenSSL is properly installed.")

# Initialize extensions
db = SQLAlchemy(app)
ma = Marshmallow(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')  # Admin or user
    posts = db.relationship('Post', backref='author', lazy=True)

# Post Model
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('Like', backref='post', lazy=True, cascade="all, delete")

# Like Model (Many-to-Many Relationship)
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# User Schema
class UserSchema(ma.SQLAlchemySchema):
    class Meta:
        model = User
        load_instance = True

# Post Schema
class PostSchema(ma.SQLAlchemySchema):
    class Meta:
        model = Post
        load_instance = True

# Like Schema
class LikeSchema(ma.SQLAlchemySchema):
    class Meta:
        model = Like
        load_instance = True

user_schema = UserSchema()
users_schema = UserSchema(many=True)
post_schema = PostSchema()
posts_schema = PostSchema(many=True)
like_schema = LikeSchema()

# Register User
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already registered'}), 400
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    new_user = User(username=data['username'], email=data['email'], password_hash=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return user_schema.jsonify(new_user)

# Login User
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if user and bcrypt.check_password_hash(user.password_hash, data['password']):
        access_token = create_access_token(identity={'id': user.id, 'role': user.role})
        return jsonify({'access_token': access_token})
    return jsonify({'message': 'Invalid credentials'}), 401

# Get Users (Admin Only)
@app.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    identity = get_jwt_identity()
    if identity['role'] != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    users = User.query.all()
    return jsonify(users_schema.dump(users))

# Create Post
@app.route('/posts', methods=['POST'])
@jwt_required()
def create_post():
    data = request.get_json()
    user_id = get_jwt_identity()['id']
    new_post = Post(content=data['content'], user_id=user_id)
    db.session.add(new_post)
    db.session.commit()
    return post_schema.jsonify(new_post)

# Get Posts
@app.route('/posts', methods=['GET'])
def get_posts():
    posts = Post.query.all()
    return jsonify(posts_schema.dump(posts))

# Update Post (Only Author)
@app.route('/posts/<int:post_id>', methods=['PATCH'])
@jwt_required()
def update_post(post_id):
    data = request.get_json()
    user_id = get_jwt_identity()['id']
    post = Post.query.get_or_404(post_id)
    if post.user_id != user_id:
        return jsonify({'message': 'Unauthorized'}), 403
    post.content = data.get('content', post.content)
    db.session.commit()
    return post_schema.jsonify(post)

# Delete Post (Only Author or Admin)
@app.route('/posts/<int:post_id>', methods=['DELETE'])
@jwt_required()
def delete_post(post_id):
    identity = get_jwt_identity()
    post = Post.query.get_or_404(post_id)
    if post.user_id != identity['id'] and identity['role'] != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Post deleted'})

# Like a Post
@app.route('/posts/<int:post_id>/like', methods=['POST'])
@jwt_required()
def like_post(post_id):
    user_id = get_jwt_identity()['id']
    if Like.query.filter_by(user_id=user_id, post_id=post_id).first():
        return jsonify({'message': 'Already liked'}), 400
    like = Like(user_id=user_id, post_id=post_id)
    db.session.add(like)
    db.session.commit()
    return like_schema.jsonify(like)

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)
