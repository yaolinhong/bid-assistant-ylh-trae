# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Bid Assistant (招标助手) - an intelligent AI-powered bidding assistant built with Python and the Parlant framework. It helps users discover bidding opportunities, analyze projects, and prepare bid documents using AI models like Kimi and Google Gemini.

## Key Commands

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Run with Docker (development mode)
./start.sh dev

# Run with Docker (production mode)
./start.sh prod
```

### Docker Management
```bash
# View logs
./start.sh logs

# Stop services
./start.sh stop

# Restart services
./start.sh restart dev  # or 'prod'

# Clean containers and images
./start.sh clean
```

### Testing and Quality
```bash
# Run tests (when implemented)
pytest

# Type checking
mypy .

# Linting
flake8 .
black .
```

## Architecture Overview

### Core Components

1. **Parlant Agent Framework** (`main.py`)
   - Main entry point using Parlant SDK
   - Defines AI agent with journeys, guidelines, and tools
   - Integrates with NLP services (Gemini/Kimi)

2. **NLP Services**
   - `gemini_nlp_service.py` - Google Gemini integration
   - `kimi_nlp_service.py` - Kimi AI integration (fallback)
   - Provides schematic generation, embedding, and moderation

3. **Web Search** (`web_search.py`)
   - Multi-source tender information search
   - Scrapes government and commercial bidding sites
   - Includes CCGP, GGZY, ChinaBidding, etc.

4. **Data Storage** (`data_store.py`)
   - Simple JSON file-based storage
   - Manages sessions, cached projects, and analysis results

5. **Monitoring Dashboard**
   - Flask web app for search statistics
   - Real-time search logs and source status
   - Accessible at `/dashboard` endpoint

### Data Flow

```
User Input → Parlant Agent → Tools (Search/Analysis) → AI Services → Data Store → Response
```

### AI Model Integration

The project supports multiple AI models:
- **Primary**: Google Gemini (via `gemini_nlp_service.py`)
- **Fallback**: Kimi AI (via `kimi_nlp_service.py`)

## Environment Configuration

### Required Environment Variables
```bash
GEMINI_API_KEY=your_gemini_api_key      # Primary AI service
KIMI_API_KEY=your_kimi_api_key          # Fallback AI service
OPENAI_API_KEY=your_openai_api_key      # For embeddings/moderation
```

### Optional Environment Variables
```bash
DATA_STORE_PATH=./data                  # Data storage directory
SEARCH_TIMEOUT=30                       # Search timeout in seconds
```

## Project Structure

```
bid-assistant-ylh-trae/
├── main.py                    # Main application entry point
├── gemini_nlp_service.py      # Google Gemini NLP service
├── kimi_nlp_service.py        # Kimi AI NLP service (fallback)
├── web_search.py              # Multi-source web search
├── data_store.py              # JSON file data storage
├── requirements.txt           # Python dependencies
├── start.sh                  # Docker management script
├── docker-compose.yml        # Production Docker config
├── docker-compose.dev.yml    # Development Docker config
├── .env.example             # Environment variables template
├── data/                    # Runtime data directory
│   ├── sessions/           # User session data
│   ├── projects/           # Cached project data
│   └── analysis/           # Analysis results
└── test_data/               # Test data and fixtures
```

## Key Features

### 1. Intelligent Search
- Multi-source tender information aggregation
- Government and commercial bidding sites
- Real-time search with caching
- Source status monitoring

### 2. AI-Powered Analysis
- Risk assessment (technical, commercial, time, compliance)
- Competition analysis and market assessment
- Qualification matching and requirements checking
- Comprehensive project evaluation

### 3. Document Processing
- Automatic tender document summarization
- Key information extraction
- Bid outline generation
- Compliance checking

### 4. User Journey Management
- Opportunity discovery
- Information analysis
- Bid preparation
- Submission support

## Development Guidelines

### Adding New Search Sources
1. Extend `tender_sites` dictionary in `web_search.py`
2. Implement source-specific search and parsing methods
3. Add source status monitoring to the dashboard

### Adding New Analysis Types
1. Extend prompts in `analyze_project_with_kimi()` function
2. Add new analysis templates to NLP service
3. Update schema definitions for structured output

### Working with Parlant Framework
- Use `@p.tool` decorator for tool functions
- Define guidelines for agent behavior
- Set up journeys for user flow management
- Integrate with the NLP service for AI capabilities

### Data Storage Patterns
- Use `SimpleDataStore` for persistent data
- Session data stored in `data/sessions/`
- Project caches stored in `data/projects/`
- Analysis results stored in `data/analysis/`

## API Integration Notes

### Google Gemini API
- Base URL: `https://generativelanguage.googleapis.com/v1beta/openai/`
- OpenAI-compatible interface
- Models: `gemini-2.5-flash`, `gemini-2.5-flash-002`

### Kimi API
- Base URL: `https://api.moonshot.cn/v1`
- Models: `moonshot-v1-8k`, `moonshot-v1-32k`, `moonshot-v1-128k`
- Used as fallback when Gemini is unavailable

### Web Search Sources
- **CCGP**: China Government Procurement (政府招标)
- **GGZY**: National Public Resources Platform (公共资源)
- **ChinaBidding**: Commercial bidding platform
- **Bidding.com**: General bidding information

## Testing and Debugging

### Debug Mode
- Application runs with debug logging by default
- Dashboard at `/dashboard` shows real-time search status
- Search logs include source-specific success/failure status

### Common Issues
1. **API Key Issues**: Verify `GEMINI_API_KEY` and `KIMI_API_KEY` in `.env`
2. **Search Failures**: Check internet connectivity and source availability
3. **Docker Issues**: Use `./start.sh clean` to reset containers
4. **Port Conflicts**: Ensure port 8800 is available

### Performance Optimization
- Search results are cached to avoid repeated API calls
- Async operations for concurrent search requests
- Rate limiting and timeout handling for external APIs

## Deployment

### Docker Deployment
- Development mode supports hot-reload
- Production mode uses optimized builds
- Volume mounting for data persistence
- Redis caching available for improved performance

### Environment-Specific Configs
- Use `docker-compose.dev.yml` for development
- Use `docker-compose.yml` for production
- Environment variables managed through `.env` file

## Important Notes

- **Service Restart**: Always use `./start.sh restart` to restart services after making changes to documentation or code