from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)


app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///students.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

    university = db.Column(db.String(100))
    country = db.Column(db.String(100))

    skills = db.Column(db.Text)
    goals = db.Column(db.Text)
    interests = db.Column(db.Text)
    links = db.Column(db.Text)

    status = db.Column(db.String(20), default="pending")

class Opportunity(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # grant / internship / project
    deadline = db.Column(db.String(50))

    verified = db.Column(db.Boolean, default=False)

@app.route("/add-opportunity", methods=["GET", "POST"])
def add_opportunity():
    if request.method == "POST":
        op = Opportunity(
            title=request.form["title"],
            description=request.form["description"],
            category=request.form["category"],
            deadline=request.form["deadline"]
        )
        db.session.add(op)
        db.session.commit()
        return redirect("/opportunities")

    return render_template("add_opportunity.html")




@app.route("/")
def home():
    return render_template("home.html")


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "POST":

        user = User.query.filter_by(email=request.form["email"]).first()

        if not user:
            user = User(email=request.form["email"])

        user.name = request.form["name"]
        user.university = request.form.get("university")
        user.country = request.form.get("country")
        user.skills = request.form.get("skills")
        user.goals = request.form.get("goals")
        user.interests = request.form.get("interests")
        user.links = request.form.get("links")

        db.session.add(user)
        db.session.commit()

        return redirect("/opportunities")

    return render_template("profile.html")



@app.route("/profiles")
def profiles():
    students = Student.query.all()
    return render_template("profiles.html", students=students)


@app.route("/opportunities")
def opportunities():
    ops = Opportunity.query.all()
    return render_template("opportunities.html", opportunities=ops)
class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_email = db.Column(db.String(120))
    opportunity_id = db.Column(db.Integer)

    status = db.Column(db.String(20), default="applied")



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

@app.route("/partners")
def partners():
    return render_template("partners.html")
@app.route("/community")
def community():
    return render_template("community.html")
@app.route("/opportunity/<int:op_id>", methods=["GET", "POST"])
def opportunity_page(op_id):
    op = Opportunity.query.get_or_404(op_id)

    if request.method == "POST":
        email = request.form["email"]

        application = Application(
            user_email=email,
            opportunity_id=op.id
        )

        db.session.add(application)
        db.session.commit()

        return redirect("/opportunities")

    return render_template("opportunity_page.html", op=op)


