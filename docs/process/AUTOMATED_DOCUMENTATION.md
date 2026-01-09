# Automated Documentation with Playwright Screenshots

DiveOps includes tools to automatically capture screenshots of the application and embed them into help documentation. This ensures documentation stays current as the application evolves.

## Overview

The documentation automation system consists of two components:

1. **Screenshot Capture Script** - Uses Playwright to navigate the application and capture full-page screenshots
2. **Embed Screenshots Command** - Updates CMS help articles with the captured images

## Prerequisites

```bash
# Install Playwright
pip install playwright

# Install Chromium browser
playwright install chromium
```

## Capturing Screenshots

Run the screenshot capture script to take fresh screenshots of all documented pages:

```bash
cd testbed
python scripts/capture_help_screenshots.py
```

### Options

| Option | Description |
|--------|-------------|
| `--headed` | Show the browser window while capturing |
| `--base-url URL` | Specify a different server URL (default: http://localhost:8000) |
| `--output-dir PATH` | Save screenshots to a custom location |

### Example

```bash
# Capture with visible browser
python scripts/capture_help_screenshots.py --headed

# Capture from staging server
python scripts/capture_help_screenshots.py --base-url https://staging.example.com
```

## How It Works

1. The script creates an authenticated session using a staff user (no password changes)
2. Playwright browser navigates to each application page
3. Full-page screenshots are captured and saved to `media/help/screenshots/`
4. Screenshots are named to match their help article (e.g., `agreements-creating-agreements.png`)

### Session Authentication

The script authenticates by directly creating a Django session in the database:

```python
session = SessionStore()
session["_auth_user_id"] = str(staff_user.pk)
session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
session["_auth_user_hash"] = staff_user.get_session_auth_hash()
session.create()
```

This approach:
- Does not modify or expose any passwords
- Creates a valid session cookie for Playwright to use
- Works with any authentication backend

## Embedding Screenshots in Articles

After capturing screenshots, embed them into the CMS help articles:

```bash
python manage.py embed_help_screenshots
```

### Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview changes without modifying the database |
| `--media-url URL` | Custom URL prefix for images |

### What It Does

1. Iterates through all help articles
2. Checks if article already has a screenshot embedded
3. Creates an image block at the top of the article
4. Updates the published snapshot for immediate visibility

## Adding New Screenshots

To add screenshots for new help articles:

1. **Add the article** to `HELP_SECTIONS` in `help_views.py`:
   ```python
   {
       "slug": "system",
       "articles": [
           {"slug": "new-feature", "title": "New Feature"},
       ],
   }
   ```

2. **Map to application URL** in `capture_help_screenshots.py`:
   ```python
   ARTICLE_TO_APP_URL = {
       ("system", "new-feature"): {
           "url": "/staff/diveops/new-feature/",
           "description": "New feature page",
       },
   }
   ```

3. **Map to screenshot file** in `embed_help_screenshots.py`:
   ```python
   ARTICLE_SCREENSHOTS = {
       ("system", "new-feature"): "system-new-feature.png",
   }
   ```

4. **Run both scripts**:
   ```bash
   python scripts/capture_help_screenshots.py
   python manage.py embed_help_screenshots
   ```

## Keeping Documentation Current

Run these scripts periodically (or after major UI changes) to keep screenshots up to date:

```bash
# Capture fresh screenshots
python scripts/capture_help_screenshots.py

# Re-embed (command skips articles that already have images)
python manage.py embed_help_screenshots
```

### CI/CD Integration

Consider adding screenshot capture to your CI pipeline:

```yaml
# Example GitHub Actions step
- name: Update documentation screenshots
  run: |
    python scripts/capture_help_screenshots.py
    python manage.py embed_help_screenshots
```

## File Locations

| File | Purpose |
|------|---------|
| `scripts/capture_help_screenshots.py` | Playwright screenshot capture script |
| `diveops/management/commands/embed_help_screenshots.py` | CMS embedding command |
| `diveops/help_views.py` | Help section/article configuration |
| `media/help/screenshots/` | Screenshot storage directory |

## Troubleshooting

### Browser not launching

Ensure Chromium is installed:
```bash
playwright install chromium
```

### Authentication failing

The script requires at least one active staff user:
```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
print(User.objects.filter(is_staff=True, is_active=True).count(), 'staff users')
"
```

### Screenshots not appearing

1. Check that the development server is running on the expected port
2. Verify the media URL is configured correctly in Django settings
3. Ensure `MEDIA_URL` and `MEDIA_ROOT` are set in `settings.py`
