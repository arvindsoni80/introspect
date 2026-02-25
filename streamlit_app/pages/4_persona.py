"""Persona Analysis Page - Understand customer questions by persona type."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core import Config
from src.data import Database, Repository
from src.services import PersonaClassifier
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode


# Page config
st.set_page_config(page_title="Persona Analysis", page_icon="🎭", layout="wide")

# Load Font Awesome
st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
""", unsafe_allow_html=True)


def load_participants_with_questions(repo: Repository, days: int = 30, segment: str = None, stage: str = None):
    """
    Load all external participants who asked questions in the time range.

    Returns:
        List of dicts with participant info, questions, call details
    """
    # Build query with filters
    query = """
        SELECT
            cp.id,
            cp.name,
            cp.title,
            cp.persona,
            cp.speaker_questions,
            cp.question_count,
            c.call_id,
            c.call_title,
            c.call_date,
            c.primary_stage,
            a.domain,
            a.primary_segment
        FROM call_participants cp
        JOIN calls c ON cp.call_id = c.call_id
        JOIN accounts a ON c.account_id = a.id
        WHERE cp.affiliation = 'External'
          AND cp.speaker_questions IS NOT NULL
          AND cp.question_count > 0
          AND c.call_date >= ?
    """

    params = [(datetime.now() - timedelta(days=days)).isoformat()]

    if segment:
        query += " AND a.primary_segment = ?"
        params.append(segment)

    if stage:
        query += " AND c.primary_stage = ?"
        params.append(stage)

    query += " ORDER BY c.call_date DESC"

    cursor = repo.conn.execute(query, params)
    rows = cursor.fetchall()

    participants = []
    for row in rows:
        # Parse questions JSON
        try:
            questions = json.loads(row['speaker_questions']) if row['speaker_questions'] else []
        except json.JSONDecodeError:
            questions = []

        participants.append({
            'id': row['id'],
            'name': row['name'],
            'title': row['title'],
            'persona': row['persona'],
            'questions': questions,
            'question_count': row['question_count'],
            'call_id': row['call_id'],
            'call_title': row['call_title'],
            'call_date': datetime.fromisoformat(row['call_date']),
            'stage': row['primary_stage'],
            'account': row['domain'],
            'segment': row['primary_segment'],
        })

    return participants


def normalize_question(q: str) -> str:
    """Normalize question for grouping (case-insensitive, strip whitespace and punctuation)."""
    return q.lower().strip().rstrip('?').strip()


def group_questions_by_text(participants, persona_filter=None):
    """
    Group questions by normalized text and track metadata.

    Returns:
        List of dicts with question text, count, and sample calls
    """
    questions_map = defaultdict(lambda: {
        'original': None,
        'count': 0,
        'calls': []
    })

    for p in participants:
        # Filter by persona if specified
        if persona_filter and p['persona'] != persona_filter:
            continue

        for question in p['questions']:
            normalized = normalize_question(question)

            # Store original (first occurrence)
            if questions_map[normalized]['original'] is None:
                questions_map[normalized]['original'] = question

            # Increment count
            questions_map[normalized]['count'] += 1

            # Add call info (avoid duplicates)
            call_info = {
                'call_id': p['call_id'],
                'call_title': p['call_title'],
                'call_date': p['call_date'],
                'account': p['account'],
                'asker_name': p['name'],
                'asker_title': p['title'],
            }

            # Check if this call is already recorded for this question
            existing = [c for c in questions_map[normalized]['calls']
                       if c['call_id'] == p['call_id'] and c['asker_name'] == p['name']]

            if not existing:
                questions_map[normalized]['calls'].append(call_info)

    # Convert to list and sort by frequency
    questions_list = []
    for normalized, data in questions_map.items():
        questions_list.append({
            'question': data['original'],
            'count': data['count'],
            'calls': sorted(data['calls'], key=lambda x: x['call_date'], reverse=True),
        })

    # Sort by frequency (descending)
    questions_list.sort(key=lambda x: x['count'], reverse=True)

    return questions_list


def format_gong_url(call_id: str) -> str:
    """Format Gong call URL from call_id."""
    # TODO: Make this configurable if different Gong instances are used
    return f"https://us-35231.app.gong.io/call?id={call_id}"


def load_themes_for_persona(repo: Repository, persona: str):
    """
    Load themes and their questions for a specific persona.

    Returns:
        List of theme dicts with questions
    """
    # Get themes
    cursor = repo.conn.execute("""
        SELECT
            id,
            theme_name,
            theme_description,
            suggested_collateral,
            question_count,
            last_generated
        FROM question_themes
        WHERE persona = ?
        ORDER BY question_count DESC
    """, (persona,))

    themes = []
    for row in cursor.fetchall():
        theme_id = row['id']

        # Get questions for this theme
        q_cursor = repo.conn.execute("""
            SELECT
                question_original,
                frequency,
                sample_call_ids
            FROM question_theme_assignments
            WHERE theme_id = ?
            ORDER BY frequency DESC
        """, (theme_id,))

        questions = []
        for q_row in q_cursor.fetchall():
            try:
                call_ids = json.loads(q_row['sample_call_ids']) if q_row['sample_call_ids'] else []
            except json.JSONDecodeError:
                call_ids = []

            questions.append({
                'question': q_row['question_original'],
                'frequency': q_row['frequency'],
                'call_ids': call_ids
            })

        try:
            suggested_collateral = json.loads(row['suggested_collateral']) if row['suggested_collateral'] else []
        except json.JSONDecodeError:
            suggested_collateral = []

        themes.append({
            'theme_id': theme_id,
            'theme_name': row['theme_name'],
            'theme_description': row['theme_description'],
            'suggested_collateral': suggested_collateral,
            'question_count': row['question_count'],
            'last_generated': row['last_generated'],
            'questions': questions
        })

    return themes


def get_persona_stats(participants):
    """Get summary statistics by persona."""
    stats = {
        'Decision Maker': {'participants': set(), 'questions': 0, 'accounts': set()},
        'Influencer': {'participants': set(), 'questions': 0, 'accounts': set()},
        'User': {'participants': set(), 'questions': 0, 'accounts': set()},
    }

    for p in participants:
        persona = p['persona']
        if persona in stats:
            stats[persona]['participants'].add(p['name'])
            stats[persona]['questions'] += p['question_count']
            stats[persona]['accounts'].add(p['account'])

    # Convert sets to counts
    for persona in stats:
        stats[persona]['participants'] = len(stats[persona]['participants'])
        stats[persona]['accounts'] = len(stats[persona]['accounts'])

    return stats


def get_title_distribution(repo: Repository, days: int = 30, segment: str = None, stage: str = None):
    """
    Get distribution of titles by persona.

    Returns:
        List of dicts with persona, title, count
    """
    query = """
        SELECT
            cp.persona,
            cp.title,
            COUNT(DISTINCT cp.id) as participant_count,
            COUNT(DISTINCT cp.call_id) as call_count
        FROM call_participants cp
        JOIN calls c ON cp.call_id = c.call_id
        JOIN accounts a ON c.account_id = a.id
        WHERE cp.affiliation = 'External'
          AND cp.persona IS NOT NULL
          AND cp.title IS NOT NULL
          AND cp.title != ''
          AND c.call_date >= ?
    """

    params = [(datetime.now() - timedelta(days=days)).isoformat()]

    if segment:
        query += " AND a.primary_segment = ?"
        params.append(segment)

    if stage:
        query += " AND c.primary_stage = ?"
        params.append(stage)

    query += """
        GROUP BY cp.persona, cp.title
        ORDER BY cp.persona, participant_count DESC
    """

    cursor = repo.conn.execute(query, params)
    rows = cursor.fetchall()

    return [
        {
            'Persona': row['persona'],
            'Title': row['title'],
            'Participants': row['participant_count'],
            'Calls': row['call_count']
        }
        for row in rows
    ]


def render_persona_card(persona, stats, icon, color):
    """Render a summary card for a persona."""
    st.markdown(f"""
        <div style="text-align: center; padding: 15px; border: 1px solid #ddd; border-radius: 8px; background-color: #f9f9f9;">
            <p style="color: {color}; font-size: 2rem; margin: 0;">
                <i class="{icon}"></i>
            </p>
            <p style="font-weight: bold; font-size: 1.1rem; margin: 8px 0 4px 0;">
                {persona}
            </p>
            <p style="font-size: 0.9rem; color: #666; margin: 4px 0;">
                {stats['participants']} participants
            </p>
            <p style="font-size: 0.9rem; color: #666; margin: 4px 0;">
                {stats['questions']} questions
            </p>
            <p style="font-size: 0.9rem; color: #666; margin: 4px 0;">
                {stats['accounts']} accounts
            </p>
        </div>
    """, unsafe_allow_html=True)


def render_themes_view(themes, persona_name, repo):
    """Render the themes view for a persona."""
    if not themes:
        st.info(f"No themes generated for {persona_name}s yet.")
        st.markdown("Click **'Regenerate Themes'** button in the sidebar to generate themes.")
        return

    st.markdown(f"**{len(themes)} themes identified** (sorted by question count)")
    st.markdown("---")

    for i, theme in enumerate(themes, 1):
        theme_name = theme['theme_name']
        theme_desc = theme['theme_description']
        q_count = theme['question_count']
        questions = theme['questions']
        collateral = theme['suggested_collateral']

        # Theme header with border
        with st.container(border=True):
            # Theme title and count
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                st.markdown(f"### {i}. {theme_name}")
            with col2:
                st.markdown(f"<p style='text-align: right; color: #3498db; font-weight: bold; margin-top: 10px;'>{q_count} questions</p>",
                           unsafe_allow_html=True)

            # Theme description
            if theme_desc:
                st.markdown(f"*{theme_desc}*")

            # Suggested collateral
            if collateral:
                st.markdown("**💡 Suggested Collateral:**")
                for item in collateral:
                    st.markdown(f"  - {item}")

            st.markdown("")  # Spacing

            # Top questions in this theme
            st.markdown(f"**Top Questions** ({min(5, len(questions))} of {len(questions)}):")

            for j, q in enumerate(questions[:5], 1):
                question = q['question']
                freq = q['frequency']
                call_ids = q.get('call_ids', [])

                st.markdown(f"{j}. **{question}** (asked {freq}x)")

                # Show first sample call as a quick link with speaker info
                if call_ids:
                    first_call_id = call_ids[0]
                    cursor = repo.conn.execute("""
                        SELECT c.call_title, c.call_date, c.account_id,
                               cp.name as speaker_name, cp.title as speaker_title
                        FROM calls c
                        LEFT JOIN call_participants cp ON c.call_id = cp.call_id
                        WHERE c.call_id = ?
                          AND cp.affiliation = 'External'
                          AND cp.speaker_questions IS NOT NULL
                        LIMIT 1
                    """, (first_call_id,))
                    row = cursor.fetchone()
                    if row:
                        acc_cursor = repo.conn.execute("""
                            SELECT domain FROM accounts WHERE id = ?
                        """, (row['account_id'],))
                        acc_row = acc_cursor.fetchone()
                        account = acc_row['domain'] if acc_row else 'Unknown'
                        call_date = datetime.fromisoformat(row['call_date'])
                        call_date_str = call_date.strftime('%b %d, %Y')
                        speaker_name = row['speaker_name'] or 'Unknown'
                        speaker_title = row['speaker_title'] or ''
                        speaker_info = f"{speaker_name}, {speaker_title}" if speaker_title else speaker_name
                        gong_url = format_gong_url(first_call_id)
                        st.markdown(f"   ↳ Example: [{account} - {call_date_str} - {speaker_info}]({gong_url}) 🔗", unsafe_allow_html=True)

            # Expandable section for all questions
            if len(questions) > 5:
                with st.expander(f"See all {len(questions)} questions in this theme"):
                    for j, q in enumerate(questions, 1):
                        question = q['question']
                        freq = q['frequency']
                        call_ids = q['call_ids']

                        st.markdown(f"{j}. **{question}** (asked {freq}x)")

                        # Show sample calls with speaker info
                        if call_ids:
                            # Get call details with speaker info
                            call_info_list = []
                            for call_id in call_ids[:3]:  # Show up to 3 sample calls
                                cursor = repo.conn.execute("""
                                    SELECT c.call_title, c.call_date, c.account_id,
                                           cp.name as speaker_name, cp.title as speaker_title
                                    FROM calls c
                                    LEFT JOIN call_participants cp ON c.call_id = cp.call_id
                                    WHERE c.call_id = ?
                                      AND cp.affiliation = 'External'
                                      AND cp.speaker_questions IS NOT NULL
                                    LIMIT 1
                                """, (call_id,))
                                row = cursor.fetchone()
                                if row:
                                    # Get account domain
                                    acc_cursor = repo.conn.execute("""
                                        SELECT domain FROM accounts WHERE id = ?
                                    """, (row['account_id'],))
                                    acc_row = acc_cursor.fetchone()
                                    account = acc_row['domain'] if acc_row else 'Unknown'
                                    speaker_name = row['speaker_name'] or 'Unknown'
                                    speaker_title = row['speaker_title'] or ''

                                    call_info_list.append({
                                        'call_id': call_id,
                                        'call_title': row['call_title'],
                                        'call_date': datetime.fromisoformat(row['call_date']),
                                        'account': account,
                                        'speaker_name': speaker_name,
                                        'speaker_title': speaker_title
                                    })

                            if call_info_list:
                                st.markdown(f"   *Sample calls:*")
                                for call_info in call_info_list:
                                    call_date_str = call_info['call_date'].strftime('%b %d, %Y')
                                    speaker_info = f"{call_info['speaker_name']}, {call_info['speaker_title']}" if call_info['speaker_title'] else call_info['speaker_name']
                                    gong_url = format_gong_url(call_info['call_id'])
                                    st.markdown(f"   - [{call_info['account']} - {call_date_str} - {speaker_info}]({gong_url}) 🔗")

                        st.markdown("")  # Spacing

        st.markdown("")  # Spacing between themes


def render_questions_list(questions_list, persona_name):
    """Render the questions list for a persona."""
    if not questions_list:
        st.info(f"No questions found from {persona_name}s in the selected time range.")
        return

    st.markdown(f"**{len(questions_list)} unique questions** (sorted by frequency)")
    st.markdown("---")

    for i, q_data in enumerate(questions_list, 1):
        question = q_data['question']
        count = q_data['count']
        calls = q_data['calls']

        # Question header
        col1, col2 = st.columns([0.85, 0.15])

        with col1:
            st.markdown(f"**{i}. {question}**")

        with col2:
            st.markdown(f"<span style='color: #3498db; font-weight: bold;'>Asked {count}x</span>",
                       unsafe_allow_html=True)

        # Show first 3 call contexts inline
        if calls:
            st.markdown("*Examples:*")
            for call in calls[:3]:
                call_date_str = call['call_date'].strftime('%b %d')
                speaker_name = call['asker_name'] or 'Unknown'
                speaker_title = call['asker_title'] or ''
                speaker_info = f"{speaker_name}, {speaker_title}" if speaker_title else speaker_name
                gong_url = format_gong_url(call['call_id'])
                st.markdown(f"  - [{call['account']} - {call_date_str} - {speaker_info}]({gong_url}) 🔗")

        # Expandable call details for remaining calls
        if len(calls) > 3:
            with st.expander(f"📞 See all {len(calls)} call(s) where this was asked"):
                for call in calls[3:]:  # Show calls after the first 3
                    call_date_str = call['call_date'].strftime('%b %d, %Y')
                    speaker_name = call['asker_name'] or 'Unknown'
                    speaker_title = call['asker_title'] or ''
                    gong_url = format_gong_url(call['call_id'])
                    st.markdown(f"- [{call['account']} - {call_date_str} - {speaker_name}, {speaker_title}]({gong_url}) 🔗")

        st.markdown("")  # Spacing


def main():
    """Main Persona Analysis page."""

    # Header
    st.markdown('<h1 style="margin-bottom: 0;"><i class="fas fa-theater-masks" style="color: #9b59b6;"></i> Persona Analysis</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #7f8c8d; margin-top: 0; margin-bottom: 1rem;">Understand customer questions by persona type</p>', unsafe_allow_html=True)
    st.markdown("---")

    # Initialize
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()
    repo = Repository(db.conn)

    # Sidebar Filters
    st.sidebar.markdown("### 🔍 Filters")
    st.sidebar.markdown("---")

    days = st.sidebar.selectbox(
        "Time Range",
        options=[7, 30, 90, 365],
        format_func=lambda x: f"Last {x} days",
        index=1  # Default to 30 days
    )

    # Get unique segments
    cursor = repo.conn.execute("SELECT DISTINCT primary_segment FROM accounts WHERE primary_segment IS NOT NULL ORDER BY primary_segment")
    segments = [row[0] for row in cursor.fetchall()]
    segment = st.sidebar.selectbox("Segment", options=["All"] + segments)
    segment = None if segment == "All" else segment

    stage = st.sidebar.selectbox(
        "Stage",
        options=["All", "discovery", "trial", "negotiation", "closed"]
    )
    stage = None if stage == "All" else stage

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎨 View Options")

    view_mode = st.sidebar.radio(
        "Display Mode",
        options=["Themes View", "Raw Questions"],
        index=0
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ Actions")

    if st.sidebar.button("🔄 Regenerate Themes", help="Re-run theme generation with current filters"):
        st.info("Theme regeneration is done via command line. Run: `python scripts/generate_question_themes.py`")

    # Load data
    with st.spinner("Loading participant data..."):
        participants = load_participants_with_questions(repo, days=days, segment=segment, stage=stage)

    if not participants:
        st.warning("No participants with questions found for the selected filters.")
        db.close()
        return

    # Calculate stats
    stats = get_persona_stats(participants)

    # Summary Cards
    st.markdown("### Persona Engagement Summary")
    col1, col2, col3 = st.columns(3)

    with col1:
        render_persona_card(
            "Decision Makers",
            stats['Decision Maker'],
            "fas fa-user-tie",
            "#3498db"
        )

    with col2:
        render_persona_card(
            "Influencers",
            stats['Influencer'],
            "fas fa-handshake",
            "#2ecc71"
        )

    with col3:
        render_persona_card(
            "Users",
            stats['User'],
            "fas fa-code",
            "#e67e22"
        )

    st.markdown("---")

    # Title Distribution Section
    st.markdown("### 📊 Title Distribution by Persona")
    st.markdown("*Understanding which job titles fall under each persona category*")

    title_dist = get_title_distribution(repo, days=days, segment=segment, stage=stage)

    if title_dist:
        df = pd.DataFrame(title_dist)

        # Configure AG Grid
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_default_column(
            filterable=True,
            sortable=True,
            resizable=True,
            filter=True
        )
        gb.configure_selection(selection_mode='none')

        # Configure column widths
        gb.configure_column("Persona", width=150)
        gb.configure_column("Title", flex=1, minWidth=250)
        gb.configure_column("Participants", width=120)
        gb.configure_column("Calls", width=100)

        # Configure pagination
        gb.configure_pagination(
            enabled=True,
            paginationPageSize=20
        )

        # Build grid options
        grid_options = gb.build()

        # Display AG Grid
        AgGrid(
            df,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.MODEL_CHANGED,
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            fit_columns_on_grid_load=False,
            theme='streamlit',
            height=400,
            allow_unsafe_jscode=True,
            reload_data=False,
            enable_enterprise_modules=False
        )

        st.markdown(f"*Showing {len(title_dist)} unique title-persona combinations*")
    else:
        st.info("No title data available for the selected filters.")

    st.markdown("---")

    # Questions by Persona (Tabs)
    if view_mode == "Themes View":
        st.markdown("### 🎯 Question Themes by Persona")
    else:
        st.markdown("### 📋 All Questions by Persona")

    tab1, tab2, tab3 = st.tabs([
        "👔 Decision Makers",
        "🤝 Influencers",
        "👨‍💻 Users"
    ])

    with tab1:
        st.markdown("")  # Spacing
        if view_mode == "Themes View":
            themes = load_themes_for_persona(repo, 'Decision Maker')
            render_themes_view(themes, "Decision Maker", repo)
        else:
            questions = group_questions_by_text(participants, persona_filter='Decision Maker')
            render_questions_list(questions, "Decision Maker")

    with tab2:
        st.markdown("")  # Spacing
        if view_mode == "Themes View":
            themes = load_themes_for_persona(repo, 'Influencer')
            render_themes_view(themes, "Influencer", repo)
        else:
            questions = group_questions_by_text(participants, persona_filter='Influencer')
            render_questions_list(questions, "Influencer")

    with tab3:
        st.markdown("")  # Spacing
        if view_mode == "Themes View":
            themes = load_themes_for_persona(repo, 'User')
            render_themes_view(themes, "User", repo)
        else:
            questions = group_questions_by_text(participants, persona_filter='User')
            render_questions_list(questions, "User")

    db.close()


if __name__ == "__main__":
    main()
