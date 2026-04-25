---
module: sauspiel_scraper
date: 2026-04-25
last_updated: 2026-04-25
problem_type: convention
component: streamlit
severity: low
applies_when:
  - "Writing or updating Streamlit UI components"
symptoms:
  - "Deprecation warnings for `use_container_width`"
root_cause: streamlit_api_change
resolution_type: convention
tags:
  - streamlit
  - frontend
  - convention
---

# Streamlit Standards: Component Sizing

## Context
Streamlit has deprecated the `use_container_width` parameter in favor of a more flexible `width` parameter. To ensure future compatibility and consistent UI behavior, this project follows the new standard.

## Guidance
Always use the `width` parameter instead of `use_container_width`.

1.  **Full Width**: For components that should stretch to fill their container (equivalent to `use_container_width=True`), use:
    ```python
    width="stretch"
    ```
2.  **Content-based Width**: For components that should size themselves based on their content (equivalent to `use_container_width=False`), use:
    ```python
    width="content"
    ```

### Affected Components
This convention applies to all Streamlit components that previously used `use_container_width`, including but not limited to:
*   `st.button`
*   `st.form_submit_button`
*   `st.download_button`
*   `st.dataframe`
*   `st.plotly_chart`
*   `st.image`

## Examples

### Before (Deprecated)
```python
st.dataframe(df, use_container_width=True)
st.button("Submit", use_container_width=False)
```

### After (Standard)
```python
st.dataframe(df, width="stretch")
st.button("Submit", width="content")
```

## Why This Matters
*   **Forward Compatibility**: Prevents breakage when `use_container_width` is removed (scheduled for after 2025-12-31).
*   **Consistency**: Ensures all UI elements follow the same sizing logic across the application.
