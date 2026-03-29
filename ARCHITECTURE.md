# 🏗️ Архитектура Gold Students Club

## Текущая архитектура

```
┌─────────────────────────────────────────┐
│           Flask Application            │
│  ┌───────────────────────────────────┐ │
│  │         app.py (monolith)         │ │
│  │  - Routes                          │ │
│  │  - Models                          │ │
│  │  - Business Logic                  │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│         SQLite Database                  │
│  - users                                 │
│  - opportunities                         │
│  - applications                          │
└─────────────────────────────────────────┘
```

## Предлагаемая архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Web UI     │  │  Mobile App  │  │   Admin UI   │    │
│  │  (Templates) │  │   (Future)   │  │              │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (Flask)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Blueprints  │  │   REST API   │  │  WebSockets  │    │
│  │  - auth      │  │   /api/v1/   │  │  (Real-time) │    │
│  │  - profile   │  │              │  │              │    │
│  │  - opps      │  │              │  │              │    │
│  │  - community │  │              │  │              │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Business Logic Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Services   │  │   Matching   │  │  Notifications│   │
│  │  - User      │  │   Algorithm  │  │  Service      │    │
│  │  - Opp       │  │              │  │              │    │
│  │  - Community │  │              │  │              │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Models     │  │   Cache      │  │   Search     │    │
│  │  (SQLAlchemy)│  │   (Redis)    │  │   (Elastic)  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  PostgreSQL Database                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Users      │  │ Opportunities│  │  Community   │    │
│  │   Roles      │  │  Categories  │  │  Messages    │    │
│  │   Profiles   │  │  Partners   │  │  Groups      │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Структура проекта (предлагаемая)

```
PythonProject6/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Конфигурация
│   │
│   ├── models/                  # Модели БД
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── opportunity.py
│   │   ├── application.py
│   │   ├── community.py
│   │   ├── partner.py
│   │   └── role.py
│   │
│   ├── routes/                   # Маршруты (Blueprints)
│   │   ├── __init__.py
│   │   ├── auth.py              # Аутентификация
│   │   ├── profile.py            # Профили
│   │   ├── opportunities.py     # Возможности
│   │   ├── community.py          # Сообщество
│   │   ├── admin.py              # Админ-панель
│   │   └── api/                  # REST API
│   │       ├── __init__.py
│   │       ├── v1/
│   │       │   ├── __init__.py
│   │       │   ├── users.py
│   │       │   └── opportunities.py
│   │
│   ├── services/                 # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   ├── opportunity_service.py
│   │   ├── matching_service.py
│   │   ├── notification_service.py
│   │   └── email_service.py
│   │
│   ├── utils/                    # Утилиты
│   │   ├── __init__.py
│   │   ├── validators.py
│   │   ├── helpers.py
│   │   ├── decorators.py
│   │   └── permissions.py
│   │
│   ├── forms/                    # WTForms
│   │   ├── __init__.py
│   │   ├── profile_form.py
│   │   ├── opportunity_form.py
│   │   └── auth_form.py
│   │
│   ├── templates/                # HTML шаблоны
│   │   ├── base.html
│   │   ├── auth/
│   │   ├── profile/
│   │   ├── opportunities/
│   │   └── community/
│   │
│   └── static/                   # Статика
│       ├── css/
│       ├── js/
│       └── images/
│
├── migrations/                   # Alembic миграции
│
├── tests/                        # Тесты
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_routes.py
│   └── test_services.py
│
├── config.py                     # Конфигурация
├── requirements.txt              # Зависимости
├── .env.example                  # Пример env файла
├── docker-compose.yml            # Docker Compose
├── Dockerfile                    # Docker образ
└── README.md                     # Документация
```

## Модели данных (расширенные)

### User Model
```python
User
├── id
├── email (unique, indexed)
├── password_hash
├── name
├── role_id (FK → Role)
├── status (pending/verified/banned)
├── profile
│   ├── avatar_url
│   ├── university
│   ├── country
│   ├── bio
│   ├── cv_url
│   └── links (JSON)
├── skills (many-to-many → Skill)
├── interests
├── goals
├── reputation_score
├── created_at
├── updated_at
└── deleted_at (soft delete)
```

### Opportunity Model
```python
Opportunity
├── id
├── title
├── description
├── category_id (FK → Category)
├── partner_id (FK → Partner)
├── created_by (FK → User)
├── requirements (JSON)
├── benefits (JSON)
├── location
├── compensation
├── duration
├── deadline
├── slots_available
├── verified (boolean)
├── views_count
├── applications_count
├── created_at
├── updated_at
└── deleted_at
```

### Application Model
```python
Application
├── id
├── user_id (FK → User)
├── opportunity_id (FK → Opportunity)
├── status (applied/reviewed/accepted/rejected)
├── cover_letter
├── documents (JSON array)
├── submitted_at
└── updated_at
```

### Community Models
```python
Group
├── id
├── name
├── description
├── category
├── members (many-to-many → User)
├── moderators (many-to-many → User)
└── created_at

Message
├── id
├── sender_id (FK → User)
├── recipient_id (FK → User) [nullable]
├── group_id (FK → Group) [nullable]
├── content
├── read (boolean)
└── created_at

Project
├── id
├── name
├── description
├── owner_id (FK → User)
├── members (many-to-many → User)
├── skills_required (many-to-many → Skill)
└── status
```

## Потоки данных

### Регистрация пользователя
```
User → Registration Form
  → Validation
  → User Service
  → Create User (pending status)
  → Send Verification Email
  → Redirect to Profile Setup
```

### Подача заявки на возможность
```
User → Opportunity Page
  → Application Form
  → Validation
  → Application Service
  → Create Application
  → Notify Partner
  → Update Opportunity Stats
```

### Модерация возможности
```
Admin → Admin Panel
  → Opportunity List
  → Review Details
  → Approve/Reject
  → Update Verified Status
  → Notify Creator
```

### Поиск возможностей
```
User → Search/Filter
  → Search Service
  → Query Database (with filters)
  → Apply Matching Algorithm
  → Rank Results
  → Return to User
```

## Технологический стек

### Backend
- **Framework:** Flask 2.x
- **ORM:** SQLAlchemy
- **Database:** PostgreSQL (production), SQLite (dev)
- **Migrations:** Alembic
- **Auth:** Flask-Login, Flask-JWT
- **Forms:** WTForms
- **API:** Flask-RESTful

### Frontend
- **Templates:** Jinja2
- **CSS:** Custom CSS (CSS Variables)
- **JS:** Vanilla JS (можно добавить Vue.js)
- **Icons:** Font Awesome / Feather Icons

### Infrastructure
- **Containerization:** Docker
- **Cache:** Redis
- **Search:** PostgreSQL Full-Text Search (или Elasticsearch)
- **Email:** SendGrid / Mailgun
- **Monitoring:** Sentry
- **CI/CD:** GitHub Actions

### Future
- **Mobile:** React Native / Flutter
- **Real-time:** WebSockets (Socket.io)
- **Analytics:** Google Analytics / Mixpanel

## Безопасность

### Аутентификация
- Bcrypt для хеширования паролей
- JWT токены для API
- Session management
- Remember me функционал

### Авторизация
- Role-based access control (RBAC)
- Permission decorators
- Resource-level permissions

### Защита
- CSRF tokens
- Rate limiting
- Input validation & sanitization
- SQL injection protection (ORM)
- XSS protection
- HTTPS обязателен

## Масштабирование

### Горизонтальное масштабирование
- Load balancer (Nginx)
- Multiple app instances
- Database replication
- Redis cluster

### Вертикальное масштабирование
- Оптимизация запросов
- Индексы БД
- Кэширование
- CDN для статики

### Мониторинг
- Application logs
- Error tracking (Sentry)
- Performance metrics
- Uptime monitoring
