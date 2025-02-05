from flask import Blueprint, request, jsonify
from models import db, Post

api_bp = Blueprint("api", __name__)

@api_bp.route("/posts", methods=["GET", "POST"])
def handle_posts():
    if request.method == "POST":
        data = request.json
        new_post = Post(title=data["title"], content=data["content"], user_id=data["user_id"])
        db.session.add(new_post)
        db.session.commit()
        return jsonify({"message": "Post created"}), 201

    posts = Post.query.all()
    return jsonify([{"id": p.id, "title": p.title, "content": p.content} for p in posts])
