#!/bin/bash
# Activate the virtual environment and run the application
# Passes all arguments to main.py

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if venv exists
if [ -d "$DIR/venv" ]; then
    PYTHON_EXEC="$DIR/venv/bin/python"
elif [ -d "$DIR/.venv" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python"
else
    echo "Error: Virtual environment not found. Please run 'python3 -m venv venv && venv/bin/pip install -r requirements.txt' first."
    exit 1
fi

"$PYTHON_EXEC" "$DIR/main.py" "$@"
