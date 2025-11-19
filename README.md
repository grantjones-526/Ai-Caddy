# 🏌️‍♂️ Ai Caddy

**AI-Powered Golf Club Recommendation System**

Ai Caddy is an intelligent web application that uses machine learning to help golfers make smarter club selections on the course. By analyzing your historical shot data, Ai Caddy provides personalized club recommendations based on distance, lie, hole conditions, and your playing style.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Available-brightgreen)](https://aicaddy.onrender.com)
[![Django](https://img.shields.io/badge/Django-5.2.7-092E20?logo=django)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## ✨ Features

### 🎯 Smart Recommendations
- **K-Nearest Neighbors (KNN) Algorithm**: Analyzes your past shots to recommend the best club for your current situation
- **Multi-Factor Analysis**: Considers distance to hole, lie (fairway/rough/tee box), hole bend, and shot shape
- **Confidence Scoring**: Each recommendation includes confidence levels (High/Medium/Low) based on data quality
- **Fallback Logic**: Automatically recommends your furthest club when input yardage exceeds historical data

### 📊 Performance Tracking
- **Club Statistics**: Track average distances for each club from different lies
- **Consistency Metrics**: Standard deviation calculations show shot consistency
- **Round History**: View detailed statistics for all your recorded rounds
- **Visual Analytics**: Interactive visualizations showing shot clustering in feature space

### 📱 GPS Shot Tracking
- **On-Course Data Entry**: Use your phone's GPS to automatically measure shot distances
- **Seamless Integration**: Quick and easy shot entry while playing

### 📥 Launch Monitor Integration
- **Multi-Device Support**: Import data from popular launch monitors:
  - Garmin R10
  - SkyTrak+
  - Flightscope Mevo+
  - Arccos Caddie
  - Generic Launch Monitor
- **CSV Import**: Bulk import shot data from CSV files
- **Data Preview**: Review and confirm imported data before adding to your database

### 🎨 Modern UI/UX
- **Responsive Design**: Fully optimized for desktop, tablet, and mobile devices
- **Pixel Art Theme**: Retro-inspired design with Masters Tournament color scheme
- **Mobile-First**: Card-based layouts for easy viewing on smartphones
- **Intuitive Navigation**: Clean, user-friendly interface

---

## 🛠️ Tech Stack

### Backend
- **Django 5.2.7** - High-level Python web framework
- **PostgreSQL** - Production database (SQLite for development)
- **scikit-learn** - Machine learning library (KNN algorithm)
- **NumPy** - Numerical computing
- **python-decouple** - Environment variable management

### Frontend
- **HTML5/CSS3** - Modern web standards
- **JavaScript** - Client-side interactivity
- **Plotly.js** - Data visualization
- **Google Fonts** - Press Start 2P (pixel font)

### Deployment
- **Gunicorn** - Python WSGI HTTP Server
- **WhiteNoise** - Static file serving
- **Render.com** - Cloud hosting platform

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- PostgreSQL (for production) or SQLite (for development)
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/aicaddy.git
   cd aicaddy
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the project root:
   ```env
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   DB_USE_SQLITE=True
   
   # For PostgreSQL (production)
   # DB_USE_SQLITE=False
   # DB_NAME=aicaddy_db
   # DB_USER=your_db_user
   # DB_PASSWORD=your_db_password
   # DB_HOST=localhost
   # DB_PORT=5432
   ```

5. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

7. **Collect static files**
   ```bash
   python manage.py collectstatic
   ```

8. **Run the development server**
   ```bash
   python manage.py runserver
   ```

9. **Access the application**
   
   Open your browser and navigate to `http://localhost:8000`

---

## 📖 Usage

### First Time Setup

1. **Sign Up**: Create a new account
2. **Default Clubs**: A default set of clubs is automatically added to your bag
3. **Add Rounds**: Start tracking your golf rounds

### Adding Rounds

1. Navigate to **"Add Round"** from the dashboard
2. Enter course name and date
3. Add shots manually or use GPS tracking:
   - **Manual Entry**: Select club, distance, lie, and shot shape
   - **GPS Tracking**: Use your phone's GPS to measure distances automatically
4. Save your round

### Getting Recommendations

1. Go to **"Get Recommendation"**
2. Enter:
   - Distance to hole (yards)
   - Lie (Fairway, Rough, Tee Box, or Sand)
   - Hole bend (Straight, Left, or Right)
   - Shot shape preference (Straight, Fade, Draw, Slice, or Hook)
3. Click **"Get Recommendation"**
4. Review the top 3 club recommendations with confidence scores

### Importing Launch Monitor Data

1. Navigate to **"Import Launch Monitor"**
2. Select your device type
3. Upload your CSV file
4. Review the preview
5. Confirm import

### Viewing Statistics

- **Dashboard**: View club performance averages and consistency metrics
- **Round Detail**: Click on any round to see detailed shot information
- **Visualizations**: Explore interactive charts showing your shot patterns

---

## 🌐 Deployment

### Deploying to Render.com

1. **Push your code to GitHub**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Create a Render account** and connect your GitHub repository

3. **Create a PostgreSQL database** on Render

4. **Create a new Web Service** with these settings:
   - **Build Command**: `./build.sh` or `bash build.sh`
   - **Start Command**: `gunicorn aicaddy.wsgi:application`
   - **Environment**: Python 3

5. **Set environment variables** in Render:
   ```
   SECRET_KEY=your-secret-key
   DEBUG=False
   ALLOWED_HOSTS=your-app.onrender.com
   DB_USE_SQLITE=False
   DB_NAME=your_db_name
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_HOST=your_db_host
   DB_PORT=5432
   ```

6. **Deploy**: Render will automatically build and deploy your application

### Build Script

The `build.sh` script automates:
- Dependency installation
- Database migrations
- Static file collection

---

## 📁 Project Structure

```
aicaddy/
├── aicaddy/              # Django project settings
│   ├── settings.py      # Configuration
│   ├── urls.py          # URL routing
│   └── wsgi.py          # WSGI config
├── dashboard/            # Main application
│   ├── models.py        # Database models
│   ├── views.py         # View logic
│   ├── urls.py          # App URLs
│   ├── parsers.py       # Launch monitor parsers
│   └── templates/       # HTML templates
├── static/              # Static files
│   └── dashboard/
│       ├── css/         # Stylesheets
│       └── images/      # Images
├── build.sh             # Deployment script
├── Procfile             # Process file for Render
├── requirements.txt     # Python dependencies
└── manage.py            # Django management script
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Masters Tournament** - Color scheme inspiration
- **Google Fonts** - Press Start 2P font
- **Django Community** - Excellent documentation and support
- **scikit-learn** - Powerful machine learning tools

---

## 📧 Contact

For questions, suggestions, or support, please open an issue on GitHub.

---

## 🎯 Roadmap

- [ ] Advanced analytics dashboard
- [ ] Weather condition integration
- [ ] Multi-user round sharing
- [ ] Mobile app (iOS/Android)
- [ ] Integration with more launch monitors
- [ ] Shot trajectory visualization
- [ ] Course-specific recommendations

---

**Made with ❤️ for golfers who want to improve their game through data-driven decisions.**

