from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.forum_comment import ForumComment
from app.models.forum_post import ForumPost
from app.services.audit_service import log_event
from app.utils.authz import min_role_required
from app.utils.roles import ROLE_SUPERADMIN, is_admin_role, normalize_role

forum_bp = Blueprint("forum", __name__, url_prefix="/forum")
FORUM_CATEGORIES = ("GENERAL", "LABORATORIOS", "MATERIALES", "SOFTWARE")


def _is_admin() -> bool:
    return is_admin_role(getattr(current_user, "role", None))


def _is_superadmin() -> bool:
    return normalize_role(getattr(current_user, "role", None)) == ROLE_SUPERADMIN


def _author_label(user, is_anonymous: bool) -> str:
    if is_anonymous and not _is_superadmin():
        return "Anónimo"
    if not user:
        return "N/A"
    full_name = (getattr(user, "full_name", "") or "").strip()
    matricula = (getattr(user, "matricula", "") or "").strip()
    if full_name and matricula:
        return f"{full_name} ({matricula})"
    return full_name or user.email


def _format_forum_datetime(value) -> str:
    if not value:
        return "-"
    return value.strftime("%d/%m/%Y %H:%M")

def _author_tone_class(user, is_anonymous: bool) -> str:
    if is_anonymous and not _is_superadmin():
        seed = "anon"
    else:
        seed = (getattr(user, "email", None) or getattr(user, "name", None) or str(getattr(user, "id", "0"))).strip().lower()
    if not seed:
        seed = "unknown"
    tone_index = (sum(ord(ch) for ch in seed) % 6) + 1
    return f"commenter-tone-{tone_index}"


def _can_edit_post(post: ForumPost) -> bool:
    if not post or not getattr(current_user, "is_authenticated", False):
        return False
    return (post.author_id == current_user.id) or _is_admin()


@forum_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")
def forum_home():
    selected_category = (request.args.get("category") or "").strip().upper()
    query = ForumPost.query.options(joinedload(ForumPost.author)).order_by(ForumPost.created_at.desc())
    if not _is_admin():
        query = query.filter(ForumPost.is_hidden.is_(False))
    if selected_category in FORUM_CATEGORIES:
        query = query.filter(ForumPost.category == selected_category)

    posts = query.limit(200).all()
    post_ids = [post.id for post in posts]
    comment_counts: dict[int, int] = {}
    comment_previews_by_post: dict[int, list[ForumComment]] = {}
    if post_ids:
        comments_query = (
            db.session.query(ForumComment.post_id, func.count(ForumComment.id))
            .filter(ForumComment.post_id.in_(post_ids))
        )
        if not _is_admin():
            comments_query = comments_query.filter(ForumComment.is_hidden.is_(False))
        comment_counts = {post_id: total for post_id, total in comments_query.group_by(ForumComment.post_id).all()}

        ranked_comments = (
            db.session.query(
                ForumComment.id.label("comment_id"),
                ForumComment.post_id.label("post_id"),
                func.row_number().over(
                    partition_by=ForumComment.post_id,
                    order_by=ForumComment.created_at.desc(),
                ).label("rn"),
            )
            .filter(ForumComment.post_id.in_(post_ids))
        )
        if not _is_admin():
            ranked_comments = ranked_comments.filter(ForumComment.is_hidden.is_(False))

        ranked_subq = ranked_comments.subquery()
        preview_comments = (
            ForumComment.query
            .options(joinedload(ForumComment.author))
            .join(ranked_subq, ForumComment.id == ranked_subq.c.comment_id)
            .filter(ranked_subq.c.rn <= 5)
            .order_by(ForumComment.post_id.asc(), ForumComment.created_at.desc())
            .all()
        )
        for comment in preview_comments:
            comment_previews_by_post.setdefault(comment.post_id, []).append(comment)

    return render_template(
        "forum/list.html",
        posts=posts,
        comment_counts=comment_counts,
        comment_previews_by_post=comment_previews_by_post,
        categories=FORUM_CATEGORIES,
        selected_category=selected_category,
        is_admin=_is_admin(),
        is_superadmin=_is_superadmin(),
        author_label_fn=_author_label,
        author_tone_fn=_author_tone_class,
        format_forum_datetime=_format_forum_datetime,
        active_page="forum",
    )


@forum_bp.route("/new", methods=["GET", "POST"])
@min_role_required("STUDENT")
def create_post():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        category = (request.form.get("category") or "GENERAL").strip().upper()
        is_anonymous = False

        if not title:
            flash("El título es obligatorio.", "error")
            return redirect(url_for("forum.create_post"))

        if len(title) > 180:
            flash("El título excede el máximo de 180 caracteres.", "error")
            return redirect(url_for("forum.create_post"))

        if not content:
            flash("El contenido es obligatorio.", "error")
            return redirect(url_for("forum.create_post"))

        if category not in FORUM_CATEGORIES:
            category = "GENERAL"

        post = ForumPost(
            author_id=current_user.id,
            title=title,
            content=content,
            category=category,
            is_anonymous=is_anonymous,
            is_hidden=False,
        )
        db.session.add(post)
        db.session.flush()
        log_event(
            module="FORUM",
            action="FORUM_POST_CREATED",
            user_id=current_user.id,
            entity_label=f"ForumPost #{post.id}",
            description=f"Publicación creada en categoría {post.category}",
            metadata={"post_id": post.id, "anonymous": post.is_anonymous},
        )
        db.session.commit()

        flash("Publicación creada.", "success")
        return redirect(url_for("forum.post_detail", post_id=post.id))

    return render_template(
        "forum/new.html",
        categories=FORUM_CATEGORIES,
        format_forum_datetime=_format_forum_datetime,
        active_page="forum",
    )


@forum_bp.route("/<int:post_id>", methods=["GET", "POST"])
@min_role_required("STUDENT")
def post_detail(post_id: int):
    post = (
        ForumPost.query
        .options(
            joinedload(ForumPost.author),
            joinedload(ForumPost.comments).joinedload(ForumComment.author),
        )
        .filter(ForumPost.id == post_id)
        .first_or_404()
    )

    if post.is_hidden and not _is_admin():
        flash("La publicación no está disponible.", "error")
        return redirect(url_for("forum.forum_home"))

    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        is_anonymous = False
        if not content:
            flash("El comentario no puede estar vacío.", "error")
            return redirect(url_for("forum.post_detail", post_id=post.id))

        comment = ForumComment(
            post_id=post.id,
            author_id=current_user.id,
            content=content,
            is_anonymous=is_anonymous,
            is_hidden=False,
        )
        db.session.add(comment)
        db.session.flush()
        log_event(
            module="FORUM",
            action="FORUM_COMMENT_CREATED",
            user_id=current_user.id,
            entity_label=f"ForumComment #{comment.id}",
            description=f"Comentario creado en publicación #{post.id}",
            metadata={"post_id": post.id, "comment_id": comment.id, "anonymous": comment.is_anonymous},
        )
        db.session.commit()

        flash("Comentario publicado.", "success")
        return redirect(url_for("forum.post_detail", post_id=post.id))

    comments_query = (
        ForumComment.query
        .options(joinedload(ForumComment.author))
        .filter(ForumComment.post_id == post.id)
        .order_by(ForumComment.created_at.asc())
    )
    if not _is_admin():
        comments_query = comments_query.filter(ForumComment.is_hidden.is_(False))
    comments = comments_query.all()

    return render_template(
        "forum/detail.html",
        post=post,
        comments=comments,
        is_admin=_is_admin(),
        can_edit_post=_can_edit_post(post),
        is_superadmin=_is_superadmin(),
        author_label_fn=_author_label,
        author_tone_fn=_author_tone_class,
        format_forum_datetime=_format_forum_datetime,
        active_page="forum",
    )


@forum_bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@min_role_required("STUDENT")
def edit_post(post_id: int):
    post = ForumPost.query.get_or_404(post_id)

    if not _can_edit_post(post):
        flash("No tienes permiso para editar esta publicación.", "error")
        return redirect(url_for("forum.post_detail", post_id=post.id))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        category = (request.form.get("category") or post.category).strip().upper()

        if not title:
            flash("El título es obligatorio.", "error")
            return redirect(url_for("forum.edit_post", post_id=post.id))

        if len(title) > 180:
            flash("El título excede el máximo de 180 caracteres.", "error")
            return redirect(url_for("forum.edit_post", post_id=post.id))

        if not content:
            flash("El contenido es obligatorio.", "error")
            return redirect(url_for("forum.edit_post", post_id=post.id))

        if category not in FORUM_CATEGORIES:
            category = "GENERAL"

        post.title = title
        post.content = content
        post.category = category

        log_event(
            module="FORUM",
            action="FORUM_POST_UPDATED",
            user_id=current_user.id,
            entity_label=f"ForumPost #{post.id}",
            description=f"Publicación editada #{post.id}",
            metadata={"post_id": post.id, "edited_by": current_user.id},
        )
        db.session.commit()

        flash("Publicación actualizada.", "success")
        return redirect(url_for("forum.post_detail", post_id=post.id))

    return render_template(
        "forum/edit.html",
        post=post,
        categories=FORUM_CATEGORIES,
        format_forum_datetime=_format_forum_datetime,
        active_page="forum",
    )


@forum_bp.route("/posts/<int:post_id>/toggle-hidden", methods=["POST"])
@min_role_required("ADMIN")
def toggle_post_hidden(post_id: int):
    post = ForumPost.query.get_or_404(post_id)
    post.is_hidden = not post.is_hidden
    post.hidden_by = current_user.id if post.is_hidden else None
    post.hidden_at = db.func.now() if post.is_hidden else None
    log_event(
        module="FORUM",
        action="FORUM_POST_MODERATED",
        user_id=current_user.id,
        entity_label=f"ForumPost #{post.id}",
        description=f"Moderación de publicación #{post.id}",
        metadata={"post_id": post.id, "hidden": post.is_hidden},
    )
    db.session.commit()

    flash("Moderación de publicación actualizada.", "success")
    return redirect(url_for("forum.post_detail", post_id=post.id))


@forum_bp.route("/comments/<int:comment_id>/toggle-hidden", methods=["POST"])
@min_role_required("ADMIN")
def toggle_comment_hidden(comment_id: int):
    comment = ForumComment.query.get_or_404(comment_id)
    comment.is_hidden = not comment.is_hidden
    comment.hidden_by = current_user.id if comment.is_hidden else None
    comment.hidden_at = db.func.now() if comment.is_hidden else None
    log_event(
        module="FORUM",
        action="FORUM_COMMENT_MODERATED",
        user_id=current_user.id,
        entity_label=f"ForumComment #{comment.id}",
        description=f"Moderación de comentario #{comment.id}",
        metadata={"comment_id": comment.id, "post_id": comment.post_id, "hidden": comment.is_hidden},
    )
    db.session.commit()

    flash("Moderación de comentario actualizada.", "success")
    return redirect(url_for("forum.post_detail", post_id=comment.post_id))
