"""Pagination utilities for Streamlit."""

import streamlit as st


def paginate(items, items_per_page=10, key_prefix="page"):
    """
    Paginate a list of items and return the current page's items.

    Args:
        items: List of items to paginate
        items_per_page: Number of items per page
        key_prefix: Unique prefix for session state keys

    Returns:
        Tuple of (current_page_items, pagination_controls)
    """
    total_items = len(items)
    total_pages = (total_items + items_per_page - 1) // items_per_page

    # Initialize page in session state
    page_key = f"{key_prefix}_current_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    current_page = st.session_state[page_key]

    # Calculate slice
    start_idx = (current_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)

    current_items = items[start_idx:end_idx]

    return current_items, total_pages, current_page


def show_pagination_controls(total_pages, current_page, key_prefix="page"):
    """
    Show pagination controls (Previous/Next buttons and page indicator).

    Args:
        total_pages: Total number of pages
        current_page: Current page number
        key_prefix: Unique prefix for session state keys
    """
    if total_pages <= 1:
        return

    page_key = f"{key_prefix}_current_page"

    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])

    with col1:
        if st.button("⏮️ First", disabled=(current_page == 1), key=f"{key_prefix}_first"):
            st.session_state[page_key] = 1
            st.rerun()

    with col2:
        if st.button("◀️ Previous", disabled=(current_page == 1), key=f"{key_prefix}_prev"):
            st.session_state[page_key] = max(1, current_page - 1)
            st.rerun()

    with col3:
        st.markdown(
            f"<div style='text-align: center; padding: 5px;'>"
            f"Page {current_page} of {total_pages}</div>",
            unsafe_allow_html=True
        )

    with col4:
        if st.button("Next ▶️", disabled=(current_page == total_pages), key=f"{key_prefix}_next"):
            st.session_state[page_key] = min(total_pages, current_page + 1)
            st.rerun()

    with col5:
        if st.button("Last ⏭️", disabled=(current_page == total_pages), key=f"{key_prefix}_last"):
            st.session_state[page_key] = total_pages
            st.rerun()


def show_page_selector(total_pages, current_page, key_prefix="page"):
    """
    Show a page number selector dropdown.

    Args:
        total_pages: Total number of pages
        current_page: Current page number
        key_prefix: Unique prefix for session state keys
    """
    if total_pages <= 1:
        return

    page_key = f"{key_prefix}_current_page"

    selected_page = st.selectbox(
        "Jump to page:",
        options=list(range(1, total_pages + 1)),
        index=current_page - 1,
        key=f"{key_prefix}_selector"
    )

    if selected_page != current_page:
        st.session_state[page_key] = selected_page
        st.rerun()
