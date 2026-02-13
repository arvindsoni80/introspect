#!/bin/bash
# Setup script to move database to home directory

set -e

echo "=========================================="
echo "Introspect - Database Setup"
echo "=========================================="
echo ""

# Define paths
HOME_DIR="$HOME/introspect"
DATA_DIR="$HOME_DIR/data"
OLD_DB="./data/calls.db"
NEW_DB="$DATA_DIR/calls.db"

# Check if old database exists
if [ ! -f "$OLD_DB" ]; then
    echo "⚠️  No database found at $OLD_DB"
    echo "Creating new directory structure..."
else
    echo "✓ Found existing database at $OLD_DB"
    DB_SIZE=$(ls -lh "$OLD_DB" | awk '{print $5}')
    echo "  Size: $DB_SIZE"
fi

# Create home directory structure
echo ""
echo "Creating directory structure at $HOME_DIR..."
mkdir -p "$DATA_DIR"
echo "✓ Created $DATA_DIR"

# Move database if it exists
if [ -f "$OLD_DB" ]; then
    echo ""
    echo "Moving database to home directory..."
    cp "$OLD_DB" "$NEW_DB"
    echo "✓ Copied to $NEW_DB"

    # Verify the copy
    if [ -f "$NEW_DB" ]; then
        NEW_SIZE=$(ls -lh "$NEW_DB" | awk '{print $5}')
        echo "✓ Verified new database (Size: $NEW_SIZE)"
    else
        echo "✗ Failed to copy database"
        exit 1
    fi
fi

# Update .env file
echo ""
echo "Updating .env file..."
if [ -f ".env" ]; then
    # Backup original
    cp .env .env.backup
    echo "✓ Backed up .env to .env.backup"

    # Update SQLITE_DB_PATH
    if grep -q "^SQLITE_DB_PATH=" .env; then
        # Replace existing line
        sed -i.tmp 's|^SQLITE_DB_PATH=.*|SQLITE_DB_PATH=~/introspect/data/calls.db|' .env
        rm -f .env.tmp
        echo "✓ Updated SQLITE_DB_PATH in .env"
    else
        # Add new line
        echo "" >> .env
        echo "SQLITE_DB_PATH=~/introspect/data/calls.db" >> .env
        echo "✓ Added SQLITE_DB_PATH to .env"
    fi
else
    echo "⚠️  No .env file found. Please create one from .env.example"
    echo "   and set: SQLITE_DB_PATH=~/introspect/data/calls.db"
fi

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Database location: $NEW_DB"
echo ""
echo "Next steps:"
echo "1. Verify .env has: SQLITE_DB_PATH=~/introspect/data/calls.db"
echo "2. Test the connection:"
echo "   cd streamlit_app && python test_db_access.py"
echo "3. Run the UI:"
echo "   streamlit run app.py"
echo ""

# Optional: Remove old database
if [ -f "$OLD_DB" ]; then
    echo "Optional: Remove old database?"
    echo "  rm $OLD_DB"
    echo ""
fi
