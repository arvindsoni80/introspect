-- Introspect Database Schema v2.4
-- Stage-based sales call analysis system
-- Updated: Added primary_sales_rep to accounts (from most recent call)
--          Removed account aggregate tables (keep scores at call level only)
--          Removed stage_updated_at from accounts (redundant with last_call_date)
--          Removed days_in_current_stage from accounts (derived value: today - last_call_date)
--          call_id as primary key, no foreign key constraints

-- ============================================================================
-- Core Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE NOT NULL,

    -- Current state (denormalized for query performance)
    current_stage TEXT,
    deal_status TEXT,

    -- Primary ownership (from most recent call)
    primary_sales_rep TEXT,
    primary_segment TEXT,

    -- Timestamps
    first_call_date DATETIME,
    last_call_date DATETIME,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),

    -- Metadata
    total_calls INTEGER DEFAULT 0,

    CHECK (current_stage IN ('discovery', 'trial', 'negotiation', 'closed', NULL)),
    CHECK (deal_status IN ('active', 'stalled', 'closed_won', 'closed_lost', NULL))
);

CREATE INDEX IF NOT EXISTS idx_accounts_domain ON accounts(domain);
CREATE INDEX IF NOT EXISTS idx_accounts_current_stage ON accounts(current_stage);
CREATE INDEX IF NOT EXISTS idx_accounts_deal_status ON accounts(deal_status);
CREATE INDEX IF NOT EXISTS idx_accounts_primary_rep ON accounts(primary_sales_rep);
CREATE INDEX IF NOT EXISTS idx_accounts_segment ON accounts(primary_segment);
CREATE INDEX IF NOT EXISTS idx_accounts_last_call ON accounts(last_call_date);

-- ============================================================================

CREATE TABLE IF NOT EXISTS calls (
    call_id TEXT PRIMARY KEY,  -- Gong call ID is the natural key

    -- Foreign keys
    account_id INTEGER NOT NULL,
    sales_rep_email TEXT NOT NULL,

    -- Call metadata
    call_date DATETIME NOT NULL,
    call_title TEXT,

    -- Stage classification
    primary_stage TEXT NOT NULL,
    secondary_stage TEXT,
    stage_confidence REAL,

    -- Segment at time of call (for historical accuracy)
    segment_at_call_time TEXT,

    -- Timestamps
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),

    CHECK (primary_stage IN ('discovery', 'trial', 'negotiation', 'closed')),
    CHECK (secondary_stage IN ('discovery', 'trial', 'negotiation', 'closed', NULL)),
    CHECK (stage_confidence >= 0.0 AND stage_confidence <= 1.0)
);

CREATE INDEX IF NOT EXISTS idx_calls_account ON calls(account_id);
CREATE INDEX IF NOT EXISTS idx_calls_rep ON calls(sales_rep_email);
CREATE INDEX IF NOT EXISTS idx_calls_stage ON calls(primary_stage);
CREATE INDEX IF NOT EXISTS idx_calls_date ON calls(call_date);
CREATE INDEX IF NOT EXISTS idx_calls_account_date ON calls(account_id, call_date);
CREATE INDEX IF NOT EXISTS idx_calls_rep_date ON calls(sales_rep_email, call_date);

-- ============================================================================

CREATE TABLE IF NOT EXISTS call_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL,  -- Reference to calls table

    -- Gong IDs
    speaker_id TEXT NOT NULL,  -- Used in transcripts
    party_id TEXT,             -- Gong party ID
    user_id TEXT,              -- Gong user ID (for internal users)

    -- Participant info
    email_address TEXT,
    name TEXT,
    title TEXT,
    affiliation TEXT,  -- Internal, External, Unknown
    phone_number TEXT,

    created_at DATETIME NOT NULL DEFAULT (datetime('now')),

    -- Ensure unique speaker per call
    UNIQUE(call_id, speaker_id),

    CHECK (affiliation IN ('Internal', 'External', 'Unknown', NULL))
);

CREATE INDEX IF NOT EXISTS idx_participants_call ON call_participants(call_id);
CREATE INDEX IF NOT EXISTS idx_participants_speaker ON call_participants(speaker_id);
CREATE INDEX IF NOT EXISTS idx_participants_affiliation ON call_participants(affiliation);
CREATE INDEX IF NOT EXISTS idx_participants_email ON call_participants(email_address);

-- ============================================================================

CREATE TABLE IF NOT EXISTS sales_reps (
    email TEXT PRIMARY KEY,
    segment TEXT NOT NULL,
    joining_date DATE NOT NULL,

    -- Track if rep is still active
    is_active BOOLEAN DEFAULT TRUE,
    left_date DATE,

    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sales_reps_segment ON sales_reps(segment);
CREATE INDEX IF NOT EXISTS idx_sales_reps_active ON sales_reps(is_active);

-- ============================================================================
-- Evaluation Score Tables
-- Note: Using call_id as primary key (one evaluation per call per stage)
-- ============================================================================

CREATE TABLE IF NOT EXISTS call_meddpicc_scores (
    call_id TEXT PRIMARY KEY,  -- Direct reference to calls

    -- MEDDPICC dimensions (0/2/5 scale, higher = better)
    metrics INTEGER NOT NULL,
    economic_buyer INTEGER NOT NULL,
    decision_criteria INTEGER NOT NULL,
    decision_process INTEGER NOT NULL,
    paper_process INTEGER NOT NULL,
    identify_pain INTEGER NOT NULL,
    champion INTEGER NOT NULL,
    competition INTEGER NOT NULL,

    -- Aggregated
    overall_score REAL NOT NULL,

    -- Analysis text
    meddpicc_summary TEXT,
    key_gaps TEXT,
    clarity_of_need TEXT,
    key_influencers TEXT,
    next_steps TEXT,
    trial_readiness TEXT,

    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),

    CHECK (metrics IN (0, 2, 5)),
    CHECK (economic_buyer IN (0, 2, 5)),
    CHECK (decision_criteria IN (0, 2, 5)),
    CHECK (decision_process IN (0, 2, 5)),
    CHECK (paper_process IN (0, 2, 5)),
    CHECK (identify_pain IN (0, 2, 5)),
    CHECK (champion IN (0, 2, 5)),
    CHECK (competition IN (0, 2, 5)),
    CHECK (overall_score >= 0.0 AND overall_score <= 5.0)
);

-- ============================================================================

CREATE TABLE IF NOT EXISTS call_trial_scores (
    call_id TEXT PRIMARY KEY,

    -- TRIAL health dimensions (0/2/5 scale, higher = healthier)
    technical_validation INTEGER NOT NULL,
    readiness_progress INTEGER NOT NULL,
    internal_adoption INTEGER NOT NULL,
    advocacy_sentiment INTEGER NOT NULL,
    landscape_competition INTEGER NOT NULL,

    -- Aggregated
    overall_score REAL NOT NULL,

    -- Analysis
    health_interpretation TEXT,
    primary_concern_category TEXT,
    concern_severity TEXT,
    likelihood_to_advance TEXT,
    is_bake_off BOOLEAN DEFAULT FALSE,
    key_concerns TEXT,
    recommended_actions TEXT,
    next_steps TEXT,

    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),

    CHECK (technical_validation IN (0, 2, 5)),
    CHECK (readiness_progress IN (0, 2, 5)),
    CHECK (internal_adoption IN (0, 2, 5)),
    CHECK (advocacy_sentiment IN (0, 2, 5)),
    CHECK (landscape_competition IN (0, 2, 5)),
    CHECK (overall_score >= 0.0 AND overall_score <= 5.0),
    CHECK (health_interpretation IN ('healthy', 'at_risk', 'critical', NULL)),
    CHECK (concern_severity IN ('critical', 'high', 'medium', 'low', 'none', NULL)),
    CHECK (likelihood_to_advance IN ('high', 'medium', 'low', NULL))
);

CREATE INDEX IF NOT EXISTS idx_trial_health ON call_trial_scores(health_interpretation);

-- ============================================================================

CREATE TABLE IF NOT EXISTS call_close_scores (
    call_id TEXT PRIMARY KEY,

    -- CLOSE health dimensions (0/2/5 scale, higher = healthier)
    commercial_alignment INTEGER NOT NULL,
    legal_compliance INTEGER NOT NULL,
    organizational_consensus INTEGER NOT NULL,
    single_threading_risk INTEGER NOT NULL,
    execution_momentum INTEGER NOT NULL,

    -- Aggregated
    overall_score REAL NOT NULL,

    -- Analysis
    health_interpretation TEXT,
    primary_concern_category TEXT,
    concern_severity TEXT,
    likelihood_to_close TEXT,
    has_competitive_pressure BOOLEAN DEFAULT FALSE,
    key_concerns TEXT,
    recommended_actions TEXT,
    next_steps TEXT,

    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),

    CHECK (commercial_alignment IN (0, 2, 5)),
    CHECK (legal_compliance IN (0, 2, 5)),
    CHECK (organizational_consensus IN (0, 2, 5)),
    CHECK (single_threading_risk IN (0, 2, 5)),
    CHECK (execution_momentum IN (0, 2, 5)),
    CHECK (overall_score >= 0.0 AND overall_score <= 5.0),
    CHECK (health_interpretation IN ('healthy', 'at_risk', 'critical', NULL)),
    CHECK (concern_severity IN ('critical', 'high', 'medium', 'low', 'none', NULL)),
    CHECK (likelihood_to_close IN ('high', 'medium', 'low', NULL))
);

CREATE INDEX IF NOT EXISTS idx_close_health ON call_close_scores(health_interpretation);

-- ============================================================================

CREATE TABLE IF NOT EXISTS call_win_loss_analysis (
    call_id TEXT PRIMARY KEY,

    -- Outcome
    outcome TEXT NOT NULL,

    -- Analysis
    primary_reasons TEXT NOT NULL,
    stage_of_decision TEXT,
    critical_dimensions TEXT,
    competitive_factor TEXT,
    key_learnings TEXT,

    -- Supporting quotes
    verbatim_quotes TEXT,

    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),

    CHECK (outcome IN ('won', 'lost')),
    CHECK (stage_of_decision IN ('discovery', 'trial', 'negotiation', NULL))
);

CREATE INDEX IF NOT EXISTS idx_winloss_outcome ON call_win_loss_analysis(outcome);

-- ============================================================================
-- Tracking Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS stage_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,

    -- Transition details
    from_stage TEXT NOT NULL,
    to_stage TEXT NOT NULL,
    transitioned_at DATETIME NOT NULL,

    -- Metrics
    duration_in_previous_stage_days INTEGER,

    -- What triggered this transition
    triggered_by_call_id TEXT,

    created_at DATETIME NOT NULL DEFAULT (datetime('now')),

    CHECK (from_stage IN ('new', 'discovery', 'trial', 'negotiation', 'closed')),
    CHECK (to_stage IN ('discovery', 'trial', 'negotiation', 'closed'))
);

CREATE INDEX IF NOT EXISTS idx_transitions_account ON stage_transitions(account_id);
CREATE INDEX IF NOT EXISTS idx_transitions_date ON stage_transitions(transitioned_at);
CREATE INDEX IF NOT EXISTS idx_transitions_from ON stage_transitions(from_stage);
CREATE INDEX IF NOT EXISTS idx_transitions_to ON stage_transitions(to_stage);

-- ============================================================================

CREATE TABLE IF NOT EXISTS account_rep_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    sales_rep_email TEXT NOT NULL,

    -- Time period
    first_call_date DATETIME NOT NULL,
    last_call_date DATETIME,

    -- Stats
    total_calls INTEGER DEFAULT 1,

    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),

    UNIQUE(account_id, sales_rep_email)
);

CREATE INDEX IF NOT EXISTS idx_rep_history_account ON account_rep_history(account_id);
CREATE INDEX IF NOT EXISTS idx_rep_history_rep ON account_rep_history(sales_rep_email);
