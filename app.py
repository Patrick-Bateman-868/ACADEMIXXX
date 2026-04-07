
from flask import Flask, render_template, request, redirect, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
from sqlalchemy import text, inspect
import re

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key-change-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///students.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Войдите, чтобы открыть эту страницу."


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================
# Models
# ============================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    university = db.Column(db.String(100))
    country = db.Column(db.String(100))
    skills = db.Column(db.Text)
    goals = db.Column(db.Text)
    interests = db.Column(db.Text)
    links = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")  # pending, verified, banned
    role = db.Column(db.String(20), default="student")    # student, organizer, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_organizer(self):
        return self.role in ("organizer", "admin")

    @property
    def is_student(self):
        return self.role in ("student", "user")

    @property
    def role_display(self):
        return {"student": "Студент", "user": "Студент",
                "organizer": "Организатор", "admin": "Администратор"}.get(self.role, self.role)

    @property
    def role_badge(self):
        return {"student": "badge-secondary", "user": "badge-secondary",
                "organizer": "badge-gold", "admin": "badge-success"}.get(self.role, "badge-secondary")

    def __repr__(self):
        return f"<User {self.email}>"


class Opportunity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    requirements = db.Column(db.Text)
    category = db.Column(db.String(50), index=True)
    deadline = db.Column(db.String(50))
    source = db.Column(db.String(200))
    registration_link = db.Column(db.String(500))
    verified = db.Column(db.Boolean, default=False, index=True)
    views_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    creator = db.relationship("User", backref=db.backref("opportunities", lazy="dynamic"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Opportunity {self.title}>"


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    user_email = db.Column(db.String(120))
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunity.id"))
    status = db.Column(db.String(20), default="applied")
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)


class Group(db.Model):
    __tablename__ = "community_group"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, index=True)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    creator = db.relationship("User", backref=db.backref("owned_groups", lazy="dynamic"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GroupMember(db.Model):
    __tablename__ = "group_member"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("community_group.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("group_id", "user_id", name="uq_group_member"),)


# ============================================
# Decorators
# ============================================

def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Доступ запрещён. Требуются права администратора.", "error")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapped


def organizer_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_organizer:
            flash("Эта страница доступна только организаторам.", "error")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapped


# ============================================
# Auth Routes
# ============================================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("profile"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")

        if role not in ("student", "organizer"):
            role = "student"
        if not email or not name or not password:
            flash("Заполните все поля", "error")
            return render_template("signup.html")
        if "@" not in email or "." not in email.split("@")[-1]:
            flash("Введите корректный email", "error")
            return render_template("signup.html")
        if len(password) < 6:
            flash("Пароль должен быть не короче 6 символов", "error")
            return render_template("signup.html")
        if User.query.filter_by(email=email).first():
            flash("Пользователь с таким email уже зарегистрирован", "error")
            return render_template("signup.html")

        user = User(email=email, name=name, role=role)
        user.set_password(password)
        # First ever user → admin
        if User.query.count() == 0:
            user.role = "admin"
            user.status = "verified"

        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Регистрация успешна! Заполните профиль.", "success")
        return redirect(url_for("profile"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("profile"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Неверный email или пароль", "error")
            return render_template("login.html")
        if user.status == "banned":
            flash("Ваш аккаунт заблокирован. Обратитесь к администратору.", "error")
            return render_template("login.html")
        login_user(user)
        next_url = request.args.get("next") or url_for("profile")
        return redirect(next_url)
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    flash("Вы вышли из аккаунта", "info")
    return redirect(url_for("home"))


# ============================================
# Main Routes
# ============================================

@app.route("/")
def home():
    stats = {
        "total_users": User.query.count(),
        "verified_users": User.query.filter_by(status="verified").count(),
        "total_opportunities": Opportunity.query.count(),
        "verified_opportunities": Opportunity.query.filter_by(verified=True).count(),
        "total_applications": Application.query.count(),
    }
    return render_template("home.html", stats=stats)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Имя обязательно", "error")
            return render_template("profile.html", user=user)
        try:
            user.name = name
            user.university = request.form.get("university", "").strip() or None
            user.country = request.form.get("country", "").strip() or None
            user.skills = request.form.get("skills", "").strip() or None
            user.goals = request.form.get("goals", "").strip() or None
            user.interests = request.form.get("interests", "").strip() or None
            user.links = request.form.get("links", "").strip() or None
            db.session.commit()
            flash("Профиль сохранён", "success")
            if user.is_organizer:
                return redirect(url_for("organizer_dashboard"))
            return redirect(url_for("profiles"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка: {str(e)}", "error")
    return render_template("profile.html", user=user)


@app.route("/profiles")
def profiles():
    search_query = request.args.get("search", "").strip()
    country = request.args.get("country", "")
    university = request.args.get("university", "")
    page = request.args.get("page", 1, type=int)
    per_page = 12

    query = User.query.filter(User.status != "banned", User.role.in_(["student", "user"]))

    if search_query:
        query = query.filter(
            db.or_(
                User.name.contains(search_query),
                User.skills.contains(search_query),
                User.interests.contains(search_query)
            )
        )
    if country:
        query = query.filter(User.country == country)
    if university:
        query = query.filter(User.university.contains(university))

    query = query.order_by(
        db.case((User.status == "verified", 1), else_=2),
        User.created_at.desc()
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    countries = [c[0] for c in
                 db.session.query(User.country).distinct().filter(
                     User.country.isnot(None), User.country != "").all() if c[0]]

    return render_template(
        "profiles.html",
        students=pagination.items,
        pagination=pagination,
        countries=countries,
        universities=[],
        current_search=search_query,
        current_country=country,
        current_university=university
    )


@app.route("/profiles/<int:user_id>")
def profile_view(user_id):
    user = User.query.get_or_404(user_id)
    if user.status == "banned":
        return redirect(url_for("profiles"))
    return render_template("profile_view.html", user=user)


# ============================================
# Opportunities Routes
# ============================================

@app.route("/opportunities")
def opportunities():
    category = request.args.get("category", "")
    search_query = request.args.get("search", "").strip()
    verified_only = request.args.get("verified", "") == "on"
    with_deadline = request.args.get("deadline", "") == "on"
    sort = request.args.get("sort", "")
    page = request.args.get("page", 1, type=int)
    per_page = 12

    query = Opportunity.query
    if category:
        query = query.filter(Opportunity.category == category)
    if verified_only:
        query = query.filter(Opportunity.verified == True)
    if with_deadline:
        query = query.filter(Opportunity.deadline.isnot(None), Opportunity.deadline != "")
    if search_query:
        query = query.filter(db.or_(
            Opportunity.title.contains(search_query),
            Opportunity.description.contains(search_query),
            Opportunity.requirements.contains(search_query),
            Opportunity.source.contains(search_query)
        ))

    if sort == "deadline":
        query = query.order_by(Opportunity.deadline.asc(),
                               Opportunity.verified.desc(),
                               Opportunity.created_at.desc())
    else:
        query = query.order_by(Opportunity.verified.desc(), Opportunity.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    categories = [c[0] for c in db.session.query(Opportunity.category).distinct().all() if c[0]]

    return render_template(
        "opportunities.html",
        opportunities=pagination.items,
        pagination=pagination,
        categories=categories,
        current_category=category,
        current_search=search_query,
        verified_only=verified_only,
        with_deadline=with_deadline,
        sort=sort
    )


@app.route("/opportunity/<int:op_id>", methods=["GET", "POST"])
def opportunity_page(op_id):
    op = Opportunity.query.get_or_404(op_id)

    already_applied = False
    if current_user.is_authenticated:
        already_applied = Application.query.filter_by(
            user_email=current_user.email, opportunity_id=op.id
        ).first() is not None

    if request.method == "GET":
        op.views_count += 1
        db.session.commit()

    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Войдите, чтобы подать заявку", "error")
            return redirect(url_for("login", next=url_for("opportunity_page", op_id=op_id)))
        if already_applied:
            flash("Вы уже подали заявку на эту возможность", "warning")
        else:
            db.session.add(Application(
                user_id=current_user.id,
                user_email=current_user.email,
                opportunity_id=op.id
            ))
            db.session.commit()
            flash("Заявка успешно подана!", "success")
            return redirect("/opportunities")

    return render_template("opportunity_page.html", op=op, already_applied=already_applied)


@app.route("/add-opportunity", methods=["GET", "POST"])
@login_required
@organizer_required
def add_opportunity():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        if not title:
            flash("Название обязательно для заполнения", "error")
            return render_template("add_opportunity.html")
        if not category:
            flash("Выберите категорию", "error")
            return render_template("add_opportunity.html")
        try:
            op = Opportunity(
                title=title,
                description=request.form.get("description", "").strip() or None,
                requirements=request.form.get("requirements", "").strip() or None,
                category=category,
                deadline=request.form.get("deadline", "").strip() or None,
                source=request.form.get("source", "").strip() or None,
                registration_link=request.form.get("registration_link", "").strip() or None,
                created_by=current_user.id
            )
            db.session.add(op)
            db.session.commit()
            flash("Возможность добавлена и отправлена на модерацию!", "success")
            return redirect(url_for("organizer_dashboard"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при добавлении: {str(e)}", "error")
    return render_template("add_opportunity.html")


@app.route("/opportunity/<int:op_id>/edit", methods=["GET", "POST"])
@login_required
@organizer_required
def edit_opportunity(op_id):
    op = Opportunity.query.get_or_404(op_id)
    if not current_user.is_admin and op.created_by != current_user.id:
        flash("Вы можете редактировать только свои возможности", "error")
        return redirect(url_for("organizer_dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Название обязательно", "error")
            return render_template("add_opportunity.html", op=op, edit=True)
        try:
            op.title = title
            op.description = request.form.get("description", "").strip() or None
            op.category = request.form.get("category", "").strip()
            op.deadline = request.form.get("deadline", "").strip() or None
            op.requirements = request.form.get("requirements", "").strip() or None
            op.source = request.form.get("source", "").strip() or None
            op.registration_link = request.form.get("registration_link", "").strip() or None
            if not current_user.is_admin:
                op.verified = False  # re-review after edit
            db.session.commit()
            flash("Возможность обновлена", "success")
            return redirect(url_for("organizer_dashboard"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка: {str(e)}", "error")

    return render_template("add_opportunity.html", op=op, edit=True)


@app.route("/opportunity/<int:op_id>/delete", methods=["POST"])
@login_required
@organizer_required
def delete_opportunity(op_id):
    op = Opportunity.query.get_or_404(op_id)
    if not current_user.is_admin and op.created_by != current_user.id:
        flash("Вы можете удалять только свои возможности", "error")
        return redirect(url_for("organizer_dashboard"))
    title = op.title
    Application.query.filter_by(opportunity_id=op_id).delete()
    db.session.delete(op)
    db.session.commit()
    flash(f"Возможность «{title}» удалена", "success")
    return redirect(url_for("organizer_dashboard"))


# ============================================
# Organizer Routes
# ============================================

@app.route("/organizer/dashboard")
@login_required
@organizer_required
def organizer_dashboard():
    my_opportunities = Opportunity.query.filter_by(
        created_by=current_user.id).order_by(Opportunity.created_at.desc()).all()
    my_groups = Group.query.filter_by(
        created_by=current_user.id).order_by(Group.created_at.desc()).all()
    group_member_counts = {g.id: GroupMember.query.filter_by(group_id=g.id).count()
                           for g in my_groups}
    return render_template("organizer/dashboard.html",
                           my_opportunities=my_opportunities,
                           my_groups=my_groups,
                           group_member_counts=group_member_counts)


@app.route("/organizer/create-community", methods=["GET", "POST"])
@login_required
@organizer_required
def create_community():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        if not name:
            flash("Название обязательно", "error")
            return render_template("organizer/create_community.html")

        slug = re.sub(r"[^\w\s-]", "", name.lower())
        slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
        base_slug, counter = slug, 1
        while Group.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        try:
            group = Group(name=name, slug=slug,
                          description=description or None,
                          category=category or None,
                          created_by=current_user.id)
            db.session.add(group)
            db.session.flush()
            db.session.add(GroupMember(group_id=group.id, user_id=current_user.id))
            db.session.commit()
            flash(f"Сообщество «{name}» создано!", "success")
            return redirect(url_for("organizer_dashboard"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка: {str(e)}", "error")

    return render_template("organizer/create_community.html")


@app.route("/community/<int:group_id>/delete", methods=["POST"])
@login_required
def delete_community(group_id):
    group = Group.query.get_or_404(group_id)
    if not current_user.is_admin and group.created_by != current_user.id:
        flash("Нет доступа", "error")
        return redirect(url_for("community"))
    name = group.name
    GroupMember.query.filter_by(group_id=group_id).delete()
    db.session.delete(group)
    db.session.commit()
    flash(f"Сообщество «{name}» удалено", "success")
    if current_user.is_admin:
        return redirect(url_for("admin", tab="communities"))
    return redirect(url_for("organizer_dashboard"))


# ============================================
# Community Routes
# ============================================

@app.route("/community")
def community():
    groups = Group.query.order_by(Group.name).all()
    member_ids = set()
    member_counts = {}
    if current_user.is_authenticated:
        member_ids = {m.group_id for m in GroupMember.query.filter_by(user_id=current_user.id).all()}
    for g in groups:
        member_counts[g.id] = GroupMember.query.filter_by(group_id=g.id).count()
    return render_template("community.html", groups=groups, member_ids=member_ids,
                           member_counts=member_counts)


@app.route("/community/<int:group_id>")
def community_group(group_id):
    group = Group.query.get_or_404(group_id)
    members = GroupMember.query.filter_by(group_id=group_id).count()
    is_member = False
    if current_user.is_authenticated:
        is_member = GroupMember.query.filter_by(
            group_id=group_id, user_id=current_user.id).first() is not None
    return render_template("community_group.html", group=group,
                           members_count=members, is_member=is_member)


@app.route("/community/<int:group_id>/join", methods=["POST"])
@login_required
def community_join(group_id):
    group = Group.query.get_or_404(group_id)
    if GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first():
        flash("Вы уже в группе", "info")
    else:
        db.session.add(GroupMember(group_id=group_id, user_id=current_user.id))
        db.session.commit()
        flash(f"Вы вступили в группу «{group.name}»", "success")
    return redirect(url_for("community_group", group_id=group_id))


@app.route("/community/<int:group_id>/leave", methods=["POST"])
@login_required
def community_leave(group_id):
    GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).delete()
    db.session.commit()
    flash("Вы вышли из группы", "info")
    return redirect(url_for("community"))


# ============================================
# Admin Routes
# ============================================

@app.route("/admin")
@login_required
@admin_required
def admin():
    tab = request.args.get("tab", "overview")
    users = User.query.order_by(User.created_at.desc()).all()
    opportunities = Opportunity.query.order_by(Opportunity.created_at.desc()).all()
    groups = Group.query.order_by(Group.name).all()
    group_member_counts = {g.id: GroupMember.query.filter_by(group_id=g.id).count()
                           for g in groups}
    stats = {
        "total_users":           User.query.count(),
        "students":              User.query.filter(User.role.in_(["student", "user"])).count(),
        "organizers":            User.query.filter_by(role="organizer").count(),
        "admins":                User.query.filter_by(role="admin").count(),
        "pending_users":         User.query.filter_by(status="pending").count(),
        "banned_users":          User.query.filter_by(status="banned").count(),
        "total_opportunities":   Opportunity.query.count(),
        "pending_opportunities": Opportunity.query.filter_by(verified=False).count(),
        "verified_opportunities":Opportunity.query.filter_by(verified=True).count(),
        "total_groups":          Group.query.count(),
        "total_applications":    Application.query.count(),
    }
    return render_template("admin/index.html",
                           users=users, opportunities=opportunities,
                           groups=groups, stats=stats,
                           group_member_counts=group_member_counts,
                           active_tab=tab)


@app.route("/admin/user/<int:user_id>/verify", methods=["POST"])
@login_required
@admin_required
def admin_user_verify(user_id):
    u = User.query.get_or_404(user_id)
    u.status = "verified"
    db.session.commit()
    flash(f"Пользователь {u.name} верифицирован", "success")
    return redirect(url_for("admin", tab="users"))


@app.route("/admin/user/<int:user_id>/ban", methods=["POST"])
@login_required
@admin_required
def admin_user_ban(user_id):
    u = User.query.get_or_404(user_id)
    if u.is_admin:
        flash("Нельзя заблокировать администратора", "error")
        return redirect(url_for("admin", tab="users"))
    u.status = "banned"
    db.session.commit()
    flash(f"Пользователь {u.name} заблокирован", "success")
    return redirect(url_for("admin", tab="users"))


@app.route("/admin/user/<int:user_id>/unban", methods=["POST"])
@login_required
@admin_required
def admin_user_unban(user_id):
    u = User.query.get_or_404(user_id)
    u.status = "pending"
    db.session.commit()
    flash(f"Пользователь {u.name} разблокирован", "success")
    return redirect(url_for("admin", tab="users"))


@app.route("/admin/user/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def admin_user_role(user_id):
    u = User.query.get_or_404(user_id)
    new_role = request.form.get("role", "student")
    if new_role not in ("student", "organizer", "admin"):
        flash("Неверная роль", "error")
        return redirect(url_for("admin", tab="users"))
    if u.id == current_user.id and new_role != "admin":
        flash("Нельзя понизить свою роль администратора", "error")
        return redirect(url_for("admin", tab="users"))
    u.role = new_role
    db.session.commit()
    flash(f"Роль {u.name} изменена на «{u.role_display}»", "success")
    return redirect(url_for("admin", tab="users"))


@app.route("/admin/opportunity/<int:op_id>/verify", methods=["POST"])
@login_required
@admin_required
def admin_opportunity_verify(op_id):
    op = Opportunity.query.get_or_404(op_id)
    op.verified = True
    db.session.commit()
    flash(f"Возможность «{op.title}» верифицирована", "success")
    return redirect(url_for("admin", tab="opportunities"))


@app.route("/admin/opportunity/<int:op_id>/reject", methods=["POST"])
@login_required
@admin_required
def admin_opportunity_reject(op_id):
    op = Opportunity.query.get_or_404(op_id)
    op.verified = False
    db.session.commit()
    flash(f"Возможность «{op.title}» отклонена", "success")
    return redirect(url_for("admin", tab="opportunities"))


@app.route("/admin/opportunity/<int:op_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_opportunity_delete(op_id):
    op = Opportunity.query.get_or_404(op_id)
    title = op.title
    Application.query.filter_by(opportunity_id=op_id).delete()
    db.session.delete(op)
    db.session.commit()
    flash(f"Возможность «{title}» удалена", "success")
    return redirect(url_for("admin", tab="opportunities"))


@app.route("/admin/community/<int:group_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_community_delete(group_id):
    group = Group.query.get_or_404(group_id)
    name = group.name
    GroupMember.query.filter_by(group_id=group_id).delete()
    db.session.delete(group)
    db.session.commit()
    flash(f"Сообщество «{name}» удалено", "success")
    return redirect(url_for("admin", tab="communities"))


# ============================================
# Other
# ============================================

@app.route("/partners")
def partners():
    return render_template("partners.html")


@app.errorhandler(404)
def not_found_error(error):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template("errors/500.html"), 500


# ============================================
# Startup & DB Init
# ============================================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # ---- Schema migrations for SQLite ----
        try:
            inspector = inspect(db.engine)

            if "opportunity" in inspector.get_table_names():
                opp_cols = [c["name"] for c in inspector.get_columns("opportunity")]
                for col, sql in [
                    ("views_count",       "ALTER TABLE opportunity ADD COLUMN views_count INTEGER DEFAULT 0"),
                    ("created_at",        "ALTER TABLE opportunity ADD COLUMN created_at DATETIME"),
                    ("updated_at",        "ALTER TABLE opportunity ADD COLUMN updated_at DATETIME"),
                    ("requirements",      "ALTER TABLE opportunity ADD COLUMN requirements TEXT"),
                    ("source",            "ALTER TABLE opportunity ADD COLUMN source VARCHAR(200)"),
                    ("registration_link", "ALTER TABLE opportunity ADD COLUMN registration_link VARCHAR(500)"),
                    ("created_by",        "ALTER TABLE opportunity ADD COLUMN created_by INTEGER"),
                ]:
                    if col not in opp_cols:
                        with db.engine.connect() as conn:
                            conn.execute(text(sql)); conn.commit()

            if "user" in inspector.get_table_names():
                user_cols = [c["name"] for c in inspector.get_columns("user")]
                for col, sql in [
                    ("created_at",    "ALTER TABLE user ADD COLUMN created_at DATETIME"),
                    ("updated_at",    "ALTER TABLE user ADD COLUMN updated_at DATETIME"),
                    ("password_hash", "ALTER TABLE user ADD COLUMN password_hash VARCHAR(255)"),
                    ("role",          'ALTER TABLE "user" ADD COLUMN role VARCHAR(20) DEFAULT "student"'),
                ]:
                    if col not in user_cols:
                        with db.engine.connect() as conn:
                            conn.execute(text(sql)); conn.commit()

            if "community_group" in inspector.get_table_names():
                grp_cols = [c["name"] for c in inspector.get_columns("community_group")]
                for col, sql in [
                    ("created_by", "ALTER TABLE community_group ADD COLUMN created_by INTEGER"),
                    ("created_at", "ALTER TABLE community_group ADD COLUMN created_at DATETIME"),
                ]:
                    if col not in grp_cols:
                        with db.engine.connect() as conn:
                            conn.execute(text(sql)); conn.commit()

        except Exception as e:
            print(f"Migration warning: {e}")
            db.drop_all()
            db.create_all()

        # ---- Default community groups ----
        if Group.query.count() == 0:
            for name, slug, desc, cat in [
                ("AI & Data Science", "ai-data",
                 "Исследования в области ИИ и науки о данных.", "Технологии"),
                ("Research & Academia", "research",
                 "Академические исследования, публикации, гранты.", "Наука"),
                ("Entrepreneurship", "entrepreneurship",
                 "Стартапы, инкубаторы, поиск сооснователей и менторов.", "Бизнес"),
                ("Scholarships Abroad", "scholarships",
                 "Обучение за рубежом, стипендии, программы обмена.", "Образование"),
            ]:
                db.session.add(Group(name=name, slug=slug, description=desc, category=cat))
            db.session.commit()

        # ---- Demo accounts ----
        demo = [
            {
                "email": "student@gsc.com", "name": "Алия Иванова",
                "password": "student123", "role": "student", "status": "verified",
                "university": "МГУ им. Ломоносова", "country": "Россия",
                "skills": "Python, Data Analysis, Research",
                "interests": "AI, Science, Entrepreneurship",
                "goals": "Поступить в аспирантуру и получить грант на исследования в области ИИ.",
            },
            {
                "email": "organizer@gsc.com", "name": "Дмитрий Петров",
                "password": "organizer123", "role": "organizer", "status": "verified",
                "university": "НИУ ВШЭ", "country": "Россия",
                "skills": "Event Management, Fundraising, Leadership",
                "interests": "Scholarships, Academic Competitions",
                "goals": "Организовывать международные образовательные программы для студентов.",
            },
            {
                "email": "admin@gsc.com", "name": "Администратор",
                "password": "admin123", "role": "admin", "status": "verified",
            },
        ]
        for acc in demo:
            if not User.query.filter_by(email=acc["email"]).first():
                u = User(
                    email=acc["email"],
                    name=acc["name"],
                    role=acc["role"],
                    status=acc["status"],
                    university=acc.get("university"),
                    country=acc.get("country"),
                    skills=acc.get("skills"),
                    interests=acc.get("interests"),
                    goals=acc.get("goals"),
                )
                u.set_password(acc["password"])
                db.session.add(u)
        db.session.commit()

    app.run(debug=True)
