# Display a list of available commands
default:
    just --list

# Clean up all temporary and cache files. Removes Python bytecode files, cache directories, build artifacts, coverage reports, editor temporary files, and virtual environments.
clean:
    @echo "🧹 Cleaning temporary files and caches..."
    # Python cache files
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    find . -type f -name "*.pyo" -delete
    find . -type f -name "*.pyd" -delete
    find . -type f -name ".coverage" -delete
    find . -type f -name ".coverage.*" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    find . -type d -name "*.egg" -exec rm -rf {} +
    find . -type d -name ".pytest_cache" -exec rm -rf {} +
    find . -type d -name ".mypy_cache" -exec rm -rf {} +
    find . -type d -name ".ruff_cache" -exec rm -rf {} +

    # Build directories
    rm -rf build/
    rm -rf dist/
    rm -rf .eggs/

    # Coverage reports
    rm -rf htmlcov/
    rm -rf .coverage
    rm -rf coverage.xml

    # Temp files
    find . -type f -name "*.swp" -delete
    find . -type f -name "*.swo" -delete
    find . -type f -name "*~" -delete
    find . -name ".DS_Store" -delete

    # Virtual environments
    rm -rf .venv/
    rm -rf venv/

    @echo "✨ Cleanup complete!"

# Format code using isort and Ruff formatter
format:
    isort *.py
    ruff format

# Lint and auto-fix code issues
lint: format
    ruff check *.py --fix

# Install dependencies using uv package manager
install:
    uv sync

# Run the application with environment variables. Formats code first, then runs main.py with environment variables loaded from .env file
run: format
    dotenv run -- uv run python main.py
