# ACM Connect - Discord Internship Bot

![ConnectBanner](https://github.com/user-attachments/assets/9f99f591-6c65-4666-8b93-4c2f55da2d1e)

<img width="616" alt="image" src="https://github.com/user-attachments/assets/7751b58e-99bd-4e2c-a9e6-80c93e2f2192">

## 🤖 Bot Invite Links

### Production Bot
**[📥 Invite Production Bot](https://discord.com/oauth2/authorize?client_id=1300902289816682516&permissions=8&integration_type=0&scope=bot)**
- Use this for live Discord servers
- Posts daily at 9:15 PM EST with role notifications
- Requires activation key for server registration

### Test Bot  
**[🧪 Invite Test Bot](https://discord.com/oauth2/authorize?client_id=1365002882817982485&permissions=8&integration_type=0&scope=bot)**
- Use this for testing and development
- Safe for experimentation without affecting production servers
- Can be configured for rapid testing or staging modes

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Environment Modes](#environment-modes)
- [Prerequisites](#prerequisites)
- [AWS Setup](#aws-setup)
- [Environment Variables](#environment-variables)
- [Installation & Deployment](#installation--deployment)
- [SDK Admin Dashboard](#sdk-admin-dashboard)
- [File Structure](#file-structure)
- [Deployment Pipeline](#deployment-pipeline)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🎯 Overview

ACM Connect is a sophisticated Discord bot that automatically posts internship opportunities from Simplify's repository to Discord servers. The system uses AWS infrastructure for data collection and processing, with intelligent filtering to show only relevant upcoming internship terms.

### Key Capabilities
- **Automated Daily Posting**: Posts internships at 9:15 PM EST daily
- **Smart Term Filtering**: Only shows internships for upcoming terms (excludes current term)
- **Multi-Server Support**: Can be deployed across multiple Discord servers
- **Admin Dashboard**: Web-based management interface for server administration
- **Multiple Environment Modes**: Test, Stage, and Production configurations

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GitHub API    │───▶│   AWS Lambda     │───▶│   AWS S3        │
│  (Simplify)     │    │  (Data Fetcher)  │    │  (Data Store)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Discord API   │◀───│   Discord Bot    │◀───│   EC2 Instance  │
│   (Servers)     │    │  (ACM Connect)   │    │  (Host Server)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Admin SDK      │
                       │ (Streamlit UI)  │
                       └─────────────────┘
```

### Data Flow
1. **AWS Lambda** fetches internship data from Simplify's GitHub repository daily at 9:00 PM EST
2. **Raw data** is stored in AWS S3 bucket as `listings.json`
3. **Discord Bot** (running on EC2) fetches data from S3 at 9:15 PM EST
4. **Smart filtering** removes current term internships and old postings
5. **Formatted posts** are sent to configured Discord forum channels
6. **Admin SDK** provides web interface for managing servers and debugging

## ✨ Features

### 🤖 Automated Internship Posting
- **Daily Schedule**: Runs at 9:15 PM EST (2:15 AM UTC)
- **Smart Filtering**: Only posts internships for upcoming terms
- **Rich Embeds**: Beautiful Discord embeds with company logos, locations, terms, and sponsorship info
- **Forum Integration**: Creates dedicated forum threads for each day's postings
- **Batch Processing**: Handles Discord's embed limits intelligently

### 🌐 Multi-Server Support
- **Guild Management**: Supports multiple Discord servers simultaneously
- **Role Notifications**: Configurable role mentions for new postings
- **Channel Configuration**: Flexible forum channel setup per server

### 🔧 Environment Modes
- **Production Mode**: Full functionality with notifications
- **Stage Mode**: Production-like testing without notifications
- **Test Mode**: Rapid testing with 5-second intervals

## 🚦 Environment Modes

ACM Connect supports three distinct operating modes:

### Production Mode
```bash
TEST_MODE=false
STAGE=false
```
- Uses production Discord servers (`guilds.json`)
- Sends role notifications
- Runs daily at 9:15 PM EST
- Posts actual internship listings

### Stage Mode  
```bash
TEST_MODE=false
STAGE=true
```
- Uses **test bot token** (`TEST_BOT_TOKEN`) and test Discord servers (`test_guilds.json`)
- **NO role notifications** (silent posting)
- Runs daily at 9:15 PM EST
- Posts actual internship listings
- Perfect for testing production deployment without spamming users

### Test Mode
```bash
TEST_MODE=true
STAGE=false (automatically disabled if both are true)
```
- Uses test Discord servers (`test_guilds.json`)
- Sends role notifications (for testing notification functionality)
- Runs every 5 seconds for rapid testing
- Posts actual internship listings (no more dummy data)
- Sets `posted_today` flag to prevent multiple posts per restart

### Mode Priority
If both `TEST_MODE=true` and `STAGE=true` are set, **TEST_MODE takes precedence** and STAGE is automatically disabled with a warning logged.

## 📋 Prerequisites

### Required Accounts & Services
- **AWS Account** with programmatic access
- **Discord Developer Account** with bot application
- **GitHub Personal Access Token** (for Simplify repository access)
- **EC2 Instance** (Ubuntu/Amazon Linux recommended)
- **Domain/Subdomain** (optional, for SDK hosting)

### Required Software
- **Python 3.11+**
- **Docker & Docker Compose**
- **Git**
- **AWS CLI** (optional, for debugging)

## ☁️ AWS Setup

### 1. Create S3 Bucket
```bash
# Create bucket (replace with your preferred name)
aws s3 mb s3://your-acm-github-data --region us-east-2
```

**Required S3 Files:**
- `listings.json` - Main internship data (populated by Lambda)
- `guilds.json` - Production Discord servers configuration
- `test_guilds.json` - Test Discord servers configuration  
- `keys.json` - Activation keys for server registration
- `companies.json` - Cached company logo URLs

### 2. Create IAM User
Create an IAM user with the following policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-acm-github-data",
                "arn:aws:s3:::your-acm-github-data/*"
            ]
        }
    ]
}
```

Save the **Access Key ID** and **Secret Access Key** for environment variables.

### 3. Deploy Lambda Function

#### Create Lambda Function
1. Go to AWS Lambda Console
2. Create new function: `acm-internship-fetcher`
3. Runtime: Python 3.11
4. Upload the code from `data/lambda_function.py`

#### Set Lambda Environment Variables
```bash
GH_API_TOKEN=your_github_personal_access_token
ENDPOINT=https://api.github.com/repos/SimplifyJobs/Summer2025-Internships/contents/README.md
```

#### Create EventBridge Schedule
Create a schedule to run Lambda daily at 9:00 PM EST (2:00 AM UTC):

```bash
# EventBridge rule
aws events put-rule \
    --name acm-daily-fetch \
    --schedule-expression "cron(0 2 * * ? *)" \
    --description "Daily internship data fetch"

# Add Lambda target
aws events put-targets \
    --rule acm-daily-fetch \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-2:ACCOUNT:function:acm-internship-fetcher"
```

### 4. Launch EC2 Instance

#### Instance Specifications
- **Instance Type**: t3.micro (sufficient for Discord bot)
- **OS**: Ubuntu 22.04 LTS or Amazon Linux 2023
- **Storage**: 8GB GP3 (default)
- **Security Group**: Allow SSH (port 22) and optionally HTTP/HTTPS for SDK

#### Security Group Rules
```bash
# SSH access
Type: SSH, Protocol: TCP, Port: 22, Source: Your IP

# Optional: HTTP for SDK
Type: HTTP, Protocol: TCP, Port: 80, Source: 0.0.0.0/0

# Optional: HTTPS for SDK  
Type: HTTPS, Protocol: TCP, Port: 443, Source: 0.0.0.0/0

# Optional: Custom port for SDK
Type: Custom TCP, Protocol: TCP, Port: 8501, Source: 0.0.0.0/0
```

## 🔐 Environment Variables

Create a `.env` file in the `app/` directory with the following variables:

### Discord Configuration
```bash
# Production bot token from Discord Developer Portal
BOT_TOKEN=your_production_discord_bot_token

# Test bot token (can be same as BOT_TOKEN if using one bot)
TEST_BOT_TOKEN=your_test_discord_bot_token
```

### Mode Configuration
```bash
# Environment mode settings
TEST_MODE=false          # true/false - Enables rapid testing mode
STAGE=false             # true/false - Enables staging mode (no notifications)
```

### AWS Configuration
```bash
# AWS credentials for S3 access
AWS_ACCESS_KEY=AKIA...              # IAM user access key
AWS_SECRET=your_secret_access_key   # IAM user secret key
```

### Logging Configuration
```bash
# Discord webhook URLs for logging (optional)
LOG_WEBHOOK_URL=https://discord.com/api/webhooks/...     # Production logs
LOG_WEBHOOK_URL_TEST=https://discord.com/api/webhooks/... # Test logs
```

### GitHub Configuration (Lambda Only)
```bash
# For Lambda function only
GH_API_TOKEN=ghp_your_github_token
ENDPOINT=https://api.github.com/repos/SimplifyJobs/Summer2025-Internships/contents/README.md
```

### Environment Variable Details

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `BOT_TOKEN` | ✅ | Discord bot token for production | `MTIzNDU2Nzg5...` |
| `TEST_BOT_TOKEN` | ⚠️ | Discord bot token for testing (can be same as BOT_TOKEN) | `MTIzNDU2Nzg5...` |
| `TEST_MODE` | ✅ | Enables test mode (5-second intervals) | `true` or `false` |
| `STAGE` | ✅ | Enables stage mode (no notifications) | `true` or `false` |
| `AWS_ACCESS_KEY` | ✅ | AWS IAM user access key for S3 | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET` | ✅ | AWS IAM user secret key for S3 | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `LOG_WEBHOOK_URL` | ❌ | Discord webhook for production logs | `https://discord.com/api/webhooks/...` |
| `LOG_WEBHOOK_URL_TEST` | ❌ | Discord webhook for test logs | `https://discord.com/api/webhooks/...` |
| `GH_API_TOKEN` | ✅* | GitHub personal access token (*Lambda only) | `ghp_xxxxxxxxxxxxxxxxxxxx` |
| `ENDPOINT` | ✅* | Simplify repository API endpoint (*Lambda only) | `https://api.github.com/repos/...` |

## 🚀 Installation & Deployment

### Local Development Setup

1. **Clone Repository**
```bash
git clone https://github.com/your-org/acm-connect.git
cd acm-connect/app
```

2. **Create Environment File**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Run Bot Locally**
```bash
python bot.py
```

### Production Deployment on EC2

1. **Connect to EC2 Instance**
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

2. **Install Docker**
```bash
# Ubuntu
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker ubuntu
sudo systemctl enable docker
sudo systemctl start docker

# Amazon Linux
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -a -G docker ec2-user
```

3. **Clone and Setup Project**
```bash
git clone https://github.com/your-org/acm-connect.git
cd acm-connect/app
cp .env.example .env
# Edit .env with your production configuration
nano .env
```

4. **Deploy with Docker**
```bash
docker-compose up -d --build
```

5. **Verify Deployment**
```bash
docker-compose logs -f
```

### S3 Data Files

The bot automatically manages the following JSON files in your S3 bucket:

**guilds.json** (Production servers) - *Auto-managed by bot setup*:
```json
[
    {
        "id": 1234567890123456789,
        "name": "Your Production Server",
        "channel": 1234567890123456789,
        "role": 1234567890123456789
    }
]
```

**test_guilds.json** (Test servers) - *Auto-managed by bot setup*:
```json
[
    {
        "id": 9876543210987654321,
        "name": "Your Test Server", 
        "channel": 9876543210987654321,
        "role": 9876543210987654321
    }
]
```

**keys.json** (Activation keys) - *Managed via SDK*:
```json
[
    "activation_key_1_here",
    "activation_key_2_here"
]
```

**companies.json** (Company logo cache) - *Auto-populated by bot*:
```json
[]
```

> **Note**: You don't need to manually create these files. The bot's setup process and SDK will handle file creation and management automatically.

## 🎛️ SDK Admin Dashboard

The SDK provides a web-based admin interface for managing Discord servers and debugging the bot.

### Features
- **Server Management**: View and manage production/test Discord servers
- **Key Management**: Generate and manage activation keys
- **Listings Debug**: Analyze internship data and filtering logic
- **Real-time Monitoring**: View current bot status and logs

### Setup SDK

1. **Navigate to SDK Directory**
```bash
cd sdk
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure Environment**
```bash
cp .env.example .env
# Add your AWS credentials
```

4. **Run SDK**
```bash
streamlit run sdk.py --server.port 8501
```

5. **Access Dashboard**
Open `http://your-ec2-ip:8501` in your browser

### SDK Environment Variables
```bash
# Same AWS credentials as main bot
AWS_ACCESS_KEY=your_access_key
AWS_SECRET=your_secret_key
```

## 📁 File Structure

```
acm-connect/
├── app/                          # Main Discord bot application
│   ├── bot.py                   # Bot entry point and setup
│   ├── post_listings.py         # Core posting logic and scheduling
│   ├── logger.py                # Custom logging system
│   ├── util.py                  # Utility functions for S3 and data processing
│   ├── setup.py                 # Bot setup and slash commands
│   ├── requirements.txt         # Python dependencies
│   ├── Dockerfile              # Container configuration
│   ├── docker-compose.yml      # Docker Compose setup
│   ├── .env.example            # Environment variables template
│   ├── .env                    # Your environment configuration (create this)
│   ├── update.sh               # Deployment update script
│   └── acm_logo.png            # ACM logo for embeds
├── data/                        # AWS Lambda function
│   ├── lambda_function.py       # Data fetching from Simplify repository
│   └── .env.example            # Lambda environment template
├── sdk/                         # Admin dashboard
│   ├── sdk.py                  # Streamlit admin interface
│   ├── requirements.txt        # SDK Python dependencies
│   ├── .env.example           # SDK environment template
│   └── .env                   # SDK environment configuration (create this)
├── scripts/                     # Deployment scripts
│   └── update.sh               # Alternative update script
└── README.md                   # This comprehensive guide
```

### Key Files Explained

#### Core Bot Files
- **`bot.py`**: Main entry point, loads extensions and handles Discord connection
- **`post_listings.py`**: Heart of the bot - handles scheduling, data fetching, filtering, and posting
- **`logger.py`**: Custom logging system with Discord webhook integration
- **`util.py`**: S3 utilities, data processing, and Discord helper functions
- **`setup.py`**: Bot setup commands and slash command registration

#### Configuration Files
- **`requirements.txt`**: Python package dependencies
- **`Dockerfile`**: Container build instructions
- **`docker-compose.yml`**: Container orchestration
- **`.env`**: Environment variables (you create this from `.env.example`)

#### AWS Files
- **`data/lambda_function.py`**: Fetches internship data from Simplify's GitHub
- **S3 JSON Files**:
  - `listings.json`: Raw internship data from Simplify
  - `guilds.json`: Production Discord server configurations
  - `test_guilds.json`: Test Discord server configurations
  - `keys.json`: Activation keys for server registration
  - `companies.json`: Cached company logo URLs

#### Admin Tools
- **`sdk/sdk.py`**: Streamlit web dashboard for administration
- **`update.sh`**: Automated deployment update script

## 🔄 Deployment Pipeline

The deployment pipeline uses SSH and Git for automated updates:

### How It Works
1. **GitHub Push**: Code changes are pushed to the main branch
2. **SSH Connection**: Deployment script connects to EC2 instance
3. **Git Pull**: Latest code is pulled from GitHub
4. **Docker Rebuild**: Container is rebuilt with new code
5. **Service Restart**: Bot service is restarted with zero downtime

### Manual Deployment
```bash
# On EC2 instance
cd acm-connect/app
./update.sh
```

### Automated Deployment (GitHub Actions)
Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to EC2

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - name: Deploy to EC2
      uses: appleboy/ssh-action@v0.1.5
      with:
        host: ${{ secrets.EC2_HOST }}
        username: ubuntu
        key: ${{ secrets.EC2_SSH_KEY }}
        script: |
          cd acm-connect/app
          ./update.sh
```

### Update Script Details
The `update.sh` script performs:
1. **Git Operations**: Fetches latest code and resets to origin/main
2. **Docker Operations**: Rebuilds image, stops old containers, starts new ones
3. **Error Handling**: Exits on any failure with detailed logging
4. **Zero Downtime**: Uses Docker Compose for seamless updates

## 🐛 Troubleshooting

### Common Issues

#### Bot Not Posting
1. **Check Environment Mode**:
   ```bash
   # View current configuration
   docker-compose logs | grep "TEST_MODE\|STAGE"
   ```

2. **Verify S3 Data**:
   ```bash
   # Check if listings.json exists and has data
   aws s3 ls s3://your-bucket-name/
   aws s3 cp s3://your-bucket-name/listings.json - | jq length
   ```

3. **Check Discord Permissions**:
   - Bot has "Send Messages" permission
   - Bot has "Create Forum Posts" permission
   - Bot can mention the configured role

#### Lambda Not Fetching Data
1. **Check Lambda Logs**:
   ```bash
   aws logs describe-log-groups --log-group-name-prefix /aws/lambda/acm-internship-fetcher
   ```

2. **Verify GitHub Token**:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" https://api.github.com/user
   ```

3. **Test Lambda Function**:
   - Use AWS Console to test with empty event
   - Check CloudWatch logs for errors

#### Docker Issues
1. **Container Won't Start**:
   ```bash
   docker-compose logs
   docker-compose down && docker-compose up --build
   ```

2. **Permission Errors**:
   ```bash
   sudo chown -R $USER:$USER .
   ```

3. **Port Conflicts**:
   ```bash
   sudo netstat -tulpn | grep :8501
   ```

### Debug Commands

```bash
# View bot logs
docker-compose logs -f discord-bot

# Check container status
docker-compose ps

# Restart specific service
docker-compose restart discord-bot

# View S3 bucket contents
aws s3 ls s3://your-bucket-name/ --recursive

# Test Discord bot token
curl -H "Authorization: Bot YOUR_BOT_TOKEN" https://discord.com/api/users/@me
```

### Log Analysis
The bot provides detailed logging with categories:
- **POST_LISTINGS**: Main posting operations
- **DATA_LOAD**: S3 data fetching
- **DATA_PROCESS**: Filtering and processing
- **ERROR**: Error conditions
- **SUCCESS**: Successful operations
- **WARNING**: Warning conditions

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Test thoroughly in TEST_MODE
5. Submit a pull request

### Code Style
- Follow PEP 8 Python style guidelines
- Use meaningful variable names
- Add docstrings to functions
- Include error handling
- Write tests for new features

### Testing
1. **Test Mode**: Use `TEST_MODE=true` for rapid iteration
2. **Stage Mode**: Use `STAGE=true` for production-like testing
3. **SDK Testing**: Use the admin dashboard to verify data processing

## 👥 Acknowledgements

ACM Connect was proudly developed by:
- **Alex Fisher** - Lead Developer
- **Jason Tenczar** - Backend Architecture  
- **Steve Sajeev** - Discord Integration
- **Jacob Frankel** - AWS Infrastructure
- **Alex Milanes** - Frontend & UI

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For questions, issues, or contributions:
1. **GitHub Issues**: Open an issue on this repository
2. **Discord**: Join our development Discord server
3. **Email**: Contact the development team

---

**Happy job hunting! 🚀**

*Last updated: January 2025*