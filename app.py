from flask import Flask, render_template, request, redirect, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
from sqlalchemy import text, inspect

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


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # nullable для старых записей
    name = db.Column(db.String(100), nullable=False)
    university = db.Column(db.String(100))
    country = db.Column(db.String(100))
    skills = db.Column(db.Text)
    goals = db.Column(db.Text)
    interests = db.Column(db.Text)
    links = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
    role = db.Column(db.String(20), default="user")  # user, moderator, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'

class Opportunity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    requirements = db.Column(db.Text)  # требования
    category = db.Column(db.String(50), index=True)  # grant, internship, project, mentor, housing
    deadline = db.Column(db.String(50))
    source = db.Column(db.String(200))  # источник / партнёр
    verified = db.Column(db.Boolean, default=False, index=True)
    views_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Opportunity {self.title}>'

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120))
    opportunity_id = db.Column(db.Integer)
    status = db.Column(db.String(20), default="applied")


class Group(db.Model):
    __tablename__ = "community_group"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, index=True)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GroupMember(db.Model):
    __tablename__ = "group_member"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("community_group.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("group_id", "user_id", name="uq_group_member"),)

@app.route("/add-opportunity", methods=["GET", "POST"])
def add_opportunity():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        deadline = request.form.get("deadline", "").strip()
        
        # Валидация
        if not title:
            flash("Название обязательно для заполнения", "error")
            return render_template("add_opportunity.html")
        
        try:
            requirements = request.form.get("requirements", "").strip()
            source = request.form.get("source", "").strip()
            op = Opportunity(
                title=title,
                description=description,
                requirements=requirements or None,
                category=category,
                deadline=deadline,
                source=source or None
            )
            db.session.add(op)
            db.session.commit()
            flash("Возможность успешно добавлена и отправлена на модерацию", "success")
            return redirect("/opportunities")
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при добавлении: {str(e)}", "error")
            return render_template("add_opportunity.html")

    return render_template("add_opportunity.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("profile"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
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
        user = User(email=email, name=name)
        user.set_password(password)
        if User.query.count() == 0:
            user.role = "admin"
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Регистрация успешна. Заполните профиль.", "success")
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
        login_user(user)
        next_url = request.args.get("next") or url_for("profile")
        return redirect(next_url)
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    flash("Вы вышли из аккаунта", "info")
    return redirect(url_for("home"))


@app.route("/")
def home():
    # Статистика для главной страницы
    total_users = User.query.count()
    verified_users = User.query.filter_by(status="verified").count()
    total_opportunities = Opportunity.query.count()
    verified_opportunities = Opportunity.query.filter_by(verified=True).count()
    total_applications = Application.query.count()
    
    stats = {
        "total_users": total_users,
        "verified_users": verified_users,
        "total_opportunities": total_opportunities,
        "verified_opportunities": verified_opportunities,
        "total_applications": total_applications
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
            return redirect(url_for("profiles"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка: {str(e)}", "error")
    return render_template("profile.html", user=user)



@app.route("/profiles")
def profiles():
    # Получаем параметры фильтрации
    search_query = request.args.get("search", "").strip()
    country = request.args.get("country", "")
    university = request.args.get("university", "")
    page = request.args.get("page", 1, type=int)
    per_page = 12
    
    # Базовый запрос
    query = User.query.filter(User.status != "banned")
    
    # Применяем фильтры
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
    
    # Сортировка: верифицированные сначала, потом по дате создания
    query = query.order_by(
        db.case((User.status == "verified", 1), else_=2),
        User.created_at.desc()
    )
    
    # Пагинация
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    students = pagination.items
    
    # Получаем уникальные страны и университеты для фильтра
    countries = db.session.query(User.country).distinct().filter(User.country != None, User.country != "").all()
    countries = [c[0] for c in countries if c[0]]
    
    universities = db.session.query(User.university).distinct().filter(User.university != None, User.university != "").limit(20).all()
    universities = [u[0] for u in universities if u[0]]
    
    return render_template(
        "profiles.html",
        students=students,
        pagination=pagination,
        countries=countries,
        universities=universities,
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


@app.route("/opportunities")
def opportunities():
    # Параметры фильтрации
    category = request.args.get("category", "")
    search_query = request.args.get("search", "").strip()
    verified_only = request.args.get("verified", "") == "on"
    with_deadline = request.args.get("deadline", "") == "on"  # только с указанным дедлайном
    sort = request.args.get("sort", "")  # "", "deadline", "newest"
    page = request.args.get("page", 1, type=int)
    per_page = 12
    
    query = Opportunity.query
    
    if category:
        query = query.filter(Opportunity.category == category)
    if verified_only:
        query = query.filter(Opportunity.verified == True)
    if with_deadline:
        query = query.filter(Opportunity.deadline != None, Opportunity.deadline != "")
    if search_query:
        query = query.filter(
            db.or_(
                Opportunity.title.contains(search_query),
                Opportunity.description.contains(search_query),
                Opportunity.requirements.contains(search_query),
                Opportunity.source.contains(search_query)
            )
        )
    
    # Сортировка
    if sort == "deadline":
        query = query.order_by(
            Opportunity.deadline.asc(),
            Opportunity.verified.desc(),
            Opportunity.created_at.desc()
        )
    else:
        query = query.order_by(
            Opportunity.verified.desc(),
            Opportunity.created_at.desc()
        )
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    ops = pagination.items
    
    categories = [c[0] for c in db.session.query(Opportunity.category).distinct().all() if c[0]]
    
    return render_template(
        "opportunities.html",
        opportunities=ops,
        pagination=pagination,
        categories=categories,
        current_category=category,
        current_search=search_query,
        verified_only=verified_only,
        with_deadline=with_deadline,
        sort=sort
    )


@app.route("/partners")
def partners():
    return render_template("partners.html")


@app.route("/community")
def community():
    groups = Group.query.order_by(Group.name).all()
    member_ids = set()
    if current_user.is_authenticated:
        member_ids = {m.group_id for m in GroupMember.query.filter_by(user_id=current_user.id).all()}
    return render_template("community.html", groups=groups, member_ids=member_ids)


@app.route("/community/<int:group_id>")
def community_group(group_id):
    group = Group.query.get_or_404(group_id)
    members = GroupMember.query.filter_by(group_id=group_id).count()
    is_member = False
    if current_user.is_authenticated:
        is_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first() is not None
    return render_template("community_group.html", group=group, members_count=members, is_member=is_member)


@app.route("/community/<int:group_id>/join", methods=["POST"])
@login_required
def community_join(group_id):
    group = Group.query.get_or_404(group_id)
    if GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first():
        flash("Вы уже в группе", "info")
    else:
        m = GroupMember(group_id=group_id, user_id=current_user.id)
        db.session.add(m)
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


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Доступ запрещён", "error")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapped


@app.route("/admin")
@login_required
@admin_required
def admin():
    users = User.query.order_by(User.created_at.desc()).limit(100).all()
    opportunities = Opportunity.query.order_by(Opportunity.created_at.desc()).limit(50).all()
    return render_template("admin/index.html", users=users, opportunities=opportunities)


@app.route("/admin/user/<int:user_id>/verify", methods=["POST"])
@login_required
@admin_required
def admin_user_verify(user_id):
    u = User.query.get_or_404(user_id)
    u.status = "verified"
    db.session.commit()
    flash(f"Пользователь {u.email} верифицирован", "success")
    return redirect(url_for("admin"))


@app.route("/admin/opportunity/<int:op_id>/verify", methods=["POST"])
@login_required
@admin_required
def admin_opportunity_verify(op_id):
    op = Opportunity.query.get_or_404(op_id)
    op.verified = True
    db.session.commit()
    flash(f"Возможность «{op.title}» верифицирована", "success")
    return redirect(url_for("admin"))


@app.route("/opportunity/<int:op_id>", methods=["GET", "POST"])
def opportunity_page(op_id):
    op = Opportunity.query.get_or_404(op_id)
    
    # Увеличиваем счетчик просмотров
    if request.method == "GET":
        op.views_count += 1
        db.session.commit()

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        
        if not email:
            flash("Пожалуйста, укажите ваш email", "error")
            return render_template("opportunity_page.html", op=op)
        
        # Проверяем, не подавал ли уже пользователь заявку
        existing = Application.query.filter_by(
            user_email=email,
            opportunity_id=op.id
        ).first()
        
        if existing:
            flash("Вы уже подали заявку на эту возможность", "warning")
        else:
            application = Application(
                user_email=email,
                opportunity_id=op.id
            )
            db.session.add(application)
            db.session.commit()
            flash("Заявка успешно подана!", "success")
            return redirect("/opportunities")

    return render_template("opportunity_page.html", op=op)


# Обработчики ошибок
@app.errorhandler(404)
def not_found_error(error):
    return render_template("errors/404.html"), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template("errors/500.html"), 500

if __name__ == "__main__":
    with app.app_context():
        # Создаем таблицы, если их нет
        db.create_all()
        
        # Добавляем недостающие колонки, если их нет (миграция для SQLite)
        try:
            inspector = inspect(db.engine)
            
            # Проверяем и добавляем views_count для opportunity
            if 'opportunity' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('opportunity')]
                
                if 'views_count' not in columns:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE opportunity ADD COLUMN views_count INTEGER DEFAULT 0'))
                        conn.commit()
                
                if 'created_at' not in columns:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE opportunity ADD COLUMN created_at DATETIME'))
                        conn.commit()
                        
                if 'updated_at' not in columns:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE opportunity ADD COLUMN updated_at DATETIME'))
                        conn.commit()
                
                if 'requirements' not in columns:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE opportunity ADD COLUMN requirements TEXT'))
                        conn.commit()
                if 'source' not in columns:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE opportunity ADD COLUMN source VARCHAR(200)'))
                        conn.commit()
            
            # Проверяем и добавляем created_at и updated_at для user
            if 'user' in inspector.get_table_names():
                user_columns = [col['name'] for col in inspector.get_columns('user')]
                
                if 'created_at' not in user_columns:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE user ADD COLUMN created_at DATETIME'))
                        conn.commit()
                        
                if 'updated_at' not in user_columns:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE user ADD COLUMN updated_at DATETIME'))
                        conn.commit()
                
                if 'password_hash' not in user_columns:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE user ADD COLUMN password_hash VARCHAR(255)'))
                        conn.commit()
                
                if 'role' not in user_columns:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT "user"'))
                        conn.commit()
                        
        except Exception as e:
            print(f"Migration failed: {e}. Recreating tables...")
            db.drop_all()
            db.create_all()
        
        # Группы по умолчанию
        if Group.query.count() == 0:
            for name, slug, desc, cat in [
                ("AI & Data Science", "ai-data", "Исследования в области ИИ и науки о данных. Обмен проектами и возможностями.", "Технологии"),
                ("Research & Academia", "research", "Академические исследования, публикации, гранты.", "Наука"),
                ("Entrepreneurship", "entrepreneurship", "Стартапы, инкубаторы. Поиск сооснователей и менторов.", "Бизнес"),
                ("Scholarships Abroad", "scholarships", "Обучение за рубежом, стипендии, программы обмена.", "Образование"),
            ]:
                db.session.add(Group(name=name, slug=slug, description=desc, category=cat))
            db.session.commit()
    
    app.run(debug=True)
