# AI Caddy - Implementation Documentation

## STRUCTURE

### Technology Stack and Dependencies

#### Core Framework
- **Django 5.2.7**: Web framework for Python
- **PostgreSQL**: Relational database (via `psycopg2-binary==2.9.11`)
- **Python 3.12**: Programming language

#### Machine Learning & Data Science
- **scikit-learn>=1.3.0**: K-Nearest Neighbors (KNN) algorithm for club recommendations
- **numpy>=1.26.0**: Numerical operations and array handling

#### Security & Configuration
- **python-decouple==3.8**: Environment variable management for secure credential handling

#### Frontend
- **Plotly.js** (CDN): Interactive data visualization for KNN feature space
- **Google Fonts**: 'Playfair Display' (serif) and 'Lato' (sans-serif) for typography
- **CSS3**: Custom styling with CSS variables, gradients, and responsive design

### File/Folder Architecture

```
aicaddy_project/
├── aicaddy/                    # Main Django project configuration
│   ├── __init__.py
│   ├── settings.py             # Django settings (DB, apps, middleware)
│   ├── urls.py                 # Root URL configuration
│   ├── wsgi.py                 # WSGI application entry point
│   └── asgi.py                 # ASGI application entry point
│
├── dashboard/                  # Main application module
│   ├── __init__.py
│   ├── apps.py                 # App configuration
│   ├── models.py               # Database models (Club, GolfRound, Shot)
│   ├── views.py                # View functions (business logic)
│   ├── urls.py                 # URL routing for dashboard app
│   ├── admin.py                # Django admin configuration
│   ├── tests.py                # Unit tests (placeholder)
│   │
│   ├── migrations/             # Database migrations
│   │   └── 0001_initial.py     # Initial schema creation
│   │
│   ├── static/                 # Static files (CSS, images)
│   │   └── dashboard/
│   │       ├── css/
│   │       │   └── style.css   # Main stylesheet (Masters green theme)
│   │       └── images/         # Image assets
│   │
│   └── templates/              # HTML templates
│       ├── dashboard/
│       │   ├── base.html       # Base template with header/nav
│       │   ├── dashboard.html  # Main dashboard (club performance)
│       │   ├── addround.html   # Add new round form
│       │   ├── round_detail.html # Round details view
│       │   ├── recommendations.html # KNN recommendation interface
│       │   └── clear_data_confirm.html # Data deletion confirmation
│       └── registration/
│           ├── login.html      # Login page
│           └── signup.html     # Registration page
│
├── static/                     # Additional static files directory
├── staticfiles/                # Collected static files (production)
├── venv/                       # Python virtual environment
├── dummy_shots.csv             # Test data CSV (500+ shot records)
├── manage.py                   # Django management script
├── requirements.txt            # Python dependencies
└── .env                        # Environment variables (not in repo)
```

### Purpose of Each Component

#### `aicaddy/settings.py`
- **Purpose**: Central configuration for Django application
- **Key Settings**:
  - Database connection (PostgreSQL via environment variables)
  - Installed apps (`dashboard`)
  - Middleware stack (security, sessions, CSRF, authentication)
  - Static files configuration
  - Login/logout URLs

#### `dashboard/models.py`
- **Purpose**: Database schema definition using Django ORM
- **Models**:
  - `Club`: User's golf clubs (Driver, 7 Iron, etc.)
  - `GolfRound`: A single round of golf (date, course name)
  - `Shot`: Individual shot data (club, distance, lie, shot_shape)
- **Custom Methods**:
  - `Club.get_average_distance_fairway()`: Average distance for Fairway/Tee Box shots
  - `Club.get_average_distance_rough()`: Average distance for Rough shots
  - `Club.get_fairway_shot_count()`: Count of fairway/tee box shots
  - `Club.get_rough_shot_count()`: Count of rough shots

#### `dashboard/views.py`
- **Purpose**: Business logic and request handling
- **Key Views**:
  - Authentication: `signup_view`, `login_view`, `logout_view`
  - Data Management: `dashboard_view`, `add_round_view`, `round_detail_view`, `load_test_data_view`, `clear_all_data_view`
  - AI Recommendations: `recommendation_view`, `recommendation_visualization_view`

#### `dashboard/urls.py`
- **Purpose**: URL routing for dashboard app
- **Routes**:
  - `/`: Dashboard
  - `/signup/`, `/login/`, `/logout/`: Authentication
  - `/round/add/`: Add new round
  - `/round/<id>/`: Round details
  - `/recommendations/`: Get club recommendation
  - `/recommendations/visualization/`: KNN visualization API
  - `/load_test_data/`: Load dummy data
  - `/clear_all_data/`: Clear user data

#### `dashboard/static/dashboard/css/style.css`
- **Purpose**: Styling with vintage golf pro shop theme
- **Features**:
  - CSS variables for color palette (Masters green, browns, gold)
  - Responsive design with media queries
  - Custom gradients and shadows
  - Modal styling for visualizations

### Data Flow and State Management Patterns

#### Request Flow
1. **User Request** → Django URL dispatcher (`aicaddy/urls.py` → `dashboard/urls.py`)
2. **View Processing** → `dashboard/views.py` function handles request
3. **Database Query** → Django ORM queries PostgreSQL
4. **Template Rendering** → Django template engine renders HTML
5. **Response** → HTML + CSS + JavaScript sent to client

#### State Management
- **Server-Side**: Django sessions for authentication state
- **Database**: PostgreSQL stores persistent data (clubs, rounds, shots)
- **Client-Side**: No JavaScript framework; vanilla JS for visualization modal
- **No Global State**: Each request is stateless; data retrieved from DB per request

#### Data Flow Example: Club Recommendation
```
1. User submits form (distance, lie, bend, shot_shape)
   ↓
2. recommendation_view() receives GET parameters
   ↓
3. Query database for user's historical shots
   ↓
4. Prepare feature matrix:
   - Extract: distance, lie, bend (inferred), shot_shape
   - Encode categorical features (LabelEncoder)
   - Combine into numpy array
   ↓
5. Train KNN model:
   - Determine k (sqrt of sample size, min 3, max 10)
   - Fit KNeighborsClassifier with distance weighting
   ↓
6. Predict club for query point
   ↓
7. Calculate confidence scores:
   - Distance-weighted probabilities
   - Neighbor agreement percentages
   - Cap probabilities at 95% for realism
   ↓
8. Retrieve club objects for average distances
   ↓
9. Render recommendations.html with results
```

### Key Algorithms and Business Logic

#### K-Nearest Neighbors (KNN) Algorithm

**Location**: `dashboard/views.py` → `recommendation_view()`

**Algorithm Steps**:
1. **Feature Extraction**:
   ```python
   features = [
       distance,      # Numeric (yards)
       lie,           # Categorical (Fairway, Rough, Sand, Tee Box)
       bend,          # Categorical (Straight, Dogleg Left, Dogleg Right)
       shot_shape     # Categorical (Straight, Fade, Draw, Slice, Hook)
   ]
   ```

2. **Feature Encoding**:
   - Numeric features (distance) used directly
   - Categorical features encoded using `LabelEncoder`:
     ```python
     lie_encoder = LabelEncoder()
     lie_encoded = lie_encoder.fit_transform(lie_col)
     ```

3. **K Value Selection**:
   ```python
   k = max(3, min(10, int(np.sqrt(len(X_train)))))
   ```
   - Dynamic k based on sample size
   - Minimum 3 neighbors, maximum 10
   - Square root rule for balanced bias/variance

4. **Model Training**:
   ```python
   knn = KNeighborsClassifier(n_neighbors=k, weights='distance')
   knn.fit(X_train, y_train)
   ```
   - Distance weighting: closer neighbors have more influence

5. **Prediction**:
   ```python
   predicted_club = knn.predict(X_query)[0]
   ```

6. **Confidence Calculation**:
   - **Distance-Weighted Scores**: Inverse distance as weight
   - **Confidence Factor**: Based on average neighbor distance
   - **Probability Capping**: Maximum 95% to show uncertainty
   - **Agreement Percentage**: How many neighbors agree on club

**Bend Inference Logic**:
```python
def infer_bend_from_shot_shape(shot_shape):
    if shot_shape in ['Draw', 'Hook']:
        return 'Dogleg Left'  # Used draw/hook to go left
    elif shot_shape in ['Fade', 'Slice']:
        return 'Dogleg Right'  # Used fade/slice to go right
    else:
        return 'Straight'
```
- Historical shots: bend inferred from shot_shape
- New queries: bend provided by user

#### PCA for Visualization

**Location**: `dashboard/views.py` → `recommendation_visualization_view()`

**Purpose**: Reduce 4D feature space to 2D for visualization

**Algorithm**:
```python
X_combined = np.vstack([X_train, X_query])
pca = PCA(n_components=2)
X_2d = pca.fit_transform(X_combined)
```

**Output**: 2D coordinates for Plotly.js scatter plot

#### Average Distance Calculation

**Location**: `dashboard/models.py` → `Club` model methods

**Fairway Average**:
```python
def get_average_distance_fairway(self):
    avg = self.shot_set.filter(lie__in=['Fairway', 'Tee Box']).aggregate(
        average=Avg('distance')
    )['average']
    return int(round(avg)) if avg else None
```

**Rough Average**:
```python
def get_average_distance_rough(self):
    avg = self.shot_set.filter(lie='Rough').aggregate(
        average=Avg('distance')
    )['average']
    return int(round(avg)) if avg else None
```

**Note**: Sand shots excluded from averages; Tee Box treated as Fairway

---

## FEATURES

### User-Facing Features

#### 1. User Authentication
- **Sign Up**: Create account with username/password
- **Login/Logout**: Session-based authentication
- **Default Clubs**: New users get 13 default clubs (Driver, 3 Wood, 5 Wood, 4-9 Iron, Pitching Wedge, 52/56/60 Degree)

#### 2. Dashboard
- **Purpose**: Display club performance statistics
- **Features**:
  - Table of all user clubs
  - Average distance for Fairway/Tee Box shots
  - Average distance for Rough shots
  - Recent rounds list
  - Action buttons: "Add New Round", "Load Test Data", "Clear All Data"

#### 3. Add New Round
- **Purpose**: Record a golf round with multiple shots
- **Features**:
  - Course name input
  - Dynamic shot input rows (add multiple shots per round)
  - Per-shot data: club, distance, shot shape, lie
  - Redirects to round detail page after submission

#### 4. Round Detail
- **Purpose**: View all shots from a specific round
- **Features**:
  - Round metadata (date, course name)
  - Table of all shots (club, distance, shot shape, lie)
  - "Back to Dashboard" button

#### 5. Club Recommendation (KNN)
- **Purpose**: AI-powered club selection based on historical data
- **Input Parameters**:
  - Distance to target (yards)
  - Current lie (Fairway, Rough, Sand, Tee Box)
  - Hole bend (Straight, Dogleg Left, Dogleg Right)
  - Shot shape (optional, defaults to Straight)
- **Output**:
  - Ranked list of recommended clubs
  - Average distance for each club (based on lie)
  - Confidence level (High/Medium/Low)
  - Match Score (distance-weighted probability, capped at 95%)
  - Agreement percentage (neighbor consensus)
- **Visualization**: Interactive 2D PCA plot showing:
  - All historical shots (colored by club)
  - Nearest neighbors (highlighted)
  - Query point (red star)
  - PCA explained variance

#### 6. Load Test Data
- **Purpose**: Populate database with sample shots from CSV
- **Features**:
  - Reads `dummy_shots.csv` from project root
  - Creates new round "Test Data Load"
  - Validates club names against user's clubs
  - Skips invalid rows with error messages
  - Bulk creates shots for performance

#### 7. Clear All Data
- **Purpose**: Delete all rounds and shots for a user
- **Features**:
  - Confirmation page showing counts
  - Preserves clubs (equipment)
  - Cascade deletes shots when rounds deleted
  - Success message with deletion counts

### API Endpoints/Functions

#### Authentication Views

##### `signup_view(request)`
- **Method**: GET, POST
- **Parameters**: `request` (Django HttpRequest)
- **Returns**: `HttpResponse` (rendered template or redirect)
- **Functionality**:
  - GET: Display signup form
  - POST: Create user, log in, create default clubs, redirect to dashboard

##### `login_view(request)`
- **Method**: GET, POST
- **Parameters**: `request`
- **Returns**: `HttpResponse`
- **Functionality**:
  - GET: Display login form
  - POST: Authenticate user, log in, redirect to dashboard

##### `logout_view(request)`
- **Method**: GET
- **Parameters**: `request`
- **Returns**: `HttpResponse` (redirect)
- **Functionality**: Log out user, redirect to login

#### Main Application Views

##### `dashboard_view(request)`
- **Method**: GET
- **Decorator**: `@login_required`
- **Parameters**: `request`
- **Returns**: `HttpResponse` (rendered `dashboard/dashboard.html`)
- **Context**:
  - `clubs`: QuerySet of user's clubs
  - `rounds`: QuerySet of user's rounds (ordered by date DESC)

##### `add_round_view(request)`
- **Method**: GET, POST
- **Decorator**: `@login_required`
- **Parameters**: `request`
- **POST Data**:
  - `course_name`: String
  - `club[]`: List of club IDs
  - `distance[]`: List of distances
  - `shot_shape[]`: List of shot shapes
  - `lie[]`: List of lies
- **Returns**: `HttpResponse` (form or redirect)
- **Functionality**:
  - GET: Display form with user's clubs
  - POST: Create round and shots, redirect to round detail

##### `round_detail_view(request, round_id)`
- **Method**: GET
- **Decorator**: `@login_required`
- **Parameters**: `request`, `round_id` (int)
- **Returns**: `HttpResponse` (rendered `dashboard/round_detail.html`)
- **Context**:
  - `round`: GolfRound object
  - `shots`: QuerySet of shots for the round

##### `recommendation_view(request)`
- **Method**: GET
- **Decorator**: `@login_required`
- **GET Parameters**:
  - `distance`: int (required)
  - `lie`: str (default: 'Fairway')
  - `bend`: str (default: 'Straight')
  - `shot_shape`: str (default: 'Straight')
- **Returns**: `HttpResponse` (rendered `dashboard/recommendations.html`)
- **Context**:
  - `recommendations`: List of dicts with club recommendations
  - `k_value`: int (number of neighbors used)
  - `total_shots_analyzed`: int
  - `distance_input`, `lie_input`, `bend_input`, `shot_shape_input`: User inputs
  - `error`: str (if error occurred)

##### `recommendation_visualization_view(request)`
- **Method**: GET
- **Decorator**: `@login_required`
- **GET Parameters**: Same as `recommendation_view`
- **Returns**: `JsonResponse`
- **Response Structure**:
  ```json
  {
    "shots": [
      {
        "x": float,
        "y": float,
        "club": str,
        "distance": int,
        "lie": str,
        "bend": str,
        "shot_shape": str,
        "is_neighbor": bool,
        "shot_id": int
      }
    ],
    "query_point": {
      "x": float,
      "y": float,
      "distance": int,
      "lie": str,
      "bend": str,
      "shot_shape": str
    },
    "predicted_club": str,
    "club_colors": { "Club Name": "#hexcolor" },
    "pca_explained_variance": [float, float],
    "k": int
  }
  ```

##### `load_test_data_view(request)`
- **Method**: GET
- **Decorator**: `@login_required`
- **Parameters**: `request`
- **Returns**: `HttpResponse` (redirect or error message)
- **Functionality**:
  - Reads `dummy_shots.csv`
  - Creates new round
  - Bulk creates shots
  - Displays success/error messages

##### `clear_all_data_view(request)`
- **Method**: GET, POST
- **Decorator**: `@login_required`
- **Parameters**: `request`
- **Returns**: `HttpResponse`
- **Functionality**:
  - GET: Display confirmation page
  - POST: Delete all rounds (cascade deletes shots), redirect to dashboard

### Database Schema

#### Club Model
```python
class Club(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    
    # Methods:
    # - get_average_distance() -> float
    # - get_average_distance_fairway() -> int | None
    # - get_average_distance_rough() -> int | None
    # - get_fairway_shot_count() -> int
    # - get_rough_shot_count() -> int
```

**Relationships**:
- One-to-Many with `User` (one user has many clubs)
- One-to-Many with `Shot` (one club has many shots)

#### GolfRound Model
```python
class GolfRound(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    course_name = models.CharField(max_length=200)
```

**Relationships**:
- One-to-Many with `User` (one user has many rounds)
- One-to-Many with `Shot` (one round has many shots)

#### Shot Model
```python
class Shot(models.Model):
    SHOT_SHAPE_CHOICES = [
        ('Straight', 'Straight'),
        ('Fade', 'Fade'),
        ('Draw', 'Draw'),
        ('Slice', 'Slice'),
        ('Hook', 'Hook')
    ]
    LIE_CHOICES = [
        ('Fairway', 'Fairway'),
        ('Rough', 'Rough'),
        ('Sand', 'Sand'),
        ('Tee Box', 'Tee Box')
    ]
    
    golf_round = models.ForeignKey(GolfRound, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    distance = models.PositiveIntegerField()
    shot_shape = models.CharField(max_length=10, choices=SHOT_SHAPE_CHOICES)
    lie = models.CharField(max_length=10, choices=LIE_CHOICES)
```

**Relationships**:
- Many-to-One with `GolfRound` (many shots belong to one round)
- Many-to-One with `Club` (many shots use one club)

**Cascade Behavior**:
- Deleting a `GolfRound` deletes all associated `Shot` objects
- Deleting a `Club` deletes all associated `Shot` objects
- Deleting a `User` deletes all associated `Club`, `GolfRound`, and `Shot` objects

### Configuration Options and Environment Variables

#### Environment Variables (`.env` file)

**Required for Production**:
```bash
SECRET_KEY=django-insecure-...  # Django secret key
DEBUG=False                      # Set to False in production
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com  # Comma-separated
DB_NAME=aicaddy_db              # PostgreSQL database name
DB_USER=your_db_user           # PostgreSQL username
DB_PASSWORD=your_db_password   # PostgreSQL password
DB_HOST=localhost              # Database host
DB_PORT=5432                   # Database port
```

**Development Defaults** (in `settings.py`):
- `SECRET_KEY`: Has insecure default (change in production)
- `DEBUG`: Defaults to `True`
- `ALLOWED_HOSTS`: Defaults to empty list
- `DB_NAME`: Defaults to `'aicaddy_db'`
- `DB_USER`: Defaults to `'grant'`
- `DB_PASSWORD`: Defaults to empty string
- `DB_HOST`: Defaults to `'localhost'`
- `DB_PORT`: Defaults to `'5432'`

#### Django Settings

**INSTALLED_APPS**:
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'dashboard',  # Main application
]
```

**MIDDLEWARE**:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

**Static Files**:
- `STATIC_URL = 'static/'`
- `STATIC_ROOT = BASE_DIR / 'staticfiles'` (for `collectstatic`)
- `STATICFILES_DIRS = [BASE_DIR / 'static']`

**Authentication**:
- `LOGIN_URL = 'login'`
- `LOGIN_REDIRECT_URL = 'dashboard'`

---

## UNIQUE ASPECTS

### Novel Approaches or Optimizations

#### 1. Dynamic K Selection for KNN
- **Approach**: `k = max(3, min(10, int(np.sqrt(len(X_train)))))`
- **Rationale**: Balances bias and variance based on sample size
- **Benefit**: Adapts to small datasets (minimum 3) and large datasets (maximum 10)

#### 2. Distance-Weighted Confidence Scores
- **Approach**: Inverse distance weighting for neighbor votes
- **Implementation**:
  ```python
  weight = 1.0 / (neighbor_dists[i] + 0.0001)
  ```
- **Benefit**: Closer neighbors have more influence, improving accuracy

#### 3. Probability Capping at 95%
- **Approach**: Maximum probability set to 95% regardless of model confidence
- **Rationale**: Acknowledges model uncertainty and prevents overconfidence
- **Benefit**: More realistic user experience

#### 4. Bend Inference from Historical Data
- **Approach**: Infers hole bend from shot shape for historical shots
- **Logic**: Draw/Hook → Dogleg Left, Fade/Slice → Dogleg Right, Straight → Straight
- **Benefit**: Enables bend feature without requiring historical bend data

#### 5. Lie-Specific Average Distances
- **Approach**: Separate averages for Fairway/Tee Box vs. Rough
- **Implementation**: Model methods filter by lie before aggregation
- **Benefit**: More accurate recommendations based on current lie

#### 6. Bulk Create for Test Data
- **Approach**: `Shot.objects.bulk_create(shots_to_create)`
- **Benefit**: Single database query instead of N queries (performance)

#### 7. PCA for Visualization
- **Approach**: Reduces 4D feature space to 2D for visualization
- **Benefit**: Makes high-dimensional data interpretable

### Custom Utilities, Helpers, or Middleware

#### Helper Function: `infer_bend_from_shot_shape()`
**Location**: `dashboard/views.py` (inside `recommendation_view` and `recommendation_visualization_view`)

**Purpose**: Convert historical shot shapes to bend values for KNN feature

**Code**:
```python
def infer_bend_from_shot_shape(shot_shape):
    if shot_shape in ['Draw', 'Hook']:
        return 'Dogleg Left'
    elif shot_shape in ['Fade', 'Slice']:
        return 'Dogleg Right'
    else:
        return 'Straight'
```

#### Model Methods: Club Statistics
**Location**: `dashboard/models.py`

**Custom Methods**:
- `get_average_distance_fairway()`: Filters by Fairway/Tee Box, returns int or None
- `get_average_distance_rough()`: Filters by Rough, returns int or None
- `get_fairway_shot_count()`: Count of Fairway/Tee Box shots
- `get_rough_shot_count()`: Count of Rough shots

**Design Pattern**: Encapsulates business logic in model layer

### Performance Considerations and Trade-offs

#### Optimizations

1. **Bulk Create for Test Data**:
   - **Trade-off**: Memory usage vs. query count
   - **Decision**: Use bulk_create for 500+ shots (single query)

2. **QuerySet Filtering**:
   - **Optimization**: Filter shots by user at database level
   - **Code**: `Shot.objects.filter(club__user=request.user)`
   - **Benefit**: Reduces data transfer from database

3. **Dictionary Lookup for Clubs**:
   - **Optimization**: Convert QuerySet to dict for O(1) lookup
   - **Code**: `club_objects = {club.name: club for club in Club.objects.filter(user=request.user)}`
   - **Benefit**: Faster club retrieval in recommendation loop

#### Trade-offs

1. **KNN Training on Every Request**:
   - **Current**: Model trained fresh for each recommendation
   - **Trade-off**: Accuracy (always up-to-date) vs. Performance (recomputes)
   - **Future Optimization**: Cache model or use incremental learning

2. **PCA Recalculation**:
   - **Current**: PCA fit on combined training + query data each time
   - **Trade-off**: Accuracy (includes query in fit) vs. Performance
   - **Alternative**: Fit PCA on training data only, transform query

3. **No Database Indexing**:
   - **Current**: No explicit indexes on foreign keys or filters
   - **Trade-off**: Simplicity vs. Query performance
   - **Future**: Add indexes on `club__user`, `golf_round__user`, `lie`, `shot_shape`

### Security Implementations

#### 1. Environment Variable Management
- **Implementation**: `python-decouple` for secrets
- **Files**: `.env` (not in repo), `.env.example` (template)
- **Benefit**: Prevents credential exposure in code

#### 2. CSRF Protection
- **Implementation**: Django's `CsrfViewMiddleware`
- **Protection**: All POST forms include CSRF token
- **Benefit**: Prevents cross-site request forgery

#### 3. Authentication Required
- **Implementation**: `@login_required` decorator on all views
- **Protection**: Redirects unauthenticated users to login
- **Benefit**: Prevents unauthorized access

#### 4. User Data Isolation
- **Implementation**: All queries filter by `user=request.user`
- **Protection**: Users can only access their own data
- **Example**: `Club.objects.filter(user=request.user)`

#### 5. Input Validation
- **Implementation**: Model choices, type checking, error handling
- **Protection**: Prevents invalid data insertion
- **Example**: `shot_shape` must be in `SHOT_SHAPE_CHOICES`

#### 6. SQL Injection Prevention
- **Implementation**: Django ORM (parameterized queries)
- **Protection**: All database queries use ORM, not raw SQL
- **Benefit**: Automatic SQL injection prevention

#### 7. XSS Protection
- **Implementation**: Django template auto-escaping
- **Protection**: User input automatically escaped in templates
- **Benefit**: Prevents cross-site scripting attacks

---

## CONTEXT FOR LLM MODIFICATION

### Entry Points and Main Execution Flow

#### Application Startup
1. **WSGI Server** → `aicaddy/wsgi.py` → Django application
2. **URL Routing** → `aicaddy/urls.py` → `dashboard/urls.py` → View function
3. **View Processing** → `dashboard/views.py` → Business logic
4. **Database** → Django ORM → PostgreSQL
5. **Template Rendering** → Django template engine → HTML response

#### Main Execution Flow: Club Recommendation

```
User submits form
    ↓
GET /recommendations/?distance=150&lie=Fairway&bend=Straight
    ↓
aicaddy/urls.py → include('dashboard.urls')
    ↓
dashboard/urls.py → path('recommendations/', views.recommendation_view)
    ↓
recommendation_view(request)
    ↓
1. Extract GET parameters (distance, lie, bend, shot_shape)
    ↓
2. Query database: Shot.objects.filter(club__user=request.user)
    ↓
3. Prepare features:
   - Extract distance, lie, bend (inferred), shot_shape
   - Encode categorical features (LabelEncoder)
   - Combine into numpy array
    ↓
4. Train KNN:
   - Calculate k = max(3, min(10, int(sqrt(len(X_train)))))
   - Fit KNeighborsClassifier(n_neighbors=k, weights='distance')
    ↓
5. Predict club for query point
    ↓
6. Calculate confidence:
   - Distance-weighted probabilities
   - Neighbor agreement
   - Cap at 95%
    ↓
7. Retrieve club objects for average distances
    ↓
8. Build recommendations list
    ↓
9. Render template: dashboard/recommendations.html
    ↓
HTML response with recommendations table
```

### How Components Interact and Depend on Each Other

#### Dependency Graph

```
aicaddy/settings.py
    ├──→ dashboard (INSTALLED_APPS)
    ├──→ Database configuration
    └──→ Static files configuration

aicaddy/urls.py
    └──→ dashboard/urls.py

dashboard/urls.py
    └──→ dashboard/views.py (all views)

dashboard/views.py
    ├──→ dashboard/models.py (Club, GolfRound, Shot)
    ├──→ Django auth (User, login, logout)
    ├──→ scikit-learn (KNN, LabelEncoder, PCA)
    ├──→ numpy (array operations)
    └──→ dashboard/templates/ (HTML rendering)

dashboard/models.py
    ├──→ Django User model (ForeignKey)
    └──→ Django ORM (Avg, StdDev aggregations)

dashboard/templates/
    ├──→ dashboard/base.html (inherited by all pages)
    ├──→ dashboard/static/dashboard/css/style.css (styling)
    └──→ Plotly.js CDN (for visualizations)
```

#### Key Dependencies

1. **Views → Models**: All views import and query models
2. **Templates → Views**: Templates receive context from views
3. **Models → Database**: Models define schema, ORM handles queries
4. **KNN → NumPy**: KNN uses numpy arrays for features
5. **Visualization → KNN**: Visualization view uses same KNN logic as recommendation view

### Critical Files That Require Careful Handling

#### 1. `dashboard/models.py`
- **Criticality**: HIGH
- **Reason**: Schema changes require migrations
- **Modification Process**:
  1. Edit model
  2. Run `python manage.py makemigrations`
  3. Run `python manage.py migrate`
  4. Update views/templates if needed

#### 2. `dashboard/views.py` → `recommendation_view()`
- **Criticality**: HIGH
- **Reason**: Core AI logic, complex algorithm
- **Modification Considerations**:
  - Feature changes require retraining logic updates
  - K value changes affect recommendation quality
  - Confidence calculation affects user experience

#### 3. `dashboard/views.py` → `recommendation_visualization_view()`
- **Criticality**: MEDIUM
- **Reason**: Must match recommendation_view logic
- **Modification Considerations**:
  - Feature extraction must match recommendation_view
  - PCA dimensions must match frontend expectations
  - JSON response structure must match JavaScript

#### 4. `aicaddy/settings.py`
- **Criticality**: HIGH
- **Reason**: Configuration affects entire application
- **Modification Considerations**:
  - Database changes require migration
  - DEBUG=False in production
  - ALLOWED_HOSTS must include domain

#### 5. `dashboard/models.py` → `Club` methods
- **Criticality**: MEDIUM
- **Reason**: Used in dashboard and recommendations
- **Modification Considerations**:
  - Filter logic affects displayed averages
  - Return type (int vs None) affects template rendering

### Testing Approach and Coverage

#### Current Testing
- **Status**: Minimal (placeholder `tests.py` files)
- **Coverage**: No automated tests

#### Recommended Testing Strategy

1. **Unit Tests**:
   - Model methods (`get_average_distance_fairway`, etc.)
   - Helper functions (`infer_bend_from_shot_shape`)
   - KNN algorithm logic

2. **Integration Tests**:
   - View functions with database
   - Authentication flow
   - Recommendation generation

3. **Test Data**:
   - Use `dummy_shots.csv` or fixtures
   - Create test users and rounds

4. **Example Test Structure**:
   ```python
   # dashboard/tests.py
   from django.test import TestCase
   from django.contrib.auth.models import User
   from .models import Club, GolfRound, Shot
   
   class ClubModelTest(TestCase):
       def setUp(self):
           self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
           self.club = Club.objects.create(user=self.user, name='Driver')
       
       def test_get_average_distance_fairway(self):
           # Create test shots
           round = GolfRound.objects.create(user=self.user, course_name='Test')
           Shot.objects.create(golf_round=round, club=self.club, 
                              distance=250, shot_shape='Straight', lie='Fairway')
           # Test method
           avg = self.club.get_average_distance_fairway()
           self.assertEqual(avg, 250)
   ```

### Known Limitations or Technical Debt

#### 1. KNN Training on Every Request
- **Limitation**: Model retrained for each recommendation
- **Impact**: Slower response times with large datasets
- **Future Fix**: Cache model or use incremental learning

#### 2. No Model Persistence
- **Limitation**: KNN model not saved between requests
- **Impact**: Cannot track model performance over time
- **Future Fix**: Save model to disk or database

#### 3. Limited Feature Engineering
- **Limitation**: Only 4 features (distance, lie, bend, shot_shape)
- **Impact**: May miss important patterns
- **Future Enhancements**:
  - Weather conditions
  - Wind speed/direction
  - Elevation change
  - Pin position

#### 4. No Data Validation for Recommendations
- **Limitation**: No minimum data requirement enforced
- **Impact**: Poor recommendations with insufficient data
- **Current Workaround**: Error message if < 3 shots
- **Future Fix**: Enforce minimum shots per club

#### 5. PCA Visualization Accuracy
- **Limitation**: 2D visualization loses information
- **Impact**: May not accurately represent 4D space
- **Note**: Explained variance shown to user

#### 6. No User Feedback Loop
- **Limitation**: Cannot learn from user corrections
- **Impact**: Model doesn't improve with usage
- **Future Enhancement**: Allow users to rate recommendations

#### 7. Hardcoded Default Clubs
- **Limitation**: Default clubs list in `signup_view`
- **Impact**: Not customizable per user
- **Future Fix**: Make configurable or user-selectable

#### 8. No Database Indexes
- **Limitation**: No explicit indexes on foreign keys or filters
- **Impact**: Slower queries with large datasets
- **Future Fix**: Add indexes on frequently queried fields

#### 9. CSV File Location
- **Limitation**: `dummy_shots.csv` must be in project root
- **Impact**: Not flexible for different environments
- **Future Fix**: Make path configurable

#### 10. No Error Logging
- **Limitation**: Errors only printed to console
- **Impact**: Difficult to debug in production
- **Future Fix**: Implement proper logging (Django logging framework)

---

## CODE EXAMPLES

### Adding a New Feature to KNN

**Example: Add "Wind Speed" Feature**

1. **Update Model** (if storing wind speed):
   ```python
   # dashboard/models.py
   class Shot(models.Model):
       # ... existing fields ...
       wind_speed = models.IntegerField(null=True, blank=True)  # mph
   ```

2. **Update View** (add to feature extraction):
   ```python
   # dashboard/views.py → recommendation_view()
   features_list.append([
       shot.distance,
       shot.lie,
       inferred_bend,
       shot.shot_shape,
       shot.wind_speed or 0  # New feature
   ])
   ```

3. **Update Query Point**:
   ```python
   wind_speed = int(request.GET.get('wind_speed', 0))
   X_query = np.array([[distance_to_hole, lie_encoded_query, 
                       bend_encoded_query, shot_shape_encoded_query, 
                       wind_speed]])  # Add wind_speed
   ```

4. **Update Template** (add input field):
   ```html
   <!-- dashboard/templates/dashboard/recommendations.html -->
   <div class="form-group">
       <label for="wind_speed">Wind Speed (mph)</label>
       <input type="number" id="wind_speed" name="wind_speed" value="0">
   </div>
   ```

5. **Run Migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

### Modifying Confidence Calculation

**Location**: `dashboard/views.py` → `recommendation_view()` (lines ~212-247)

**Current Logic**:
```python
# Distance-weighted scores
club_scores = {}
for i, club in enumerate(neighbor_clubs):
    weight = 1.0 / (neighbor_dists[i] + 0.0001)
    club_scores[club] = club_scores.get(club, 0) + weight

# Normalize and cap
for club, score in club_scores.items():
    raw_prob = score / total_weight
    adjusted_prob = raw_prob * (0.7 + 0.3 * distance_confidence)
    club_probabilities[club] = min(0.95, adjusted_prob)
```

**Modification Example** (change cap to 90%):
```python
club_probabilities[club] = min(0.90, adjusted_prob)  # Changed from 0.95
```

### Adding a New View

**Example: Add "Club Performance" View**

1. **Create View Function**:
   ```python
   # dashboard/views.py
   @login_required
   def club_performance_view(request, club_id):
       club = get_object_or_404(Club, id=club_id, user=request.user)
       shots = Shot.objects.filter(club=club).order_by('-golf_round__date')
       return render(request, 'dashboard/club_performance.html', {
           'club': club,
           'shots': shots
       })
   ```

2. **Add URL Route**:
   ```python
   # dashboard/urls.py
   path('club/<int:club_id>/', views.club_performance_view, name='club_performance'),
   ```

3. **Create Template**:
   ```html
   <!-- dashboard/templates/dashboard/club_performance.html -->
   {% extends 'dashboard/base.html' %}
   {% block content %}
   <h2>{{ club.name }} Performance</h2>
   <!-- Template content -->
   {% endblock %}
   ```

---

## SUMMARY

AI Caddy is a Django-based web application that uses K-Nearest Neighbors (KNN) machine learning to recommend golf clubs based on historical shot data. The application features:

- **User Authentication**: Sign up, login, logout with default club setup
- **Data Management**: Record rounds, shots, load test data, clear data
- **AI Recommendations**: KNN algorithm with distance, lie, bend, and shot shape features
- **Visualization**: 2D PCA plot of feature space with Plotly.js
- **Vintage UI**: Masters green and brown color scheme with responsive design

**Key Technical Highlights**:
- Dynamic k selection for KNN
- Distance-weighted confidence scores
- Probability capping for realism
- Bend inference from historical data
- Lie-specific average distances
- PCA for visualization

**Architecture**: Traditional Django MVC pattern with PostgreSQL database, scikit-learn for ML, and vanilla JavaScript for frontend interactivity.

