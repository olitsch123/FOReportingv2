"""Session state management utilities."""

import streamlit as st
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "selected_files": set(),
        "chat_session_id": None,
        "chat_messages": [],
        "current_investor": None,
        "processing_status": {},
        "last_refresh": None,
        "api_errors": [],
        "selected_fund_id": None,
        "view_mode": "simple",
        "batch_size": 100,
        "auto_refresh": False
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def get_state(key: str, default: Any = None) -> Any:
    """Get value from session state with default."""
    return st.session_state.get(key, default)


def set_state(key: str, value: Any) -> None:
    """Set value in session state."""
    st.session_state[key] = value


def update_state(updates: Dict[str, Any]) -> None:
    """Update multiple session state values."""
    for key, value in updates.items():
        st.session_state[key] = value


def clear_state(keys: Optional[List[str]] = None) -> None:
    """Clear specific keys or all session state."""
    if keys is None:
        st.session_state.clear()
        init_session_state()
    else:
        for key in keys:
            if key in st.session_state:
                del st.session_state[key]


def add_to_set(key: str, value: Any) -> None:
    """Add value to a set in session state."""
    if key not in st.session_state:
        st.session_state[key] = set()
    st.session_state[key].add(value)


def remove_from_set(key: str, value: Any) -> None:
    """Remove value from a set in session state."""
    if key in st.session_state and isinstance(st.session_state[key], set):
        st.session_state[key].discard(value)


def toggle_in_set(key: str, value: Any) -> bool:
    """Toggle value in a set, return True if added, False if removed."""
    if key not in st.session_state:
        st.session_state[key] = set()
    
    if value in st.session_state[key]:
        st.session_state[key].remove(value)
        return False
    else:
        st.session_state[key].add(value)
        return True


def get_selected_files() -> Set[str]:
    """Get currently selected files."""
    return get_state("selected_files", set())


def set_selected_files(files: Set[str]) -> None:
    """Set selected files."""
    set_state("selected_files", files)


def clear_selected_files() -> None:
    """Clear all selected files."""
    set_state("selected_files", set())


def add_api_error(error: str) -> None:
    """Add an API error to the error list."""
    errors = get_state("api_errors", [])
    errors.append({
        "timestamp": st.session_state.get("last_refresh"),
        "error": error
    })
    # Keep only last 10 errors
    set_state("api_errors", errors[-10:])


def get_api_errors() -> List[Dict[str, Any]]:
    """Get recent API errors."""
    return get_state("api_errors", [])


def clear_api_errors() -> None:
    """Clear API error history."""
    set_state("api_errors", [])


def update_processing_status(file_path: str, status: str) -> None:
    """Update processing status for a file."""
    processing = get_state("processing_status", {})
    processing[file_path] = {
        "status": status,
        "timestamp": datetime.now().isoformat()
    }
    set_state("processing_status", processing)


def get_processing_status(file_path: str) -> Optional[Dict[str, Any]]:
    """Get processing status for a file."""
    processing = get_state("processing_status", {})
    return processing.get(file_path)