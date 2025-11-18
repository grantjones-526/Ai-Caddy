# Free Hosting Guide for Ai Caddy

## Project Size Assessment

Your project is **well-suited for free hosting**:
- ✅ Small Django application (~1,000 lines of code)
- ✅ Lightweight dependencies (Django, scikit-learn, numpy)
- ✅ Small database footprint (text-based data, no large files)
- ✅ Minimal static files (CSS, images)
- ✅ No heavy media uploads

**Estimated resource needs:**
- Storage: < 100MB (code + database)
- RAM: 512MB-1GB (sufficient for Django + ML libraries)
- Database: < 100MB (unless you have thousands of users)

---

## Recommended Free Hosting Options

### 1. **Render** (Best for Django) ⭐ Recommended
**Free Tier:**
- 750 hours/month (enough for 24/7 operation)
- 512MB RAM
- Free PostgreSQL database
- Automatic SSL certificates
- Custom domain support

**Limitations:**
- App spins down after 15 minutes of inactivity (freezes on first request)
- Limited to 1 free web service

**Setup:**
- Connect GitHub repo
- Auto-detects Django
- Easy PostgreSQL setup
- Environment variables support

**Best for:** Demo/prototype, low traffic

---

### 2. **Railway** (Great Developer Experience)
**Free Tier:**
- $5 credit/month (usually enough for small apps)
- 512MB RAM
- Free PostgreSQL included
- No spin-down (always on)
- Automatic deployments

**Limitations:**
- Credit-based (may need to upgrade if you exceed $5/month)
- Requires credit card (but won't charge if you stay within free tier)

**Best for:** Active development, always-on requirement

---

### 3. **Fly.io** (Good Performance)
**Free Tier:**
- 3 shared-cpu-1x VMs (256MB RAM each)
- 3GB persistent volume storage
- Free PostgreSQL (limited)
- Global edge network

**Limitations:**
- More complex setup
- Limited to 3 VMs on free tier

**Best for:** If you need better performance/global distribution

---

### 4. **PythonAnywhere** (Simplest)
**Free Tier:**
- 1 web app
- 512MB disk space
- MySQL database (not PostgreSQL)
- Limited to 1 custom domain
- External requests limited

**Limitations:**
- Must use MySQL instead of PostgreSQL (requires code changes)
- No HTTPS on free tier (only on subdomain)
- Limited external API calls

**Best for:** Quick testing, learning

---

## Quick Setup Guide for Render (Recommended)

### Step 1: Prepare Your Project

1. **Create `render.yaml`** (optional, for easier setup):
```yaml
services:
  - type: web
    name: aicaddy
    env: python
    buildCommand: pip install -r requirements.txt && python manage.py collectstatic --noinput
    startCommand: gunicorn aicaddy.wsgi:application
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: SECRET_KEY
        generateValue: true
      - key: DEBUG
        value: False
      - key: DB_USE_SQLITE
        value: False
```

2. **Create `Procfile`**:
```
web: gunicorn aicaddy.wsgi:application
```

3. **Update `requirements.txt`** (add gunicorn):
```
Django==5.2.7
psycopg2-binary==2.9.11
python-decouple==3.8
scikit-learn>=1.3.0
numpy>=1.26.0
gunicorn>=21.2.0
whitenoise>=6.6.0
```

4. **Update `settings.py`** for production:
```python
# Add to settings.py
ALLOWED_HOSTS = ['your-app.onrender.com', 'yourdomain.com']

# For static files (add whitenoise)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add this
    # ... rest of middleware
]

STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

### Step 2: Deploy to Render

1. Push your code to GitHub
2. Go to [render.com](https://render.com) and sign up
3. Click "New +" → "Web Service"
4. Connect your GitHub repo
5. Configure:
   - **Name**: aicaddy
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - **Start Command**: `gunicorn aicaddy.wsgi:application`
6. Add environment variables:
   - `SECRET_KEY` (generate a new one)
   - `DEBUG=False`
   - `DB_USE_SQLITE=False`
7. Create PostgreSQL database (free tier)
8. Add database environment variables:
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
9. Deploy!

---

## Important Considerations

### Database Choice
- **SQLite**: Works for free hosting but not recommended for production
- **PostgreSQL**: Better for production, available on most free tiers
- **MySQL**: Available on PythonAnywhere (requires code changes)

### Static Files
- Use **WhiteNoise** for serving static files (no CDN needed for small apps)
- Run `collectstatic` during deployment
- Static files will be served from your Django app

### Environment Variables
Store sensitive data in environment variables:
- `SECRET_KEY`
- `DEBUG`
- Database credentials
- Any API keys (if you add features later)

### Performance Tips for Free Tier
1. **Optimize database queries** (you've already done this with `select_related` and `prefetch_related`)
2. **Use caching** (if needed, Redis available on some free tiers)
3. **Limit data retention** (archive old rounds if needed)
4. **Optimize ML calculations** (your KNN is already efficient)

---

## Cost Breakdown (Free Tier)

| Resource | Render | Railway | Fly.io |
|----------|--------|---------|--------|
| Web Service | ✅ Free | ✅ Free ($5 credit) | ✅ Free (3 VMs) |
| Database | ✅ Free PostgreSQL | ✅ Free PostgreSQL | ⚠️ Limited |
| Storage | ✅ Unlimited | ✅ Included | ✅ 3GB |
| Bandwidth | ✅ Unlimited | ✅ Included | ✅ Included |
| SSL/HTTPS | ✅ Free | ✅ Free | ✅ Free |
| Custom Domain | ✅ Free | ✅ Free | ✅ Free |

---

## When to Upgrade

Consider paid hosting if:
- You have > 100 active users
- Database exceeds 1GB
- You need always-on (no spin-down)
- You need more RAM for faster ML processing
- You exceed free tier limits

**Typical paid hosting costs:**
- Render: $7-25/month
- Railway: $5-20/month
- Fly.io: $5-15/month

---

## Quick Start Checklist

- [ ] Add `gunicorn` and `whitenoise` to `requirements.txt`
- [ ] Update `ALLOWED_HOSTS` in `settings.py`
- [ ] Configure `STATIC_ROOT` and WhiteNoise
- [ ] Create `Procfile`
- [ ] Set `DEBUG=False` for production
- [ ] Generate new `SECRET_KEY`
- [ ] Push code to GitHub
- [ ] Deploy to chosen platform
- [ ] Run migrations on production database
- [ ] Test the live site!

---

## Recommended: Start with Render

**Why Render:**
- Easiest Django deployment
- Free PostgreSQL included
- Good documentation
- Automatic SSL
- Easy environment variable management

**URL Format:** `https://your-app-name.onrender.com`

Perfect for your demo and initial users!

