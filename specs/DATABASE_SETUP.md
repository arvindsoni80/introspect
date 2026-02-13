# Database Setup Guide

## Recommended: Home Directory Storage

For better security and to keep data separate from your code repository, we recommend storing the database in your home directory.

### Quick Setup

Run the automated setup script:

```bash
./setup_home_directory.sh
```

This script will:
1. Create `~/introspect/data/` directory
2. Copy existing database from `./data/calls.db` to `~/introspect/data/calls.db`
3. Update your `.env` file to use the new location
4. Backup your original `.env` file

### Manual Setup

If you prefer to set it up manually:

```bash
# 1. Create directory
mkdir -p ~/introspect/data

# 2. Move database
cp ./data/calls.db ~/introspect/data/calls.db

# 3. Update .env
echo "SQLITE_DB_PATH=~/introspect/data/calls.db" >> .env
```

### Why Home Directory?

**Benefits:**
- ✅ **Keeps data separate from code** - No risk of accidentally committing sensitive call data
- ✅ **Survives repo operations** - Data persists even if you delete/reclone the repo
- ✅ **Clear separation** - Code in repo, data in home directory
- ✅ **Predictable location** - Same path across different project clones

**Security:**
- Database contains call transcripts, MEDDPICC scores, and sales data
- Should NOT be committed to version control
- `.gitignore` already protects `data/` directory, but home directory is safer

## Path Expansion Support

The configuration supports multiple path formats:

```bash
# Home directory (Recommended)
SQLITE_DB_PATH=~/introspect/data/calls.db

# Environment variable
SQLITE_DB_PATH=$HOME/introspect/data/calls.db

# Absolute path
SQLITE_DB_PATH=/Users/yourname/introspect/data/calls.db

# Relative path (from project root)
SQLITE_DB_PATH=./data/calls.db
```

All of these will be properly expanded by the configuration system.

## Verifying Setup

After setup, test the database connection:

```bash
cd streamlit_app
python test_db_access.py
```

Expected output:
```
✓ Settings loaded
  DB Path (from settings): ~/introspect/data/calls.db
  Resolved DB Path: /Users/yourname/introspect/data/calls.db
✓ Database file exists
✓ Connected to database
✓ Queried accounts
  Total accounts: 223
```

## Backup Strategy

Since the database is now in your home directory, set up regular backups:

```bash
# Daily backup script
cp ~/introspect/data/calls.db ~/introspect/data/backups/calls_$(date +%Y%m%d).db

# Or use the built-in backup
sqlite3 ~/introspect/data/calls.db .dump > ~/introspect/data/backups/backup_$(date +%Y%m%d).sql
```

## Multiple Environments

You can maintain separate databases for different purposes:

```bash
# Production data
SQLITE_DB_PATH=~/introspect/data/calls.db

# Testing data
SQLITE_DB_PATH=~/introspect/data/calls_test.db

# Development data
SQLITE_DB_PATH=~/introspect/data/calls_dev.db
```

Just update your `.env` file to point to the appropriate database.

## Troubleshooting

**"Database not found"**
- Check that `~/introspect/data/calls.db` exists
- Verify `.env` has correct `SQLITE_DB_PATH` value
- Try absolute path: `/Users/yourname/introspect/data/calls.db`

**"No accounts found" but database exists**
- Run the analyzer first: `python main.py --sales-reps your@email.com`
- Check if you're looking at the right database
- Verify with: `sqlite3 ~/introspect/data/calls.db "SELECT COUNT(*) FROM accounts"`

**Permission denied**
- Ensure you own the directory: `ls -la ~/introspect/data/`
- Fix permissions: `chmod 755 ~/introspect/data && chmod 644 ~/introspect/data/calls.db`

## Migration Guide

If you've been using `./data/calls.db` and want to switch:

1. **Backup current database:**
   ```bash
   cp ./data/calls.db ./data/calls.db.backup
   ```

2. **Run setup script:**
   ```bash
   ./setup_home_directory.sh
   ```

3. **Test new location:**
   ```bash
   cd streamlit_app && python test_db_access.py
   ```

4. **Verify data:**
   - Check that account count matches
   - Verify recent calls are present
   - Test UI: `streamlit run app.py`

5. **Remove old database (optional):**
   ```bash
   rm ./data/calls.db
   ```

## Best Practices

1. **Never commit database files** - The `.gitignore` protects `data/` but home directory is safer
2. **Regular backups** - Set up automated backups of `~/introspect/data/`
3. **Document location** - Team members should know where data lives
4. **Use environment variables** - For production deployments, use `$DB_PATH` env var
5. **Secure permissions** - Keep database files readable only by your user
