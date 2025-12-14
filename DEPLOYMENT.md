# PAT System Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Deployment](#docker-deployment)
4. [Production Considerations](#production-considerations)
5. [Monitoring and Maintenance](#monitoring-and-maintenance)
6. [Troubleshooting](#troubleshooting)
7. [Backup and Recovery](#backup-and-recovery)

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+ recommended) or macOS
- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Memory**: Minimum 2GB RAM (4GB recommended for production)
- **Storage**: Minimum 10GB available disk space
- **Ports**: 8000 (API), 5432 (PostgreSQL), 5050 (pgAdmin - optional)

### Software Installation

```bash
# Install Docker (Ubuntu/Debian)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker compose version
```

## Environment Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd pat
```

### 2. Configure Environment Variables

Create `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your production values:

```bash
# Application Settings
APP_NAME="PAT API"
APP_VERSION=0.1.0
DEBUG=false  # IMPORTANT: Set to false in production

# Database Configuration
POSTGRES_DB=pat_db
POSTGRES_USER=pat_user
POSTGRES_PASSWORD=<STRONG_PASSWORD_HERE>
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://pat_user:<STRONG_PASSWORD_HERE>@postgres:5432/pat_db

# JWT Configuration
JWT_SECRET_KEY=<GENERATE_STRONG_SECRET_KEY>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# CORS Settings
CORS_ORIGINS=["https://yourdomain.com"]

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60

# pgAdmin (Optional - for database management)
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=<STRONG_PASSWORD_HERE>
PGADMIN_PORT=5050
```

### 3. Generate Secure Secrets

**Generate JWT Secret Key:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Generate Strong Passwords:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

### 4. Security Checklist

- [ ] Set `DEBUG=false` in production
- [ ] Use strong, unique passwords for all services
- [ ] Generate a cryptographically secure JWT secret key
- [ ] Configure CORS to only allow your frontend domain
- [ ] Use HTTPS in production (configure reverse proxy)
- [ ] Restrict database port (5432) - don't expose publicly
- [ ] Restrict pgAdmin port (5050) or disable in production

## Docker Deployment

### Development Deployment

```bash
# Build and start all services
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f

# View specific service logs
docker compose logs -f app
```

### Production Deployment

#### 1. Build Production Image

```bash
# Set production version
export APP_VERSION=0.1.0

# Build image
docker compose build app

# Tag for production
docker tag pat:${APP_VERSION} pat:production
```

#### 2. Start Services

```bash
# Start in detached mode
docker compose up -d

# Wait for services to be healthy
docker compose ps

# Verify application is running
curl http://localhost:8000/health
```

#### 3. Verify Database Migration

```bash
# Check migration logs
docker compose logs migration

# Verify tables exist
docker compose exec postgres psql -U pat_user -d pat_db -c "\dt"
```

#### 4. Verify Sample FCS File Initialization

```bash
# Check application logs for initialization
docker compose logs app | grep "Sample FCS"

# Expected output:
# Sample FCS file initialized: 34297 events, 26 parameters
```

### Service Management

```bash
# Stop all services
docker compose down

# Restart specific service
docker compose restart app

# View resource usage
docker stats

# Scale services (if needed)
docker compose up -d --scale app=3
```

## Production Considerations

### 1. Reverse Proxy Setup (Nginx)

Create `/etc/nginx/sites-available/pat-api`:

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Proxy Settings
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # File upload size limit
    client_max_body_size 100M;

    # Logging
    access_log /var/log/nginx/pat-api-access.log;
    error_log /var/log/nginx/pat-api-error.log;
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/pat-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 2. SSL Certificate (Let's Encrypt)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d api.yourdomain.com

# Auto-renewal is configured by default
# Test renewal
sudo certbot renew --dry-run
```

### 3. Firewall Configuration

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Block direct access to application ports
sudo ufw deny 8000/tcp
sudo ufw deny 5432/tcp
sudo ufw deny 5050/tcp

# Enable firewall
sudo ufw enable
sudo ufw status
```

### 4. Docker Compose Production Override

Create `docker-compose.prod.yml`:

```yaml
services:
  postgres:
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  app:
    restart: always
    environment:
      DEBUG: "false"
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    # Remove hot-reload volumes in production
    volumes:
      - ./uploads:/app/uploads
      - ./sample_data:/app/sample_data

  migration:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # Disable pgAdmin in production (optional)
  pgadmin:
    profiles:
      - tools
```

Deploy with production override:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 5. Environment-Specific Settings

**Production `.env` template:**
```bash
# Application
APP_NAME="PAT API"
APP_VERSION=0.1.0
DEBUG=false

# Database
POSTGRES_DB=pat_db
POSTGRES_USER=pat_user
POSTGRES_PASSWORD=${PROD_DB_PASSWORD}
DATABASE_URL=postgresql+asyncpg://pat_user:${PROD_DB_PASSWORD}@postgres:5432/pat_db

# Security
JWT_SECRET_KEY=${PROD_JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# CORS - Only allow your frontend
CORS_ORIGINS=["https://app.yourdomain.com"]

# Rate Limiting - Adjust based on expected traffic
RATE_LIMIT_PER_MINUTE=100
```

## Monitoring and Maintenance

### 1. Health Checks

```bash
# Application health
curl https://api.yourdomain.com/health

# Expected response:
# {"status": "healthy"}

# Database health
docker compose exec postgres pg_isready -U pat_user

# Service status
docker compose ps
```

### 2. Log Monitoring

```bash
# View application logs
docker compose logs -f app --tail 100

# View database logs
docker compose logs -f postgres --tail 100

# Search for errors
docker compose logs app | grep -i error

# Monitor in real-time
docker compose logs -f --tail 0 app
```

### 3. Resource Monitoring

```bash
# Container resource usage
docker stats

# Disk usage
docker system df
df -h

# Database size
docker compose exec postgres psql -U pat_user -d pat_db -c "
SELECT pg_size_pretty(pg_database_size('pat_db')) AS db_size;"
```

### 4. Performance Monitoring

**Install and configure Prometheus + Grafana (optional):**

Create `docker-compose.monitoring.yml`:

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: pat_prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - pat_network

  grafana:
    image: grafana/grafana:latest
    container_name: pat_grafana
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    networks:
      - pat_network

volumes:
  prometheus_data:
  grafana_data:

networks:
  pat_network:
    external: true
```

### 5. Database Maintenance

```bash
# Vacuum database (reclaim storage)
docker compose exec postgres psql -U pat_user -d pat_db -c "VACUUM ANALYZE;"

# Check database bloat
docker compose exec postgres psql -U pat_user -d pat_db -c "
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Reindex
docker compose exec postgres psql -U pat_user -d pat_db -c "REINDEX DATABASE pat_db;"
```

## Troubleshooting

### Common Issues

#### 1. Services Won't Start

```bash
# Check logs
docker compose logs

# Check for port conflicts
sudo netstat -tulpn | grep -E '8000|5432|5050'

# Reset and restart
docker compose down
docker compose up -d
```

#### 2. Database Connection Errors

```bash
# Check database is healthy
docker compose exec postgres pg_isready -U pat_user

# Verify connection from app
docker compose exec app python -c "
from app.common.database import async_session_maker
import asyncio
async def test():
    async with async_session_maker() as session:
        await session.execute('SELECT 1')
asyncio.run(test())
"

# Check DATABASE_URL in .env
docker compose exec app env | grep DATABASE_URL
```

#### 3. Migration Failures

```bash
# Check migration status
docker compose exec app alembic current

# View migration history
docker compose exec app alembic history

# Reset migration (CAUTION: destroys data)
docker compose down -v
docker compose up -d
```

#### 4. Sample FCS File Not Loading

```bash
# Check if sample file exists
ls -lh sample_data/sample.fcs

# Check volume mount
docker compose exec app ls -lh /app/sample_data/

# Check initialization logs
docker compose logs app | grep -i "sample\|fcs"

# Manually trigger (if needed)
docker compose exec app python -c "
from app.common.startup import initialize_sample_fcs_file
from app.common.database import async_session_maker
import asyncio
async def init():
    async with async_session_maker() as session:
        await initialize_sample_fcs_file(session)
asyncio.run(init())
"
```

#### 5. High Memory Usage

```bash
# Check container stats
docker stats

# Restart services
docker compose restart

# Prune unused resources
docker system prune -a --volumes
```

#### 6. Rate Limit Issues

```bash
# Check current rate limit setting
docker compose exec app env | grep RATE_LIMIT

# Adjust in .env and restart
# RATE_LIMIT_PER_MINUTE=100
docker compose restart app
```

### Debug Mode

Enable debug logging temporarily:

```bash
# Edit .env
DEBUG=true

# Restart application
docker compose restart app

# View detailed logs
docker compose logs -f app
```

**IMPORTANT:** Remember to disable debug mode after troubleshooting!

## Backup and Recovery

### 1. Database Backup

**Manual Backup:**
```bash
# Create backup directory
mkdir -p backups

# Backup database
docker compose exec postgres pg_dump -U pat_user -Fc pat_db > backups/pat_db_$(date +%Y%m%d_%H%M%S).dump

# Verify backup
ls -lh backups/
```

**Automated Daily Backup Script:**

Create `scripts/backup-db.sh`:
```bash
#!/bin/bash

BACKUP_DIR="/path/to/backups"
RETENTION_DAYS=7

# Create backup
BACKUP_FILE="${BACKUP_DIR}/pat_db_$(date +%Y%m%d_%H%M%S).dump"
docker compose exec -T postgres pg_dump -U pat_user -Fc pat_db > "${BACKUP_FILE}"

# Compress
gzip "${BACKUP_FILE}"

# Remove old backups
find "${BACKUP_DIR}" -name "pat_db_*.dump.gz" -mtime +${RETENTION_DAYS} -delete

echo "Backup completed: ${BACKUP_FILE}.gz"
```

Add to crontab:
```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /path/to/pat/scripts/backup-db.sh >> /var/log/pat-backup.log 2>&1
```

### 2. Database Restore

```bash
# Stop application
docker compose stop app

# Restore from backup
docker compose exec -T postgres pg_restore -U pat_user -d pat_db --clean < backups/pat_db_20241214_020000.dump

# Or from compressed backup
gunzip -c backups/pat_db_20241214_020000.dump.gz | docker compose exec -T postgres pg_restore -U pat_user -d pat_db --clean

# Restart application
docker compose start app
```

### 3. Full System Backup

```bash
# Backup script
#!/bin/bash

BACKUP_ROOT="/path/to/backups/full"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_ROOT}/backup_${TIMESTAMP}"

mkdir -p "${BACKUP_DIR}"

# Backup database
docker compose exec -T postgres pg_dump -U pat_user -Fc pat_db > "${BACKUP_DIR}/database.dump"

# Backup uploaded files
cp -r uploads "${BACKUP_DIR}/"

# Backup environment configuration
cp .env "${BACKUP_DIR}/.env.backup"

# Backup docker-compose configuration
cp docker-compose.yml "${BACKUP_DIR}/"

# Create tarball
tar -czf "${BACKUP_ROOT}/full_backup_${TIMESTAMP}.tar.gz" -C "${BACKUP_ROOT}" "backup_${TIMESTAMP}"

# Cleanup
rm -rf "${BACKUP_DIR}"

echo "Full backup completed: full_backup_${TIMESTAMP}.tar.gz"
```

### 4. Disaster Recovery

**Complete System Restore:**

```bash
# Extract backup
tar -xzf full_backup_20241214_020000.tar.gz

# Restore environment
cp backup_20241214_020000/.env.backup .env

# Start services
docker compose up -d postgres
sleep 10

# Restore database
docker compose exec -T postgres pg_restore -U pat_user -d pat_db --clean < backup_20241214_020000/database.dump

# Restore uploads
cp -r backup_20241214_020000/uploads ./

# Start application
docker compose up -d
```

## Update and Migration

### Application Updates

```bash
# Pull latest code
git pull origin main

# Backup database first!
./scripts/backup-db.sh

# Rebuild and restart
docker compose down
docker compose build
docker compose up -d

# Verify migration
docker compose logs migration

# Test application
curl https://api.yourdomain.com/health
```

### Database Schema Updates

```bash
# Create new migration (if needed)
docker compose exec app alembic revision --autogenerate -m "Description of changes"

# Apply migrations
docker compose exec app alembic upgrade head

# Rollback if needed
docker compose exec app alembic downgrade -1
```

## Security Best Practices

1. **Regular Updates**: Keep Docker, OS, and dependencies updated
2. **Secret Management**: Never commit `.env` to version control
3. **Access Control**: Use strong passwords and limit SSH access
4. **Monitoring**: Set up alerts for unusual activity
5. **Backups**: Automate and test backup restoration regularly
6. **Audit Logs**: Review audit logs periodically
7. **HTTPS**: Always use HTTPS in production
8. **Database**: Don't expose PostgreSQL port publicly
9. **Rate Limiting**: Configure appropriate rate limits
10. **Dependencies**: Regularly scan for vulnerabilities

## Support and Documentation

- **API Documentation**: https://api.yourdomain.com/docs
- **ReDoc**: https://api.yourdomain.com/redoc
- **Health Check**: https://api.yourdomain.com/health
- **Repository**: <repository-url>
- **Issue Tracker**: <issue-tracker-url>

---

**Deployment Checklist:**

- [ ] Prerequisites installed (Docker, Docker Compose)
- [ ] Environment variables configured
- [ ] Strong passwords and secrets generated
- [ ] DEBUG=false in production
- [ ] CORS configured correctly
- [ ] Docker services running
- [ ] Database migrations applied
- [ ] Sample FCS file initialized
- [ ] All tests passing (68/68)
- [ ] Reverse proxy configured (Nginx)
- [ ] SSL certificates installed
- [ ] Firewall configured
- [ ] Backup script configured
- [ ] Monitoring setup
- [ ] Health checks verified
- [ ] Documentation reviewed

**For additional help, refer to CLAUDE.md for development history and technical details.**
